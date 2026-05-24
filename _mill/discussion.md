# Discussion: Adopt V3 wiki module in V2 scripts

```yaml
task: Adopt V3 wiki module in V2 scripts
slug: wiki-v3-adoption
status: discussing
parent: main
```

## Problem

V2 wiki access is fragmented across `_wiki.py` (advisory lockfile + `git add`/`commit`/`push` helper + `read_junctions`/`read_hardlinks` + `clone_or_init`), `_tasks_md.py` (regex parser + claim/append/remove helpers), `_sidebar.py` (regen-from-Home), and one-off direct `git -C <wiki>` calls in `millpy-wikipush.py` and `millpy-migrate-config.py`. The V3 wiki module shipped (`plugins/mill/scripts/wiki/`: daemon + TinyDB store + CAS writes over JSON/socket) but no V2 caller uses it.

The V3 module as merged is also incomplete for adoption:

- Its generic `OP_READ` / `OP_WRITE` lets clients write `Home.md` raw — but `_handle_write` then re-renders `Home.md` from TinyDB and atomic-writes over the client's content. That makes the raw-write path lossy and incoherent.
- `_render.py` hardcodes `group_order = [None, "A", "B", "C", "D", "Z"]` and orders ungrouped tasks first.
- `_parse.py` silently strips `[s]` and `[abandoned]` markers to `None`.
- `Store.upsert_task` numbers IDs from 1 (`max_id + 1` with `max_id = 0`).
- The module still pulls config-readers (`read_junctions`, `read_hardlinks`) from a legacy `wiki/config.yaml`, which is being purged from the repo.

This task reshapes V3 into the only wiki API, migrates every V2 call site, removes the V2 wiki layer, and purges all `wiki/config.yaml` references from the codebase.

**Why now:** V3 daemon + TinyDB landed in commits `bfdaf3a` (daemon) and `a172c64` (TinyDB migration). The branch is unblocked. Every other mill task currently waits on the V2 advisory lock for serial wiki writes; CAS over the daemon socket is faster and removes the cross-process file-lock complexity.

## Scope

**In:**

- Rework V3 daemon protocol: replace `OP_READ` / `OP_WRITE` with structured task ops (`OP_UPSERT_TASK`, `OP_SET_PHASE`, `OP_REMOVE_TASK`, `OP_GET_TASK`, `OP_LIST_TASKS_BRIEF`, `OP_LIST_TASKS_FULL`, `OP_HEALTH`). `OP_HEALTH` handler returns `{ok: true}` immediately with no DB or git access — used by `wiki._client.health_check`. Bump `PROTOCOL_VERSION` from 1 → 2 so stale daemons get killed and respawned.
- Update `wiki/_client.py` Python wrapper: drop `read` / `write_commit_push`; add `upsert_task(slug, *, title=None, brief=None, body=None, group=None, status=None)`, `set_phase(id_or_slug, phase)`, `remove_task(id_or_slug)`, `get_task(id_or_slug)`, `list_tasks_brief()`, `list_tasks_full()`, `health_check()`. Bump `CAS_RETRIES` from 3 to 5 (matches the existing `test-wiki-e2e.py` retry literal — see decision `cas-retry-count`). Rewrite `health_check` to send `OP_HEALTH` instead of `OP_READ` (the latter is being removed; see decision `structured-ops-over-socket`).
- Update `wiki/_server.py`: drop `_handle_read` / `_handle_write`; add one handler per structured op. Each mutating handler does TinyDB op → `render(all_tasks)` → `atomic_write` each rendered file → `commit_push` (with one rebase retry, as today).
- Update `wiki/_store.py`:
  - First task assigned `id = 0` (when DB empty), then `max + 1`.
  - Methods accept `int | str` identifier (slug or id): `get_task`, `remove_task`, `set_phase`.
  - `list_tasks_brief()` returns dicts with keys `{id, slug, group, brief, status}` (no `body`, no `title`).
  - `list_tasks_full()` returns full dicts.
- Update `wiki/_render.py`:
  - Render groups in alphabetical order `A`, `B`, `C`, …, `Z`, then ungrouped (`group is None`) last.
  - Skip empty groups entirely (no `# Layer X` header emitted when no tasks belong to that group).
  - Accept any group letter A–Z, not the current hardcoded subset.
  - Emit `[abandoned]` as a first-class status marker.
  - Never emit `[s]`.
  - Continue producing `Home.md`, `_Sidebar.md`, and `proposal-{slug}.md` (one per task with non-empty `body`).
- Update `wiki/_parse.py`:
  - Drop `s` from the recognised status set (parsed to `None` if encountered).
  - Keep `abandoned` as a first-class status.
  - Used only by the migration script; not invoked by the daemon at runtime.
- Add `millpy-wiki-migrate.py` one-shot migration script:
  - Argparse: `--dry-run` (print parsed state, no commits), default = commit.
  - Backs up current `<wiki>/Home.md` to `<wiki>/Home.md.pre-v3.bak`.
  - Parses current `Home.md` with an extended parser tolerant of V2 free-form content (parenthetical layer headers, info-only `##` sections, multi-paragraph briefs, varied title formats). Info-only sections (no `[slug]` line) and stray content are dropped (the backup retains them).
  - Briefs are captured as their original multi-line text, then collapsed to one paragraph for the `brief` field. Existing `proposal-{slug}.md` content (if any) is read and stored in the task's `body` field.
  - Seeds `tasks.json` via the running daemon (sends `OP_UPSERT_TASK` per parsed task).
  - Daemon's first render produces the V3-format `Home.md`, `_Sidebar.md`, and `proposal-{slug}.md` files; existing on-disk versions are overwritten.
  - Single commit: `Home.md.pre-v3.bak`, `tasks.json`, regenerated `Home.md`, `_Sidebar.md`, and `proposal-*.md`.
- Port every V2 wiki call site to the new structured API:
  - `millpy-add.py`: replace `wiki_lock` + `_tasks_md.append_entry` + `_wiki.write_commit_push` with `wiki.upsert_task(slug, title=, brief=, body=, group=)`. (No `status` kwarg in the normal add flow — new tasks default to `None` / unmarked; phase transitions go through `set_phase` later.)
  - `millpy-cleanup.py`: replace `wiki_lock` + `_tasks_md.set_phase` + `_wiki.write_commit_push` with `wiki.set_phase(slug_or_id, phase)`. Replace any `_tasks_md.remove_entry` with `wiki.remove_task`. Replace `Home.md` reads with `wiki.list_tasks_brief()`.
  - `millpy-claim.py`: drop `_wiki.sync_pull` (daemon lazy-refreshes inside each op). Replace the direct `wiki_path / "config.yaml"` read at line 68 with the `_config.load_config` path. Replace Home.md parsing with `wiki.list_tasks_brief()` / `wiki.get_task(slug)` for the claim flow.
  - `millpy-fold.py`: replace `wiki_lock` + body amendment + `_wiki.write_commit_push` with `wiki.get_task` → mutate locally → `wiki.upsert_task`.
  - `millpy-spawn.py`: replace `_wiki.sync_pull` (drop entirely) and the eventual `_spawn_core.claim_in_wiki` call (already switching below).
  - `_spawn_core.claim_in_wiki`: replace with `wiki.set_phase(slug, "active")`.
  - `_spawn_core.groom_and_claim_merge`: replace the read-modify-write window with N × `wiki.remove_task(slug)` + `wiki.upsert_task(merged_slug, ..., body=..., has_proposal=...)` + `wiki.set_phase(merged_slug, "active")`. No advisory lock; CAS conflicts surface as `WikiConflictError` and the caller retries up to `wiki._client.CAS_RETRIES` attempts (see decision `cas-retry-count` below — `CAS_RETRIES` is bumped from 3 to 5 in this task so the constant matches the existing `test-wiki-e2e.py` integration-test pattern; `groom_and_claim_merge` uses the constant, not a local literal).
- Move `read_junctions` / `read_hardlinks` from `_wiki.py` to `_junction.py`. Strip the `wiki/config.yaml` fallback path — `mill-config.yaml` (hub root) is the only source. Update the two call sites (`_setup.py:85,86` and `millpy-cleanup.py:636`) for the new import path.
- Move `clone_or_init` from `_wiki.py` into `_setup.py` (its sole caller).
- Delete `_wiki.py`, `_tasks_md.py`, `_sidebar.py` outright (no shim, no deprecation). The `Task` dataclass and `LOCKED_FOLD_PHASES` constant move into `wiki/__init__.py`.
- Strip the `wiki/config.yaml` fallback from `_config.py:load_config` (lines 179, 188, 198–202). Only `mill-config.yaml` is consulted; missing → clean error.
- Delete `millpy-migrate-config.py` and its integration test `test-migration.py`.
- Update fixtures across `test-cleanup.py`, `test-merge.py`, `test-millpy-implement.py`, `test-review-discussion.py`, `test-config.py` to stop creating `wiki/config.yaml`. Where the fixture's purpose was to exercise the fallback path, delete the test.
- Update skill docs `plugins/mill/skills/mill-claim/SKILL.md` and `plugins/mill/skills/mill-finalize/SKILL.md` to remove `wiki/config.yaml` references.
- Update prompt templates `plugins/mill/templates/review-plan-holistic.md` and `review-plan-batch.md` to drop the `wiki/config.yaml` BLOCKING rule (no longer applicable).
- Add V3 tests:
  - Unit tests for new `Store` methods (id assignment from 0, identifier-by-int-or-str, brief vs full list).
  - Unit tests for new protocol ops in `_server.py` (each handler, plus rejection of removed `OP_READ` / `OP_WRITE`).
  - Unit tests for `_render.py` (group order A→Z then None, empty-group skip, all letters accepted, `[s]` never emitted, `[abandoned]` emitted, proposal-{slug}.md gating on `body`).
  - Unit tests for `_parse.py` (the extended parser used by the migration script — covers parenthetical layer headers, info-only `##` sections, multi-paragraph briefs; `[s]` parsed to None, `[abandoned]` preserved).
  - Integration test for `millpy-wiki-migrate.py` (dry-run + commit; uses a fixture mirroring current `Home.md`).
  - Update existing `test-wiki-e2e.py` to use structured ops.

**Out:**

- `millpy-wikipush.py` rewrite — direct git subprocess stays, no V3 API equivalent. It pushes whatever the user dirtied manually in the wiki working tree and resolves conflicts on the fly; that flow has no place in a daemon-backed structured-write model. **In-scope sliver:** remove the `_wiki` import and the `wiki_lock` / `LockBusy` call sites (lines 32, 104, 111, 113) so the script keeps working after `_wiki.py` is deleted. The push logic itself is untouched.
- Jinja or external template support for `_render.py` — current Python function is editable in place; defer until proven necessary.
- Migration of `[s]` markers in the corpus — user has stopped using `[s]`; no current Home.md entry carries it.
- Backwards-compat shim for `wiki/config.yaml` — purged outright. If a user has a stale `wiki/config.yaml` after this lands, mill-setup should warn and refuse to start until removed (covered by the existing `[config] stale wiki/config.yaml detected` message, which can stay in mill-setup but is removed from runtime config-load).
- Advisory locking — CAS handles concurrency; no `wiki_lock` replacement.
- Cross-host conflict resolution beyond the existing one-rebase-retry — the V3 `commit_push` already covers this.

## Decisions

### tinydb-source-of-truth

- Decision: `tasks.json` (TinyDB) is the authoritative store of task state. `Home.md`, `_Sidebar.md`, and `proposal-{slug}.md` are cosmetic, daemon-generated artifacts. Clients never write them directly.
- Rationale: Eliminates the lossy parse → render round-trip in V3's current `_handle_write`. Makes the render layer editable without breaking client writes.
- Rejected: (a) clients write raw `Home.md` + daemon parses + renders (V3 as-shipped — already proven lossy on free-form content); (b) keep `_tasks_md.py` as a parallel parser (two sources of truth).

### structured-ops-over-socket

- Decision: Daemon exposes structured task ops over the existing JSON/socket protocol. Generic `OP_READ` / `OP_WRITE` removed.
- Rationale: V2 callers do read-modify-write on Home.md text; that's an anti-pattern once TinyDB owns state. Structured ops are a single round-trip each, idiomatic for the daemon, and the protocol stays one wire format. No bypass of the daemon.
- Rejected: keep `OP_READ` / `OP_WRITE` for general inspection — would have no Python caller after this task lands (proposals are read via `get_task(slug).body`, Home.md via `list_tasks_brief()`); dead weight.

### protocol-version-bump

- Decision: `PROTOCOL_VERSION` bumps from 1 → 2. Old daemons get killed and respawned by `_ensure_daemon`'s existing version-mismatch path.
- Rationale: The op-set is breaking. The protocol-version mechanism already handles this exact case.
- Rejected: dual-support both protocols — complicates server with no benefit; this is a one-shot migration.

### no-advisory-lock

- Decision: Drop `wiki_lock` entirely. The daemon serialises writes within a host (single-threaded request handler); CAS handles cross-host conflicts.
- Rationale: User confirmed only the daemon reads and writes wiki state. The advisory lockfile (`.mill-lock`) was V2's way to serialise across processes on one host — superseded by routing every write through one process.
- Rejected: keep advisory lock for cross-host throttling — CAS already detects conflicts and surfaces them as `WikiConflictError`; pre-blocking via lock would only add latency.

### id-and-slug-dual-identifier

- Decision: Every task has both a unique integer `id` (starting at 0, auto-assigned on upsert) and a unique `slug` (caller-supplied). All fetch / mutate ops accept either: `get_task(id_or_slug: int | str)`, `set_phase(id_or_slug, phase)`, `remove_task(id_or_slug)`. `upsert_task` is keyed by slug (new tasks have no id yet; existing slug → update + preserve id).
- Rationale: User wants short numeric handles for human/CLI use, slugs for everything code-facing.
- Rejected: slug-only — loses the short numeric handle the user wants; id-only — slugs are already in use everywhere.

### render-group-order

- Decision: `_render.py` orders groups alphabetically `A` through `Z`, then ungrouped (`group is None`) last. Empty groups produce no `# Layer X` header and no content. All letters A–Z accepted.
- Rationale: User-specified.
- Rejected: ungrouped-first (V3's current shape); fixed `[A, B, C, D, Z]` set (V3 as-shipped — rejects unrecognised letters).

### drop-s-keep-abandoned

- Decision: `[s]` (spawn-ready) status removed from V3 entirely — parser ignores it, render never emits it. `[abandoned]` is first-class: `mill-cleanup` flips abandoned tasks back to it.
- Rationale: User confirmed `[s]` is no longer used. `[abandoned]` is in active use by mill-cleanup's existing cleanup flow.
- Rejected: keep both — `[s]` is dead code; preserving it adds parser/render surface for zero callers.

### one-shot-migration

- Decision: `millpy-wiki-migrate.py` runs once per wiki to seed `tasks.json` from current `Home.md`, with `--dry-run` mode and a backup at `Home.md.pre-v3.bak`. After this runs, the daemon owns the state.
- Rationale: User has a populated `Home.md` that must transition without loss. Backup is the recovery path for anything the parser drops (info-only sections, free-form notes).
- Rejected: hand-write `tasks.json` — too error-prone for ~20 tasks with proposals; rolling parse on first daemon write — corrupts content silently if parse misbehaves.

### delete-v2-wiki-layer

- Decision: `_wiki.py`, `_tasks_md.py`, `_sidebar.py` deleted in this task. No shim, no deprecation cycle.
- Rationale: One squashed task; once the call-site migration is complete, the modules have no callers and adding a shim layer would just defer the cleanup.
- Rejected: deprecation cycle — would block the `wiki/config.yaml` purge and the `LOCKED_FOLD_PHASES` move to `wiki/__init__.py`.

### purge-wiki-config-yaml

- Decision: All `wiki/config.yaml` references removed from runtime code, docs, templates, and fixtures. `mill-config.yaml` (hub root) is the only config source. `millpy-migrate-config.py` is deleted with its test.
- Rationale: User-mandated. The wiki module is standalone; config-reader paths that touched `wiki/config.yaml` were a leftover from the pre-`mill-config.yaml` era.
- Rejected: keep the fallback for one release — no upgrade path uses it; the migration was done long ago.

### keep-wikipush-direct

- Decision: `millpy-wikipush.py` stays on direct `git -C <wiki>` subprocess calls. Minimal sliver in scope: drop the `_wiki` import and the `wiki_lock` / `LockBusy` call sites so the script keeps working after `_wiki.py` is deleted.
- Rationale: It commits whatever the user manually edited in the wiki working tree, including non-task content (raw markdown pages, README, etc.). V3's structured API has no equivalent and shouldn't grow one — that's a different concern than steady-state task-state writes. But the script still imports `_wiki` for its advisory lock, so deleting `_wiki.py` breaks it at import; that one-import cleanup is unavoidable here.
- Rejected: a `wiki.push_user_edits()` API — would re-introduce the generic file-write surface we just deleted. Leaving `_wiki.py` shimmed for this one script — keeps a 600-line module alive for one import; cleaner to remove the import and let the bare push helper run unwrapped.

### cas-retry-count

- Decision: Bump `wiki._client.CAS_RETRIES` from 3 to 5. `_spawn_core.groom_and_claim_merge` (and any other CAS-loop call site) uses `CAS_RETRIES`, not a local literal.
- Rationale: The integration test `test-wiki-e2e.py` already retries 5 times via a hard-coded local `max_retries = 5`. Two values for the same concept invites drift. Pick one; bump the constant; have the test reference it.
- Rejected: keep `CAS_RETRIES = 3` and adjust the test down to 3 — the test's `5` was a deliberate over-spec for concurrent-write soak; 3 attempts is tight for two writers racing on the same file.

### upsert-task-status-param

- Decision: Public `wiki.upsert_task(slug, *, title=None, brief=None, body=None, group=None, status=None)` accepts an optional `status` kwarg. Normal callers (`millpy-add`, `millpy-fold`) leave it `None`; the migration script passes the parsed legacy status (`"active"`, `"abandoned"`, etc.) directly through the same public API.
- Rationale: The migration script needs to seed `[active]` / `[abandoned]` markers as part of the initial state. Adding the parameter to the public API is one line; doing it via a private `OP_UPSERT_TASK` dispatch with a different field set splits the contract.
- Rejected: separate `wiki.seed_task(...)` for migration — single-use API for a one-shot script; not worth the surface area.

### health-check-op-health

- Decision: Add an `OP_HEALTH` op to the protocol. The daemon's handler returns `{ok: true}` immediately (no DB or git access). `wiki._client.health_check` sends `OP_HEALTH` instead of the now-removed `OP_READ` with empty path.
- Rationale: `health_check` must survive the `OP_READ` removal. A dedicated lightweight op is cheaper than reusing `OP_LIST_TASKS_BRIEF` for liveness, and signals intent.
- Rejected: reuse `list_tasks_brief` for liveness — couples health-check latency to TinyDB read cost; semantically wrong.

## Technical context

**V3 module layout** (`plugins/mill/scripts/wiki/`):

- `__init__.py` — protocol constants (`PROTOCOL_VERSION`, `OP_*`, `FIELD_*`, `ERR_*`) and exception classes (`WikiError`, `WikiNotFoundError`, `WikiConflictError`, `WikiPushError`, `WikiProtocolError`, `WikiStartupError`, `WikiPathError`).
- `_client.py` — Python API + daemon auto-spawn (`_ensure_daemon`, `_spawn_server`, `_connect_send_recv`, `_kill_daemon`, `_is_stale`). Currently exposes `read`, `write_commit_push`, `health_check` — all three replaced by the new structured methods.
- `_server.py` — daemon. `WikiServer(DaemonBase)`. Currently dispatches `OP_READ` / `OP_WRITE` via `_handle_read` / `_handle_write`. Holds a `Store` and a `_last_pull` for lazy refresh (default 10s). Writes `.wiki-daemon.json` + `.wiki-daemon.log` (both gitignored — entries written by `_ensure_gitignore`).
- `_store.py` — TinyDB-backed `Store`. `set(rel_path, content)` parses Home.md and upserts tasks (this code becomes internal-only after the protocol change — migration script uses it). `get(rel_path)` for Home.md re-renders from TinyDB. `upsert_task`, `all_tasks`, `get_by_slug` already present.
- `_parse.py` — `parse_home_md(content) -> list[dict]`. Returns dicts with `{slug, title, group, brief, status}`. Strips `s`/`abandoned` to `None` (one of the bugs being fixed).
- `_render.py` — `render(tasks) -> dict[str, str]`. Hardcoded `group_order`; emits `Home.md`, `_Sidebar.md`, `proposal-{slug}.md`.
- `_sync.py` — git ops: `path_guard`, `atomic_write`, `pull`, `commit_push`. Stays as-is.
- `_daemon.py` — generic daemon base class. Stays as-is.

**TinyDB layout**: file at `<wiki>/tasks.json`. Schema per task:

```json
{
  "id": 0,
  "slug": "wiki-v3-adoption",
  "title": "Adopt V3 wiki module in V2 scripts",
  "group": null,
  "brief": "Replace all V2 _wiki.py call sites …",
  "body": "",
  "status": "active"
}
```

**V2 call sites to migrate** (from `grep _wiki\\.`):

| File | Lines | V2 call | V3 replacement |
|---|---|---|---|
| `millpy-add.py` | 169, 198 | `wiki_lock` + `write_commit_push` | `wiki.upsert_task` |
| `millpy-cleanup.py` | 603, 632, 636, 653 | `write_commit_push`, `sync_pull`, `read_junctions`, `wiki_lock` | `wiki.set_phase`/`remove_task`/`list_tasks_brief`; `read_junctions` moves to `_junction.py`; lock dropped |
| `millpy-claim.py` | 185, 68 | `sync_pull`; direct `wiki_path / "config.yaml"` read | drop sync_pull; route config read through `_config.load_config` |
| `millpy-migrate-config.py` | all | direct git calls | **delete file** |
| `millpy-fold.py` | 87, 144 | `wiki_lock` + `write_commit_push` | `get_task` + `upsert_task` |
| `millpy-wikipush.py` | 32, 104, 111, 113 | `import _wiki`, `wiki_lock`, `LockBusy` | drop `_wiki` import; remove the `wiki_lock` guard (replace with bare call to inner push helper); push logic stays on direct git subprocess |
| `millpy-spawn.py` | 128 | `sync_pull` | drop |
| `_spawn_core.py` | 488, 514, 636, 641 | `wiki_lock` + `write_commit_push` (groom_and_claim_merge + claim_in_wiki) | `wiki.remove_task` + `upsert_task` + `set_phase`; CAS retry loop |
| `_setup.py` | 85, 86 | `read_junctions`, `read_hardlinks` | new import: `_junction.read_junctions`/`read_hardlinks` |
| `_paths.py` | 125, 140, 407 | error-message text only | update text to drop `_wiki.write_commit_push` reference |
| `_junction.py` | 239 | docstring only | update reference |
| `_worktree.py` | 207 | docstring only | update reference |

**Migration script anatomy** (`millpy-wiki-migrate.py`):

1. Resolve `wiki_path` via `_paths.resolve_wiki_path(_paths.resolve_git_root())`.
2. Read current `<wiki>/Home.md`. Write to `<wiki>/Home.md.pre-v3.bak`.
3. Parse with the extended parser:
   - Recognise `# Layer ([A-Z])(?: .*)?` (parentheticals allowed but ignored).
   - Recognise `## (.+)` task headings followed by `[slug]` or `[[slug]](proposal-slug.md)` on the next line, optional `[phase]` marker. Multi-paragraph briefs captured verbatim until next heading.
   - Skip `##` headings whose next non-blank line isn't a `[slug]` line (info notes — backup retains them).
   - For each task with `[[slug]](proposal-slug.md)`, read `<wiki>/proposal-slug.md` and set the task's `body` to that file's content.
4. For each parsed task, call the public `wiki.upsert_task(slug, title=..., group=..., brief=..., body=..., status=...)` — the migration is the canonical consumer of the `status` kwarg added in decision `upsert-task-status-param`. No internal `_ensure_daemon` / `_connect_send_recv` bypass; same API as every other caller.
5. Daemon renders new `Home.md`, `_Sidebar.md`, `proposal-*.md` on each upsert (existing flow — render after every mutation). Final state on disk is V3-rendered.
6. Single commit covering `tasks.json`, `Home.md.pre-v3.bak`, `Home.md`, `_Sidebar.md`, all `proposal-*.md` files. Commit message: `wiki: migrate to V3 (TinyDB-backed)`.
7. `--dry-run` mode: stop after step 3, print parsed tasks to stdout, no commits.

**Constraints from CLAUDE.md:**

- `${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths in skill invocations.
- All path resolution through `_paths.py`.
- Junctions stripped before any recursive delete.
- `print()` / `_log()` output ASCII only (already followed in V3 code).
- Wiki module is standalone — no junction or hardlink awareness inside `wiki/`.

## Constraints

- **Wiki module standalone.** `wiki/` package must not import `_junction`, `_setup`, `_paths` (the latter exception: `_client` may use `Path` operations but does not call `_paths.resolve_wiki_path` — callers pass `wiki_path` in). No junction or hardlink awareness inside the V3 module.
- **No `wiki/config.yaml` references anywhere in shipping code, tests, fixtures, docs, or templates.** Any leftover after this task lands is a bug.
- **TinyDB JSON is source of truth.** `Home.md`, `_Sidebar.md`, `proposal-{slug}.md` are derived. The only on-disk write of these files is the daemon's render.
- **Protocol version 2** — bumping it triggers the existing `_ensure_daemon` kill-respawn path. No client code change beyond updating the constant.
- **No advisory lock.** `wiki_lock` and its `.mill-lock` file are gone. CAS retries (already implemented in `test-wiki-e2e.py`'s pattern: 5 attempts) handle cross-host conflicts.
- **`millpy-wiki-migrate.py` is one-shot and idempotent.** Running it twice on an already-migrated wiki produces a no-op (TinyDB already populated; daemon's render produces the same content; `commit_push` returns immediately on "nothing to commit"). Backup file overwritten on each run — fine; the first backup is the canonical recovery.
- **Render output stability.** Two consecutive `render(same_tasks)` calls must produce byte-identical files. Required for `commit_push`'s `git diff --cached --quiet` short-circuit to work.

## Testing

**`wiki/_store.py` unit tests** (`test-wiki-store.py` — extend existing):

- `upsert_task` on empty DB → first task has `id = 0`.
- `upsert_task` on non-empty DB → new task has `id = max(existing) + 1`.
- `upsert_task` with existing slug → updates fields, preserves `id`.
- `get_task(slug)` and `get_task(id)` return same record; miss returns `None`.
- `remove_task(slug)` and `remove_task(id)` both work; missing identifier returns silently.
- `set_phase(slug_or_id, phase)` updates status; invalid phase raises.
- `list_tasks_brief()` returns dicts with keys `{id, slug, group, brief, status}`, no `body`/`title`. (TDD candidate.)
- `list_tasks_full()` returns dicts with every field. (TDD candidate.)

**`wiki/_server.py` protocol tests** (`test-wiki-protocol.py` — extend existing):

- Each new `OP_*` dispatched to the correct handler; happy path returns `{ok: true, ...}`.
- Removed `OP_READ` / `OP_WRITE` → `{ok: false, error_type: "protocol_error", error: "unknown op"}`.
- Bad token → unauthorised response (existing behaviour preserved).
- Protocol version mismatch on connect → daemon respawned (existing behaviour preserved).

**`wiki/_render.py` tests** (`test-wiki-render.py` — extend existing):

- Group order `A → B → C → … → Z → None` (ungrouped last). (TDD candidate.)
- Empty group (no tasks with `group == "B"`) → no `# Layer B` header and no entries for B.
- All letters A–Z accepted (not restricted to `[A, B, C, D, Z]`).
- Status `s` never emitted regardless of input task's status field.
- Status `abandoned` emitted as `[abandoned]` marker.
- `proposal-{slug}.md` present in render output when task `body` non-empty; absent when body empty.
- Two consecutive renders of the same task list produce byte-identical output.

**`wiki/_parse.py` tests** (`test-wiki-parse.py` — new, or extend existing):

- Recognises `# Layer X` with parenthetical suffix (`# Layer D (isolated)`).
- Skips `##` headings whose next line isn't a `[slug]` line (info notes).
- Captures multi-paragraph briefs verbatim until next heading.
- `[s]` → `status = None`.
- `[abandoned]` → `status = "abandoned"`.
- Title with numeric prefix and group code (`## 30 (D) — Foo`) parsed without crash.

**Migration integration test** (`test-wiki-migrate.py` — new, lives in `integration_tests/`):

- Build a `.scratch/migrate-fixture/` wiki with a Home.md mirroring the current production shape (Layer D, Layer Z, ungrouped, an `## ⚠` info note, one `[active]` task, one `[abandoned]` task, two tasks with `[[slug]](proposal-slug.md)` links + matching `proposal-slug.md` files).
- Run `millpy-wiki-migrate.py --dry-run`: assert nothing committed, parsed tasks printed.
- Run `millpy-wiki-migrate.py`: assert `Home.md.pre-v3.bak` exists with original content; `tasks.json` populated; new `Home.md` is V3-rendered (groups A–Z + null last); commit present with expected message.
- Re-run: assert no second commit produced (idempotent).

**`test-wiki-e2e.py` integration test** (update existing):

- Replace the raw `_client.read` / `_client.write_commit_push("Home.md", ...)` scenarios with structured ops: `upsert_task`, `set_phase`, concurrent `set_phase` from two subprocesses (CAS conflict + retry pattern).

**Per-CLI smoke tests** (the existing `test-millpy-*.py` files — update):

- `test-millpy-add.py`: assert `wiki.upsert_task` called, `tasks.json` reflects new entry, daemon rendered `Home.md` includes it.
- `test-cleanup.py`: update fixtures to seed `tasks.json` directly (not `Home.md`); assert phase flips via `wiki.set_phase`.
- `test-claim.py`: similar — daemon-backed.
- `test-fold.py`: assert body amendment lands via `wiki.upsert_task`.
- `test-merge.py`: drop `wiki/config.yaml` fixture creation.
- `test-review-discussion.py`, `test-millpy-implement.py`: drop `wiki/config.yaml` fixture creation; use `mill-config.yaml` only.

**Tests deleted with the modules they cover:**

- Any existing `test-wiki.py` (V2 `_wiki.py` lock/write tests).
- Any existing `test-tasks-md.py` / `test-sidebar.py` (V2 helpers gone).
- `integration_tests/test-migration.py` (covers `millpy-migrate-config.py` — both deleted together).

**Tests for `_config.py`** (`test-config.py` — update):

- Delete the legacy-fallback test (`load_config — fallback to wiki/config.yaml`).
- Delete the fallback-precedence test.
- Update remaining tests to use only `mill-config.yaml`.

## Q&A log

- **Q:** Mechanical port vs design the adoption strategy? **A:** Strategy first — V3 takes over for V2 fully; backup current Home.md to allow recovery.
- **Q:** Should the V3 render layer be passthrough or canonical? **A:** Canonical — TinyDB is source of truth; Home.md/_Sidebar.md/proposal-*.md are cosmetic generated artifacts.
- **Q:** Template engine for the render layer? **A:** Keep the simple Python `_render.py` for now. Easy to modify in place. Defer Jinja or external templates until needed.
- **Q:** Replace wiki_lock with what? **A:** Nothing. Drop locking entirely. Only the daemon reads and writes; CAS handles cross-host.
- **Q:** Where do `read_junctions` / `read_hardlinks` live? **A:** Move to `_junction.py`. Drop the legacy `wiki/config.yaml` fallback. The wiki module is standalone — no junctions/hardlinks awareness inside `wiki/`.
- **Q:** Purge `wiki/config.yaml` entirely or keep fallback? **A:** Purge entirely from runtime code, docs, templates, and fixtures. Delete `millpy-migrate-config.py` and its test.
- **Q:** Generic `OP_READ` / `OP_WRITE` after structured ops added? **A:** Drop both. Proposals are read via `get_task(slug).body`; Home.md via `list_tasks_brief()`. No raw-file API.
- **Q:** Keep `[s]` and `[abandoned]` status markers? **A:** `[s]` gone (user has stopped using it). `[abandoned]` stays first-class; mill-cleanup flips abandoned tasks back to it.
- **Q:** Migration approach for current Home.md? **A:** One-shot script `millpy-wiki-migrate.py` with backup + dry-run mode.
- **Q:** Task identification — slug or numeric? **A:** Both. Every task has unique `id: int` (from 0) and `slug: str`. Fetch ops accept either.
- **Q:** `list_tasks` shape? **A:** Two ops — `list_tasks_brief` (slug, id, group, brief, status; no body) and `list_tasks_full` (everything).
- **Q:** Info note at top of current Home.md (`## ⚠ Wiki/config.yaml er delt resource`)? **A:** Drop it. Backup retains it. Warning is obsolete once `wiki/config.yaml` is purged.
- **Q:** Fate of `_tasks_md.py`, `_sidebar.py`, `_wiki.py`? **A:** Delete outright in this task. No shim, no deprecation cycle.
- **Q:** V2-specific tests? **A:** Delete with the modules they test. Add V3 tests for the new structured ops and the migration script.
- **Q:** `millpy-wikipush.py` and `clone_or_init`? **A:** `millpy-wikipush.py` push logic stays on direct git subprocess (out of scope); minimal sliver in scope to drop the `_wiki` import and the `wiki_lock`/`LockBusy` call sites so the script survives `_wiki.py` deletion. `clone_or_init` moves to `_setup.py` (its only caller).
- **Q (review r1):** Does `_spawn_core.groom_and_claim_merge` retry 3 times (`CAS_RETRIES`) or 5 (test literal)? **A:** Bump `CAS_RETRIES` in `wiki/_client.py` from 3 to 5. Use the constant. Single source of truth.
- **Q (review r1):** Does `health_check` need rewriting once `OP_READ` is gone? **A:** Yes — switch to `OP_HEALTH`. Added to client scope.
- **Q (review r1):** Does the public `upsert_task` need a `status` parameter for the migration script? **A:** Yes — added as an optional kwarg. The migration script uses the same public API; no private bypass.
