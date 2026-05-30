# Discussion: Replace manual layer letters with depends_on + isolated flags

```yaml
task: Replace manual layer letters with depends_on + isolated flags
slug: task-deps-and-isolation
status: discussing
parent: main
```

## Problem

Task layers in the wiki (`# Layer A`, `# Layer B`, ..., `# Layer Z`) are
manually assigned by the operator when a task is added. The letter is meant to
encode a DAG of parallel execution (A = no dependency, B = depends on something
in A, Z = must run alone), but the operator has to hold the dependency graph in
their head and pick a letter that matches. This invites mis-classification (on
2026-05-27 `mill-ghissues-to-tasks` put four cluster tasks in Z when they were
really A — "isolation" was confused with "low priority"), and the letters rot:
when a dependency completes, its dependents do not auto-promote toward A.

The fix: store the dependency graph explicitly per task and let render derive
the letters. Two booleans capture the cases a pure DAG cannot: `isolated`
(must run alone, the old Z) and `deferred` (a real but very-late backlog —
"someday", not forgotten). Much of today's Layer D is in fact low-priority
backlog rather than a genuine dependency layer; `deferred` gives it a home.

## Scope

**In:**

- New per-task storage fields in `wiki/_store.py` (`tasks.json`): `depends_on:
  list[str]` (slugs), `isolated: bool`, `deferred: bool`. Remove the `group`
  field.
- Write-time validation in `wiki/_store.py` (cycle, dangling, depends-on-target
  must be schedulable, reverse-direction guards on isolate/defer, type checks).
- Rewrite of `wiki/_render.py` bucket assignment: derive layers from the DAG
  via a shared `compute_layers()` helper; new `# Someday` section; remove the
  now-unreachable `# Unspecified` section.
- New `set_deps` operation across `wiki/__init__.py` (op + error constants +
  exception), `wiki/_store.py`, `wiki/_server.py`, `wiki/_client.py`.
- `wiki/_client.py` `upsert_task` signature: drop `group=`, add `depends_on=`,
  `isolated=`, `deferred=`. New `set_deps()` client function. New
  `WikiValidationError` raised for all validation failures.
- `PROTOCOL_VERSION` bump `2 -> 3` (`wiki/__init__.py` + `_server._protocol_version`).
- `list_tasks_brief` key-set change (see Decisions) and its pinned unit test.
- A one-shot, idempotent migration performed **server-side** by the daemon: a
  new `OP_MIGRATE_DEPS` op + `Store` migration method + `_client.migrate_deps`
  wrapper + a thin `millpy-wiki-migrate-deps.py` runner.
- **Folded scope (#14):** extract `extended_title(task)` and
  `render_order(tasks)` helpers in `wiki/_render.py`; adopt them in
  `millpy-spawn`/`_spawn_core.py`, `millpy-status.py`, `millpy-inspect.py` so
  every operator-facing task list matches Home.md ordering and titles.
- **Folded scope (orphan cleanup):** add a regression test proving
  `remove_task` deletes and stages the orphaned `proposal-*.md`. The code in
  `_server._render_and_commit_all` already does this; fix only if the test fails.

**Out:**

- A richer priority scale. `deferred` is a single bool, not a 1..n priority
  (YAGNI). If finer ranking is ever needed it is a separate task.
- An interactive UI for editing deps beyond `set_deps` / `upsert_task`.
- Promoting Done tasks back into the backlog (separate concern).
- Changes to the orchestration loop (`mill-go`), review pipeline, or plan
  validator. This is a wiki storage + render change only.
- Cascading mutations: removing a task does not rewrite its dependents'
  `depends_on`; deferring/isolating a task does not auto-mutate dependents
  (those writes are *rejected*, see Decisions).
- Updating operator-facing task-creation skill prose (`mill-add`, etc.) to
  prompt for deps/flags — those skills do not pass `group` to the store today,
  so nothing breaks; refreshing their guidance is a follow-up.

## Decisions

### schema-fields

- Decision: In each `tasks.json` record, remove `group`; add `depends_on:
  list[str]` (default `[]`), `isolated: bool` (default `False`), `deferred:
  bool` (default `False`). The layer letter is **never stored** — it is derived
  at render time.
- Rationale: The DAG is the source of truth; a stored letter is the thing that
  rots. Slugs (not numeric ids) are used in `depends_on` because task numbers
  are recycled when a task is removed and a new one added.
- Rejected: Keeping `group` as a write-through fallback (proposal option a) —
  two sources of truth re-introduces the rot. Hard cut-over is cleaner.

### derivation-single-source

- Decision: One function `compute_layers(tasks: list[dict]) -> dict[str, str]`
  in `wiki/_render.py` maps each task slug to its bucket label. `render()`,
  `render_order()`, and `extended_title()` all call it. Bucket labels are
  `"A"`..`"Z"`, `"__deferred__"`, `"__done__"`.
- Rationale: Home.md and every operator-facing list must agree. A single
  function is the only way to guarantee that.
- Rejected: Computing in `_store` on read (couples storage to presentation);
  duplicating logic in the helpers (the exact bug #14 exists to kill).

### layer-algorithm

- Decision: Bucket precedence is `done > deferred > isolated > topo`:
  1. `status == "done"` -> `__done__`.
  2. else `deferred == True` -> `__deferred__`.
  3. else `isolated == True` -> `"Z"` (all isolated tasks share Layer Z).
  4. else topo level: `effective_deps = [d for d in depends_on if the task d is
     not done]`. A task with no effective deps -> `"A"`. Otherwise its level is
     `1 + max(level of each effective dep)`, mapped `0->A, 1->B, ...`.
- Decision: Letter cap is **A..Y (25 levels)** for topo tasks; `Z` is reserved
  for isolated. If a topo task would compute past Y, `render()`/`compute_layers`
  **raises** (loudly, so the operator untangles) rather than silently truncating.
- Decision: A cycle in `depends_on` makes topo non-terminating; `compute_layers`
  **raises** with the cycle path. (This is the render-time backstop; writes are
  already rejected — see validation.)
- Rationale: Matches the proposal. Filtering done deps is what makes dependents
  auto-promote toward A as work completes (see done-deps-satisfied).
- Rejected: Shortest-path / min-level assignment (does not reflect "must wait
  for the deepest prerequisite").

### done-deps-satisfied

- Decision: A dependency whose target task has `status == "done"` is filtered
  out of `effective_deps` before topo. A task whose deps are all done becomes A.
- Rationale: This is the auto-promotion the manual letters never delivered.
- Rejected: Treating all listed deps as binding regardless of done status
  (dependents would never promote).

### depends-on-invariant

- Decision: A task's `depends_on` may reference **only** tasks that are
  schedulable-active (not `isolated`, not `deferred`) **or** already `done`.
  Equivalently: **no task may depend on an isolated or deferred task.** This is
  enforced at write time (see validation). A task that is itself isolated or
  deferred *may* still carry `depends_on` (pointing at active/done tasks); those
  deps are recorded and displayed but ignored for its own bucket placement.
- Rationale: Depending on a deferred ("someday") task while you are not deferred
  is incoherent — you have prioritised the dependent above its own
  prerequisite. The same reasoning makes a dependency on an out-of-pipeline
  isolated task ill-defined for layering. Forbidding both keeps every non-done
  dependency inside A..Y, so `compute_layers` is always well-defined — no
  "dep has no level" edge case.
- Rejected: Silently filtering deferred/isolated deps out of the layer math (the
  state is incoherent and should be surfaced, not hidden); treating such a dep
  as level-A (papers over the contradiction).

### deferred-flag

- Decision: `deferred: bool`. Deferred (and not done) tasks render under a new
  `# Someday` section. Render order: lettered layers `A..Z` -> `# Someday` ->
  `# Done`. The old `# Unspecified` (`group == None`) section is **removed** —
  in the new model every active task computes to a letter (A when it has no
  deps), so `# Unspecified` is unreachable.
- Rationale: A genuine "very late backlog, not forgotten" bucket, kept visible
  below the active layers and above the closed-out Done section.
- Rejected: A `priority` integer (over-engineered); placing Someday after Done
  (it is open work, not closed); a free-form section parsed from prose.

### display-format

- Decision: In Home.md each task heading keeps a derived `[letter]` suffix for
  **A..Z (active/isolated) tasks only**. Deferred and done tasks render under
  their section header with **no** bracket suffix (the section is the
  classifier; this changes the current "done retains its `[A]`/`[Z]` suffix"
  behaviour — the pinned `test-wiki-render` case is updated). A task with a
  non-empty effective `depends_on` gets a `Depends on: #NNN, #MMM` line (deps
  shown by **task number**, translated from slug at render time) placed directly
  under the `[slug](proposal-...)` line. The line is omitted when there are no
  deps. Isolated and deferred tasks that carry deps still show the line.
- Decision: A dep slug that is not present in the task set (a target removed
  after the edge was created) renders as `#???: <slug> (missing)` and is ignored
  for layering. Write-time validation prevents *creating* a dangling edge;
  later removal of a depended-on task is tolerated and degrades to this display
  rather than cascading.
- Rationale: Numbers are what the operator reads on the board; slugs are what
  storage needs. Tolerating post-hoc dangling avoids cascade-blocking on
  removal (numbers recycle; removal should not be a graph-wide veto).
- Rejected: Showing deps by slug (operator reads numbers); rejecting `remove_task`
  when dependents exist (cascade-blocking is heavier than the proposal wants).

### validation

- Decision: All write paths in `wiki/_store.py` (`upsert_task`,
  `upsert_tasks_batch`, `merge_tasks`, the new `set_deps`) validate **before**
  any mutation and raise `ValueError` on:
  - **type**: `depends_on` not `list[str]`, `isolated`/`deferred` not `bool`,
    or a stray `group` key present (catches un-migrated callers).
  - **dangling**: a slug in `depends_on` that does not exist in the store.
  - **cycle**: `depends_on` edges that form a cycle (error names the path).
  - **target-not-schedulable**: a slug in `depends_on` whose target is
    `isolated` or `deferred`.
  - **reverse-isolate**: setting `isolated = True` on a task that some other
    task depends on. Error names the dependents.
  - **reverse-defer**: setting `deferred = True` on a task that some
    *non-deferred* task depends on. Error names the dependents. (Both reverse
    guards reject — no cascade; the operator defers/isolates dependents first or
    removes the edge.)
- Decision: `_server` maps `ValueError` from the store to a new
  `ERR_VALIDATION` error type; `_client` raises a new `WikiValidationError`
  (subclass of `WikiError`) so callers distinguish bad input from protocol
  faults. `WikiPushError` handling is unchanged.
- Rationale: Validating before mutation preserves the store/rendered-file
  consistency guarantee already relied on by `merge_tasks` (see its existing
  empty-upsert test). A typed error keeps "you sent garbage" separate from "the
  wire broke".
- Rejected: Reusing `ERR_PROTOCOL`/`WikiProtocolError` (conflates input errors
  with transport errors); validating in the daemon instead of the store (the
  store is the only layer that sees the full task set atomically).

### set-deps-op

- Decision: Add a `set_deps` operation end to end: `OP_SET_DEPS` constant,
  `Store.set_deps(slug, depends_on)`, `_server._handle_set_deps`, and
  `_client.set_deps(wiki_path, slug, depends_on)`. It runs the same validation
  as `upsert_task`.
- Rationale: Operators need to edit the graph without rewriting a task's body.
  Small, well-scoped surface.
- Rejected: Forcing all dep edits through `upsert_task(depends_on=...)` (works,
  but clumsy for a graph-only edit).

### protocol-bump

- Decision: Bump `PROTOCOL_VERSION` `2 -> 3` in `wiki/__init__.py` and
  `WikiServer._protocol_version`.
- Rationale: The payload schema changes (new fields, new op). The client already
  kills + respawns the daemon on version mismatch, so a stale daemon can never
  mishandle the new fields.
- Rejected: Leaving it at 2 (additive-but-risky; a stale daemon would silently
  drop unknown payload keys).

### brief-shape

- Decision: `list_tasks_brief` rows change from
  `{id, slug, title, group, brief, status, has_proposal}` to
  `{id, slug, title, depends_on, isolated, deferred, layer, brief, status,
  has_proposal}`. `layer` is the **derived** bucket label (read-only;
  `compute_layers` output). The pinned key-set assertion in `test-wiki-store`
  is updated.
- Rationale: Consumers (`millpy-spawn`/status/inspect) need the derived letter
  for display and the raw flags for any future filtering. Exposing the derived
  `layer` keeps consumers from re-implementing topo.
- Rejected: Keeping the key named `group` but holding the derived letter
  (misleading name); not exposing the raw flags (forecloses filtering).

### migration

- Decision: The migration runs **server-side, inside the daemon**, as a new
  one-shot op `OP_MIGRATE_DEPS` (client wrapper `_client.migrate_deps(wiki_path)`,
  triggered by a thin `plugins/mill/scripts/millpy-wiki-migrate-deps.py`
  runner). The daemon is the single serialised owner of `tasks.json`, so doing
  the migration as a daemon op removes the respawn race entirely — no external
  process rewrites the file, and the normal pull -> migrate -> render -> commit
  cycle applies. The handler calls `Store.migrate_group_to_deps()` and then the
  existing `_render_and_commit_all`.
- Decision: `Store.migrate_group_to_deps()` rewrites every record **in place via
  the TinyDB API**, preserving both the internal `doc_id` and the task `id`
  field: for each record apply TinyDB's `delete("group")` operation to drop the
  key plus a field-set update adding `depends_on = []`, `isolated = (group ==
  "Z")`, `deferred = False`. Records that already lack `group` are skipped, so a
  re-run is a no-op (idempotent). No clear-and-reinsert (that would re-key
  doc_ids); `id` is never recomputed.
- Rationale: A daemon-owned op is race-free by construction and keeps the
  "daemon owns all wiki writes" invariant intact — no daemon-shutdown /
  direct-rewrite dance (the round-1 review flagged that as a correctness hole:
  `_client` auto-respawns on the next call, leaving the rewrite window
  unprotected and doc_id/id preservation ambiguous). TinyDB's `delete` operation
  is the precise tool for dropping a key while leaving doc_id/id untouched.
  `depends_on = []` for everyone (letters cannot be reversed into edges);
  `isolated = (group == "Z")` is the one recoverable mapping; `deferred = False`
  for everyone — auto-setting `deferred = (group == "D")` was rejected (QD):
  "much of" Layer D is low-pri, not all. Operator re-curates edges and marks
  low-pri tasks afterward.
- Rejected: Shutting the daemon down and rewriting `tasks.json` from an external
  process (the round-1 GAP — unprotected respawn window, ambiguous id handling);
  rewriting records wholesale via clear-and-reinsert (re-keys TinyDB doc_ids);
  lazy auto-migration on every `Store` load (hot-path cost); a manual hand-edit.

### folded-orphan-cleanup

- Decision: Treat the orphan `proposal-*.md` cleanup as **already implemented**.
  `_server._render_and_commit_all` (around lines 345-365) globs existing
  `proposal-*.md`, unlinks those not in the freshly-rendered set, and includes
  the orphan names in `commit_paths`. Add a regression test that calls
  `remove_task` for a task with a proposal and asserts the file is deleted and
  the deletion is staged/committed. Fix the code only if that test fails.
- Rationale: Don't rewrite working code on the strength of a stale bug report;
  pin it with a test instead.
- Rejected: Blindly re-implementing the cleanup path per the proposal's
  suspicion.

## Technical context

`wiki/` is a 7-file package under `plugins/mill/scripts/wiki/` — the deliberate
V3 module exception (flat `_*.py` elsewhere). `tasks.json` (TinyDB) is the source
of truth; the daemon renders derived files (`Home.md`, `_Sidebar.md`,
`proposal-*.md`) on every mutation and commits/pushes them.

Files and what changes:

- `wiki/__init__.py` — protocol constants and exceptions. Add `OP_SET_DEPS`,
  `OP_MIGRATE_DEPS`, `ERR_VALIDATION`, `class WikiValidationError(WikiError)`.
  Bump `PROTOCOL_VERSION` 2 -> 3.
- `wiki/_store.py` (`class Store`) — new-task default dicts currently seed
  `group: None` in three places (`upsert_task`, `upsert_tasks_batch`,
  `merge_tasks`); replace with `depends_on: []`, `isolated: False`, `deferred:
  False`. Add validation (a private helper run by all write paths, given the
  full task set via `self._db.all()`), `set_deps`, `migrate_group_to_deps`
  (drops `group` via TinyDB `delete("group")` + sets new fields in place,
  preserving doc_id/`id`, idempotent), and update `list_tasks_brief`'s returned
  dict. `merge_tasks` already validates the upsert payload before mutating —
  extend that pattern; keep the "nothing removed on invalid input" guarantee
  (pinned by an existing test).
- `wiki/_render.py` (`render`, currently 100 lines) — replace the `group`-based
  bucketing with `compute_layers`. Add `extended_title(task)` and
  `render_order(tasks)`. Render order: `A..Z` (letters sorted) -> `# Someday`
  -> `# Done`. Drop the `# Unspecified` branch. Build the `Depends on:` line
  from each task's effective deps, mapping slug -> id via the task map, with the
  `#???: <slug> (missing)` fallback. `render()` stays a thin orchestrator over
  the three helpers.
- `wiki/_server.py` (`WikiServer`) — add `OP_SET_DEPS` and `OP_MIGRATE_DEPS`
  dispatch + `_handle_set_deps` / `_handle_migrate_deps` (the latter calls
  `Store.migrate_group_to_deps()` then `_render_and_commit_all`); map store
  `ValueError` -> `ERR_VALIDATION` in the `except` arms of the mutating handlers
  (`_handle_upsert_task`, `_handle_upsert_tasks_batch`, `_handle_merge_tasks`,
  `_handle_set_deps`); set `_protocol_version = 3`. The render call
  (`render(self._store.all_tasks())`) and orphan-cleanup block are unchanged.
- `wiki/_client.py` — `upsert_task`: drop `group=`, add `depends_on=`,
  `isolated=`, `deferred=` (only attach to payload when not `None`). Add
  `set_deps(wiki_path, slug, depends_on)` and `migrate_deps(wiki_path)`. Add an
  `ERR_VALIDATION -> WikiValidationError` branch to every mutating wrapper's
  error handling.
- `wiki/_parse.py` — parses the legacy hand-written `# Layer X` board; used only
  by the *original* `millpy-wiki-migrate.py` bootstrap. Unchanged by this task
  (the new migration operates on already-parsed `tasks.json` records).
- Consumers of the title/letter display: `millpy-status.py`,
  `millpy-inspect.py`, `_spawn_core.py`/`millpy-spawn.py`. They call
  `wiki.list_tasks_brief`; route their list through `render_order` and format
  each line with `extended_title` so all three match Home.md.

Gotchas:

- `print()`/log output is ASCII only (Windows cp1252) — use ` -- ` / ` -> `,
  never em-dash or unicode arrows, in any script/CLI output (validation error
  strings included, since they surface to the operator).
- Slugs in storage, numbers in display — the slug->id map only exists at render
  time (it needs the full task set), which is why `Depends on:` numbers are a
  render concern, not a store concern.
- TinyDB `update` merges keys and cannot delete `group`; the migration must
  rewrite records wholesale (see migration decision).
- Daemon auto-respawns on protocol mismatch — after the bump, the first client
  call kills the running daemon and starts a v3 one; expect one respawn.

## Constraints

- All wiki mutations go through the daemon (`_client` ops) which serialises
  writes and pushes — including this task's migration, which is a daemon op
  (`OP_MIGRATE_DEPS`), not an external rewrite. There is no daemon-shutdown /
  direct-`tasks.json` exception (the round-1 review rejected that approach).
- Working state (`_mill/`) never goes to the wiki; this task touches only the
  wiki package code + tests, not wiki *content* (beyond the migration the
  operator runs).
- Unit tests use `uv run --project plugins/mill`; they run in-process
  (`WIKI_DAEMON_INPROCESS=1` / `use_inprocess`) with no real git or LLM.

## Testing

TDD candidates (write tests first):

- **`wiki/_store.py` validation** (`test-wiki-store`): each rule in its own
  case — dangling, cycle (assert the path appears), target-isolated,
  target-deferred, reverse-isolate, reverse-defer, type errors (bad
  `depends_on`/`isolated`/`deferred`, stray `group`). Assert "no mutation on
  invalid input" (extend the existing empty-`merge_tasks` guard test). New-field
  defaults (`depends_on []`, `isolated`/`deferred` `False`). Updated
  `list_tasks_brief` key set. `set_deps` happy-path + validation.
- **`wiki/_render.py` / `compute_layers`** (`test-wiki-render`): topo levels
  (A/B/C by depth); done-dep promotion (dep done -> dependent moves toward A);
  isolated -> Z (shared); deferred -> `# Someday`; precedence
  done>deferred>isolated>topo; A..Y cap overflow raises; cycle raises; dangling
  dep -> `#???: <slug> (missing)` and ignored for layering; render order
  `A..Z -> Someday -> Done`; `# Unspecified` no longer emitted;
  `Depends on: #NNN` shows numbers and is omitted when empty; done/deferred
  carry no `[letter]` suffix. Direct unit tests for `extended_title` and
  `render_order` in isolation. Keep the byte-identical-double-render test.
- **`wiki/_server.py`** (`test-wiki-daemon` or a focused new test):
  `OP_SET_DEPS` round-trips; store `ValueError` surfaces as `ERR_VALIDATION`;
  **orphan-cleanup regression** — `remove_task` on a task with a proposal
  deletes and stages `proposal-<slug>.md`.
- **`wiki/_client.py`** (`test-wiki-protocol` / client test): new kwargs reach
  the payload; `ERR_VALIDATION` -> `WikiValidationError`; `set_deps` wrapper.
- **migration** (`test-wiki-store` for `Store.migrate_group_to_deps`, plus a
  daemon/op round-trip test): maps `group == "Z"` -> `isolated`, everything else
  -> `isolated False`; sets `deferred False`, `depends_on []`; drops the `group`
  key; preserves TinyDB `doc_id` **and** the `id` field (and `slug`/`body`);
  idempotent on a second run (records without `group` untouched). The
  `OP_MIGRATE_DEPS` round-trip re-renders Home.md from the migrated store.
- **consumers**: `test-millpy-spawn`, `test-status`, `test-inspect` (whichever
  exist) — list output uses `render_order` + `extended_title` and matches
  Home.md ordering/titles.

Scenarios that must be covered: empty store; a task depending on a since-removed
task (dangling display); a deferred task that itself has deps on active tasks
(deps displayed, task in Someday); an isolated task with deps; a diamond
dependency (two deps at different depths -> level = max + 1); attempting every
forbidden write (each rejected, store unchanged).

## Q&A log

- **Q:** Store deps as slugs or task numbers? **A:** Slugs — numbers are
  recycled when tasks are removed and re-added.
- **Q:** Soft (keep `group` as fallback) or hard (drop `group`) migration?
  **A:** Hard — one source of truth; letters rot.
- **Q:** `list_tasks_brief` shape? **A:** Replace `group` with
  `depends_on`+`isolated`(+`deferred`), add a derived read-only `layer`; update
  the pinned test.
- **Q:** Where does layer derivation live? **A:** One `compute_layers()` in
  `_render.py`, shared by `render`/`render_order`/`extended_title`.
- **Q:** Migration mechanism for the live `tasks.json`? **A:** A dedicated
  idempotent one-shot script, not a lazy in-daemon migration.
- **Q:** Include the `set_deps` op? **A:** Yes.
- **Q:** Keep the two folded-in items in scope? **A:** Yes — #14 helpers +
  adopt in spawn/status/inspect, and a regression test for orphan cleanup.
- **Q:** Validation error surfacing? **A:** New `ERR_VALIDATION` +
  `WikiValidationError`, distinct from protocol faults.
- **Q:** Bump `PROTOCOL_VERSION`? **A:** Yes, 2 -> 3.
- **Q:** Type-validate the new fields at write? **A:** Yes, fail-fast; reject a
  stray `group` key.
- **Q:** Do isolated tasks still display their deps? **A:** Yes — deps are
  recorded and shown even though ignored for the task's own layering.
- **Q:** Do done deps count as satisfied (auto-promotion)? **A:** Yes — filter
  done deps from effective deps before topo.
- **Q:** Add a low-priority flag? **A:** Yes — `deferred: bool`, rendered in a
  new `# Someday` section between the lettered layers and Done.
- **Q:** Section placement? **A:** `A..Z -> Someday -> Done`; it is open work,
  not closed.
- **Q:** Can a non-deferred task depend on a deferred task? **A:** No — it is
  incoherent; reject at write. Generalised: no task may depend on an isolated or
  deferred task (depends_on must point at active or done tasks only).
- **Q:** Enforce the reverse direction (deferring/isolating a depended-on task)?
  **A:** Reject the write naming the dependents; no cascade.
- **Q:** Migrate existing Layer D to `deferred`? **A:** No — set `deferred=False`
  for all; operator marks the real low-pri ones afterward ("much of" D is
  low-pri, not all).
- **Q:** (review r1 GAP) How does the migration avoid the daemon-respawn race
  and preserve ids? **A:** Run it server-side as a daemon op
  (`OP_MIGRATE_DEPS`) calling `Store.migrate_group_to_deps()`, which uses
  TinyDB's `delete("group")` operation plus a field-set update to drop `group`
  and add the new fields in place — `doc_id` and `id` preserved, no external
  rewrite, idempotent.
