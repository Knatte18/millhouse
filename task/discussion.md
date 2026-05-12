# Discussion: (A) — Small infra fixes batch 7

```yaml
task: (A) — Small infra fixes batch 7
slug: mill-misc-fixes-7
status: discussing
parent: main
```

## Problem

Three unrelated infrastructure bugs in the mill plugin surfaced from recent
mill-self-report runs and operator observations. Each one is small in isolation
but each one wastes operator time on a cryptic failure path. Bundled into one
task so the round-trip cost (spawn → plan → go → merge) amortises across all
three:

- **#273** — When the wiki directory disappears or its `config.yaml` is removed
  between batches (e.g. operator wipes it manually, or a buggy implementer
  `rm`s it), `millpy-implement.py` fails on the NEXT batch with the generic
  `"Missing config at <path>/config.yaml"` error. The error looks like a
  schema/config issue rather than a wiki-availability issue. mill-go does NOT
  perform a wiki health check between batches — only the Entry step calls
  `_wiki.sync_pull`.

- **#274** — On a second `/mill-setup` run, `_setup.create_hub_links` calls
  `_junction.create` unconditionally for every junction entry from
  `wiki/config.yaml`. The `_junction.create` helper documents that it raises
  `ValueError` on already-existing paths. The hardlinks block in the same
  function already has an inode-check idempotency pattern; the junctions block
  does not. Observed crash:
  `ValueError: C:\Code\millhouse\wts\millhouse\.wiki already exists — remove it
  before creating a junction` during Phase 4 of mill-setup re-run.

- **#276** — `_status.set_blocked` writes both `phase: blocked` and a
  `blocked_reason: <text>` row into the top YAML block. A subsequent call to
  `_status.append_phase(status_path, "<new-phase>", ts)` overwrites `phase:` but
  leaves `blocked_reason:` intact. Once a task advances past blocked, the stale
  `blocked_reason:` row sits in `status.md` indefinitely and misleads downstream
  inspectors (`millpy-status.py`, `mill-inspect`, dashboards). Concrete observed
  example was the `skills-direct-venv-invocation` task — `phase: planned` with
  `blocked_reason: 'auto: discussion review gaps unresolved after 2 rounds'`
  still present.

**Why now:** All three bugs were filed within the last 24 hours; the
mill-self-report queue is being drained by mill-ghissues-to-tasks, and bundling
small fixes into a single task is the established pattern (this is `batch 7` —
matches the pre-existing "small infra fixes batch N" backlog tradition).

## Scope

**In:**

- `plugins/mill/skills/mill-go/SKILL.md` — add a per-batch wiki health-check
  sub-step at the start of the Execute loop (and matching addition to the
  Holistic loop), with a clear `wiki appears missing or corrupted` error
  surface and a hard halt of the entire mill-go session.
- `plugins/mill/scripts/_wiki.py` — add `health_check(wiki_path: Path) -> None`
  helper that raises a typed `WikiHealthError` (new class) when
  `wiki_path/config.yaml` is missing.
- `plugins/mill/scripts/_junction.py` — add `points_to(link_path: Path,
  target: Path) -> bool` helper that returns True iff `link_path` is a
  junction/symlink AND resolves to `target`. Factor the
  "is-junction-or-symlink" detection out of `remove()` into a private helper
  reused by both `remove` and `points_to`.
- `plugins/mill/scripts/_setup.py` — extend `create_hub_links` junction loop
  to mirror the hardlinks inode-check pattern: if `link_path` already exists
  AND points to the correct target → skip (idempotent); if it exists with the
  wrong target → call `_junction.remove(link_path)` (which raises ValueError on
  a real directory or file, preserving the existing safety guard) and then
  recreate via `_junction.create`.
- `plugins/mill/scripts/_status.py` — modify `append_phase` to clear the
  `blocked_reason:` YAML row when the new phase is anything other than
  `blocked`. `set_blocked` is unchanged (it already writes `blocked_reason:`
  correctly).
- `plugins/mill/unit_tests/test-wiki.py` — add tests for the new
  `_wiki.health_check` helper (config present → returns None; config missing →
  raises `WikiHealthError` naming the path).
- `plugins/mill/unit_tests/test-setup-hub-links.py` — add two tests:
  junction-already-correct → idempotent skip; junction-wrong-target → remove
  and recreate.
- `plugins/mill/unit_tests/test-status.py` — add two tests: `append_phase` to
  a non-blocked phase after `set_blocked` clears `blocked_reason:`;
  `append_phase` to `blocked` preserves any existing `blocked_reason:` (this
  edge is unlikely in practice but the helper must be locally consistent).

**Out:**

- `_wiki.sync_pull` is NOT called per-batch. Health check is sufficient to
  surface the reported missing-config failure; `sync_pull` does a `git pull
  --ff-only` and would add real latency per batch with no value for #273.
- `_junction.create` contract is NOT relaxed. It still raises on existing
  paths — the contract documented in the helper docstring is preserved.
  Idempotency lives in the caller (`_setup.create_hub_links`), matching the
  existing convention for hardlinks in the same function.
- `set_blocked` is NOT refactored to share code with `append_phase`. The two
  helpers are visually similar but have different semantics
  (`set_blocked` writes `blocked_reason:`; `append_phase` does not). A unified
  helper is out of scope for a bugfix task.
- The discussion review subsystem's auto-pushed-back-only / PUSH-BACK-on-auto
  rule (relevant to how #276 surfaced) is NOT touched. That subsystem
  produced the stale `blocked_reason:`; we are fixing the symptom in `_status`,
  not redesigning auto-mode review-gap handling.
- `millpy-implement.py`'s own "Missing config" error message is NOT changed.
  The fix is upstream (catch the missing wiki in mill-go before the implementer
  ever launches); changing the implementer's own message is a different bug.
- No SKILL.md changes outside mill-go. Mill-plan/mill-merge etc. do not have
  per-batch loops where wiki corruption between rounds would matter; they
  already sync-pull at entry.

## Decisions

### D1: Wiki health-check is per-batch, lives in `_wiki.py`, halts on failure

- Decision: Add `_wiki.health_check(wiki_path)` raising `WikiHealthError` on
  missing `config.yaml`. mill-go SKILL.md calls it via inline `python -c "..."`
  as the FIRST sub-step of every Execute loop iteration (before "1.
  Implement"). It also runs once at the start of the Holistic code review
  loop, since holistic review fires the same `millpy-review-code.py` that
  loads wiki config. On `WikiHealthError`, mill-go halts the entire run with
  the message `wiki appears missing or corrupted at <path> — re-run mill-setup
  to restore it`, without writing a `blocked` state. The builder lock IS
  released before halt (otherwise the next mill-go would self-deadlock).
- Rationale: Wiki corruption is a system-level failure that will affect every
  subsequent batch; halting forces operator attention at the right layer.
  Block-batch would silently move on. The inline `python -c "..."` approach
  keeps the orchestrator lean — no new CLI to maintain. The helper is reusable
  from other orchestrators (mill-plan etc.) without a SKILL.md change there.
- Rejected:
  - **New CLI `millpy-wiki-healthcheck.py`** — unjustified new entry point;
    one-liner health check doesn't need a full CLI with PYTHONPATH plumbing,
    JSON output, etc.
  - **Push the check into `millpy-implement.py`** — too late: the implementer
    is already a heavy subprocess by the time it loads config. The Builder is
    the right layer to fail fast.
  - **Auto-call mill-setup to repair** — risky: mill-setup writes to the
    operator's filesystem (junctions, hardlinks). A self-healing implementer
    chain could mask data loss. Operator opt-in is correct.

### D2: Junction idempotency in `_setup.create_hub_links`, mirroring hardlinks

- Decision: In the junctions loop of `_setup.create_hub_links`, before calling
  `_junction.create`, check:
  1. If `link_path` doesn't exist (and isn't a broken symlink) → first-run,
     create directly. Append to `created_junctions`.
  2. If `link_path` exists and is a junction/symlink → call
     `_junction.points_to(link_path, target)`. If True → idempotent skip (do
     NOT append to `created_junctions`); if False → drift case, call
     `_junction.remove(link_path)` then `_junction.create(target, link_path)`,
     append to `created_junctions`.
  3. If `link_path` exists but is a regular file or directory → call
     `_junction.remove(link_path)`; this raises the existing
     `ValueError(f"{link_path} is not a junction or symlink — refusing to
     remove")`. Drift detection without data loss.

  Add `_junction.points_to(link_path: Path, target: Path) -> bool` helper.
  Implementation: returns False if `link_path` is not a junction/symlink (uses
  the same Windows reparse-point detection as `_junction.remove`); otherwise
  compares `link_path.resolve()` with `target.resolve()` (string equality on
  the canonical form — both must already exist for `resolve()` to canonicalise,
  which is fine: the target must exist for the original junction creation to
  have succeeded).

  Factor the "is junction or symlink on Windows / POSIX" detection logic out
  of `_junction.remove` into a private `_is_junction_or_symlink(link_path)`
  helper, used by both `remove` and `points_to`. This is a clean refactor
  with no behaviour change for `remove`.

- Rationale: The same file (`_setup.py`) already has an inode-check idempotency
  pattern in the hardlinks block — the junctions block becomes symmetric.
  `_junction.create`'s strict "raise on already-exists" contract is preserved,
  so other callers (e.g. test fixtures) keep the existing safety. The
  remove-then-create drift handler matches the hardlinks `<name>.bak`+recreate
  logic in spirit.
- Rejected:
  - **Push idempotency into `_junction.create`** — changes a documented
    contract; would silently mask cases where the caller assumed the link
    didn't exist (e.g. test fixtures). Caller-side idempotency is more honest.
  - **Add `_junction.create_or_replace` wrapper** — API surface growth for one
    caller. `_setup.create_hub_links` is the only place that needs idempotent
    creation; inline it there.

### D3: `append_phase` clears stale `blocked_reason:` on non-blocked transitions

- Decision: `_status.append_phase(status_path, phase, timestamp)` is modified
  so that, when `phase != "blocked"`, the helper removes any existing
  `blocked_reason:` row from the top YAML block as part of the same write.
  When `phase == "blocked"`, `blocked_reason:` is left untouched — callers
  that want to set blocked normally use `set_blocked` (which writes
  `blocked_reason:`), but a direct `append_phase(_, "blocked", _)` call
  shouldn't clobber a `blocked_reason:` that was just written by a prior
  call.
- Rationale: The issue (#276) itself recommends Option A. Principle: `phase:`
  is the canonical state; `blocked_reason:` is metadata that only has meaning
  while `phase: blocked`. Auto-clearing means callers don't need to remember
  to call a separate helper; eliminates the footgun. The "single read+write"
  comment in the existing `append_phase` docstring still holds — we extend
  the same loop that writes `phase:` to also delete `blocked_reason:` when
  applicable.
- Rejected:
  - **Explicit `_status.clear_blocked_reason(status_path)` helper** — forces
    callers (mill-plan resume, auto-recovery paths) to remember to call it.
    Every forgotten call regenerates the bug. Auto-clear in `append_phase` is
    centralised.

### D4: Batch structure — three sequential batches, one per bug

- Decision: The plan is three sequential batches (`01-wiki-health-check`,
  `02-setup-junction-idempotency`, `03-status-blocked-reason-cleanup`),
  ordered as filed in the wiki entry. Each batch is fully independent
  (different source files, different tests). No DAG branching needed; topo
  order is simply file order.
- Rationale: Clean isolation per bug; per-batch review surface stays small
  (each touches one helper + one test file + at most one SKILL.md). Failure
  to land any one batch doesn't block the others. The mill-go round cost
  per batch is small relative to the implementer cost, so 3 batches vs 1 is
  not a meaningful slowdown.
- Rejected:
  - **Single batch — all three together** — larger diff per review round,
    bigger blast radius if any one fix needs revision.
  - **Two batches (combine #274+#276 as data-layer fixes; keep mill-go alone)**
    — no shared code between `_setup.py` and `_status.py`; combining adds
    review burden with no architectural benefit.

## Technical context

**Repo layout (relevant files):**

- `plugins/mill/scripts/_wiki.py` — currently exposes `sync_pull`,
  `write_commit_push`, `wiki_lock`, `read_junctions`, `read_hardlinks`,
  `clone_or_init`. No health-check helper. `WikiSetupError` / `WikiPushError`
  / `LockBusy` are the existing exception classes (lines 130, 141, 152).
- `plugins/mill/scripts/_junction.py` — exposes `create`, `remove`,
  `resolve_target`, `has_slug_token`, `strip_all_in_worktree`. `remove()`
  contains the Windows reparse-point detection logic (lines 165–192) and the
  POSIX symlink branch (lines 193–200). That logic is what `points_to` needs
  to reuse.
- `plugins/mill/scripts/_setup.py` — single function `create_hub_links`. The
  junctions loop is lines 91–106; the hardlinks loop is lines 110–152. The
  hardlinks loop is the model for what the junctions loop should look like.
- `plugins/mill/scripts/_status.py` — `append_phase` is lines 271–331;
  `set_blocked` is lines 193–268. Both helpers use the same `_split_fences`
  + `_YAML_FENCE` / `_TIMELINE_FENCE` infrastructure. The pattern for
  removing a row from the YAML block (delete a line by index) is
  straightforward; `set_blocked` already inserts/rewrites
  `blocked_reason:` in-place — the inverse (delete) follows the same shape.
- `plugins/mill/skills/mill-go/SKILL.md` — the Execute loop starts at line 82.
  The new health-check sub-step lives at the very top of each iteration,
  before "### 1. Implement". The Holistic loop starts at line 232; the same
  check fits at the top of each round.

**Mill-go SKILL.md cache-form invocation pattern** (already standard, see
CLAUDE.md `Conventions worth carrying`):

```bash
PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import _paths, _wiki
wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
_wiki.health_check(wiki_path)
"
```

If the inline Python exits non-zero, the Bash tool surfaces the stderr line,
and mill-go halts. No new shell-side error handling needed — the existing
Bash exit-code semantics carry the failure.

**`Path.resolve()` semantics on Windows junctions** — junctions are reparse
points; `Path.resolve()` follows them and returns the canonical path of the
target. `Path.exists()` returns True on a live junction. `Path.is_symlink()`
returns False for NTFS junctions (they are not OS-level symlinks). The
detection logic in `_junction.remove` (the `0x400` reparse-point bit on
`os.lstat().st_file_attributes`, or `os.path.isjunction` on 3.12+) is the
correct way to detect a junction; mirror it in `points_to`.

**Existing tests for context:**

- `plugins/mill/unit_tests/test-wiki.py` — already covers `sync_pull`,
  `wiki_lock`, etc. Add a new test function or two for `health_check`.
- `plugins/mill/unit_tests/test-setup-hub-links.py` — already covers
  `test_token_scope_filter_with_slug` (which creates `.wiki` and
  `.portals` junctions), `test_hardlink_inode_skip_idempotent`,
  `test_hardlink_inode_mismatch_backup_and_recreate`. New tests
  symmetric-to-hardlinks: `test_junction_idempotent_skip_on_correct_target`
  and `test_junction_recreated_on_wrong_target`.
- `plugins/mill/unit_tests/test-status.py` — already covers `set_blocked`
  happy path, blocked_reason insert-after-phase, blocked_reason rewrite-in-
  place, `append_phase` quoting. New tests:
  `test_append_phase_clears_blocked_reason_on_non_blocked_phase`,
  `test_append_phase_preserves_blocked_reason_on_blocked_phase`.

**Run all unit tests after each batch:**

```bash
PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/run-all.py"
```

The plan should pin per-batch verify commands to the relevant test files plus
the full suite.

## Constraints

`CONSTRAINTS.md` is not present at the hub root (verified — file does not
exist). Project conventions from CLAUDE.md that apply here:

- **Plugin scripts reference `${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths.**
  The new health-check inline `python -c "..."` block in mill-go SKILL.md
  uses the same cache-form invocation pattern as every other mill-go shell
  block. Already shown above.
- **`_wiki.write_commit_push` for wiki mutations.** Not relevant — no wiki
  mutation in any of the three fixes.
- **Junctions are IDE/terminal convenience only.** The health check reads
  `config.yaml` via `_paths.resolve_wiki_path` → real wiki path, not via the
  `.wiki` junction. Already enforced by the helper layer.
- **Per-card commits go through the git-commit skill** (which runs lint +
  codeguide-update per commit). Each unit-test addition + helper edit gets
  its own commit per the existing convention.
- **No emojis in code or generated files.** Per `mill-conversation`.
- **Plugin scripts: flat module layout, no submodules.** Helpers stay in
  `plugins/mill/scripts/_*.py`. No new sub-packages.
- **`SystemExit` over `sys.exit(...)` in helper code; CLIs may use
  `sys.exit`.** `_wiki.health_check` is a library helper — raise the typed
  `WikiHealthError` exception, do NOT call `sys.exit`. The mill-go SKILL.md
  inline `python -c` block catches `WikiHealthError`, prints a clean
  one-liner to stderr, and exits non-zero via `raise SystemExit(1)`.

## Testing

**Test framework:** Per `mill:testing` and project convention, unit tests live
in `plugins/mill/unit_tests/test-<name>.py` and use `tempfile`-based fixtures.
No real LLM / git / file-system-of-record dependencies. Run via the
language-native runner (`python plugins/mill/unit_tests/run-all.py`) — not
pytest.

### Batch 1: wiki health-check (#273)

Tests in `plugins/mill/unit_tests/test-wiki.py` (extend existing file):

- `test_health_check_passes_when_config_present` — fixture: `tempfile`
  wiki dir with a valid `config.yaml`. `_wiki.health_check(wiki_path)`
  must return None and not raise.
- `test_health_check_raises_when_config_missing` — fixture: `tempfile` wiki
  dir without `config.yaml`. `_wiki.health_check(wiki_path)` must raise
  `WikiHealthError` whose message names the missing path.
- `test_health_check_raises_when_wiki_dir_missing` — fixture: a
  non-existent path. `_wiki.health_check(<bad-path>)` must raise
  `WikiHealthError`. Same code path as missing-config (config absent), but
  guards against future divergence.

No SKILL-level test — the orchestrator-side wiring is exercised by manual
smoke (operator runs mill-go after `rm wiki/config.yaml`; sees the new
error). Documenting that in the plan's batch verify step is sufficient.

### Batch 2: junction idempotency (#274)

Tests in `plugins/mill/unit_tests/test-setup-hub-links.py` (extend existing
file):

- `test_junction_idempotent_skip_on_correct_target` — fixture: full wiki
  with `_FULL_CFG`, target_root pre-seeded by a first call to
  `create_hub_links`. Second call must return empty `junctions` list (or
  not double-count); existing junctions still resolve to the original target.
  Asserts the second call did NOT raise and did NOT modify the junction.
- `test_junction_recreated_on_wrong_target` — fixture: target_root has a
  pre-existing `.wiki` junction pointing at a different (decoy) directory.
  Call `create_hub_links`. The junction must now point at the correct
  `wiki_path`, and the decoy must still exist (we removed only the link,
  not the link's old target). `result["junctions"]` must list `.wiki`.

Additionally: `test_junction_refuses_to_replace_real_directory` — fixture:
`.wiki` is a real directory (not a junction) inside `target_root` containing
a sentinel file. `create_hub_links` must raise `ValueError` (propagated from
`_junction.remove`), and the real directory plus its sentinel must be
preserved on disk afterwards. This is the safety regression guard.

### Batch 3: blocked_reason cleanup (#276)

Tests in `plugins/mill/unit_tests/test-status.py` (extend existing file):

- `test_append_phase_clears_blocked_reason_on_non_blocked_phase` — fixture:
  fresh `status.md`; call `set_blocked(sp, "test reason", timestamp=ts1)`;
  call `append_phase(sp, "planning", ts2)`. Assert: top YAML block has
  `phase: planning` AND NO `blocked_reason:` row.
- `test_append_phase_preserves_blocked_reason_when_new_phase_is_blocked` —
  fixture: fresh `status.md`; call `set_blocked(sp, "first reason",
  timestamp=ts1)`; call `append_phase(sp, "blocked", ts2)`. Assert: top YAML
  block has `phase: blocked` AND `blocked_reason: first reason` (unchanged).
- `test_append_phase_clears_blocked_reason_only_when_present` — fixture:
  fresh `status.md` (no `blocked_reason:`); call `append_phase(sp,
  "discussed", ts)`. Assert: top YAML block has `phase: discussed`, no
  `blocked_reason:` row introduced, no other rows mutated. Guards against
  the cleanup logic accidentally writing an empty row.

### Cross-cutting: all unit tests must pass per batch

Per-batch verify command (in plan):

```bash
PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/run-all.py"
```

Each batch's verify section must pin BOTH the targeted test file (fast feedback
while iterating) and the full suite (regression guard).

## Q&A log

- **Q:** How to structure plan batches? 1) Three sequential batches, one per bug 2) One batch all three 3) Two batches (combine #274+#276; mill-go alone). **A:** [auto-pick] 1) Three sequential batches. **Why:** Clean isolation; each bug touches a different file and a different test file; per-batch review surface stays small; mill-go round cost is small relative to implementer cost.
- **Q:** For #273, where does the wiki health-check live? 1) Add `_wiki.health_check(wiki_path)` helper; mill-go SKILL.md invokes it via inline `python -c "..."` per batch 2) New CLI `millpy-wiki-healthcheck.py` 3) Push check into `millpy-implement.py`. **A:** [auto-pick] 1) `_wiki.health_check` helper + inline invocation. **Why:** Inline check keeps the orchestrator lean and surfaces the error before launching the heavy implementer subprocess; helper is reusable from other orchestrators (mill-plan, mill-merge); no new CLI overhead.
- **Q:** For #273, what is the failure mode on missing wiki? 1) Halt entire mill-go session with `wiki appears missing or corrupted at <path> — re-run mill-setup to restore it` 2) Block the batch and continue 3) Auto-call mill-setup to repair. **A:** [auto-pick] 1) Halt the session. **Why:** Wiki corruption is a system-level failure; the next batch will also fail. Halting forces operator to fix the root cause. Block-batch would silently move on; auto-repair could mask data loss.
- **Q:** For #273, does sync_pull also run per batch (not just Entry)? 1) No — sync_pull stays at Entry only; health check is enough 2) Yes — sync_pull every batch. **A:** [auto-pick] 1) Entry-only sync_pull. **Why:** sync_pull does a `git fetch` and would add real latency per batch. The reported bug is about missing-config detection, not upstream-config sync. Health check is the minimum sufficient fix.
- **Q:** For #274, where does the idempotency check live? 1) In `_setup.create_hub_links` — mirror the inode-check pattern from hardlinks 2) In `_junction.create` itself 3) Add a new `_junction.create_or_replace` wrapper. **A:** [auto-pick] 1) In `_setup.create_hub_links`. **Why:** Matches the existing same-file convention. `_junction.create`'s documented strict-raise contract is preserved. Avoids API surface growth from a wrapper that has one caller.
- **Q:** For #274, on junction-already-exists with wrong target? 1) Remove the stale junction and recreate 2) Raise ValueError (strict) 3) Warn and leave the stale junction. **A:** [auto-pick] 1) Remove and recreate. **Why:** Matches the hardlinks backup-and-recreate logic in spirit ("drift" case → heal it). Operator-friendly — re-runs of mill-setup heal drift. Strict-raise on drift is annoying when the operator's intent is "make state correct"; warn-and-leave hides the drift.
- **Q:** For #274, on `.wiki` being a real directory (not a junction)? 1) Refuse with the existing `_junction.remove` ValueError 2) Back up and recreate 3) Overwrite silently. **A:** [auto-pick] 1) Refuse via `_junction.remove`'s existing guard. **Why:** The existing safety logic in `_junction.remove` prevents accidentally wiping a real directory. Back-up-and-recreate of a real directory could corrupt operator state — better to surface and let the operator decide.
- **Q:** For #276, approach? 1) Auto-clear `blocked_reason:` in `append_phase` when new phase != "blocked" 2) Add explicit `_status.clear_blocked_reason` helper that callers invoke. **A:** [auto-pick] 1) Auto-clear in `append_phase`. **Why:** Issue's recommendation. Principle: `phase:` is canonical; metadata follows phase. Callers don't have to remember to call a separate helper; eliminates the footgun for future orchestrators that resume from blocked.
- **Q:** For #276, does `set_blocked` behaviour change? 1) Leave `set_blocked` unchanged 2) Refactor `set_blocked` to call `append_phase` internally. **A:** [auto-pick] 1) Leave unchanged. **Why:** `set_blocked` already correctly writes both `phase: blocked` and `blocked_reason:`. The two helpers have different semantics; unifying them is a refactor, not a bugfix, and out of scope.
- **Q:** For #276, when `append_phase` is called with `phase="blocked"`? 1) Preserve any existing `blocked_reason:` 2) Clear it. **A:** [auto-pick] 1) Preserve. **Why:** A direct `append_phase(_, "blocked", _)` after `set_blocked` shouldn't clobber the reason that was just written. Clearing on transitions INTO blocked is the wrong direction (mathematically dual to what we want).
- **Q:** Tests for #273 — where? 1) Extend `test-wiki.py` with `health_check` cases 2) Skip — orchestration only. **A:** [auto-pick] 1) Extend `test-wiki.py`. **Why:** Helper deserves unit coverage; existing file is the natural home.
- **Q:** Tests for #274 — where? 1) Extend `test-setup-hub-links.py` with junction-already-correct, junction-wrong-target, and refuse-real-directory cases 2) New file 3) Skip. **A:** [auto-pick] 1) Extend `test-setup-hub-links.py`. **Why:** Hardlink idempotency is already tested there; adding junction-idempotency cases is the symmetric extension. Three test functions sit naturally beside the existing hardlinks ones.
- **Q:** Tests for #276 — where? 1) Extend `test-status.py` with `append_phase`-clears-blocked_reason, `append_phase`-to-blocked-preserves, and clears-only-when-present cases 2) New file 3) Skip. **A:** [auto-pick] 1) Extend `test-status.py`. **Why:** `test-status.py` already has the `set_blocked` and `append_phase` test sections; the new tests slot in next to them.
