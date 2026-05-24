# Batch: wiki-module-refactor

```yaml
task: Adopt V3 wiki module in V2 scripts
batch: wiki-module-refactor
number: 1
cards: 12
verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Reshape the V3 wiki module (`plugins/mill/scripts/wiki/`) into the structured-task API every V2 caller will consume in batch 3 and the migration script will consume in batch 2. This batch is the producer of the public surface; nothing outside `plugins/mill/scripts/wiki/` and its unit/integration tests is modified.

External interface delivered to batches 2 and 3:

- `wiki._client.upsert_task(slug, *, title=None, brief=None, body=None, group=None, status=None) -> dict`
- `wiki._client.upsert_tasks_batch(tasks: list[dict]) -> None`
- `wiki._client.set_phase(id_or_slug, phase) -> None`
- `wiki._client.remove_task(id_or_slug) -> None`
- `wiki._client.get_task(id_or_slug) -> dict | None`
- `wiki._client.list_tasks_brief() -> list[dict]` (keys `{id, slug, title, group, brief, status, has_proposal}`)
- `wiki._client.list_tasks_full() -> list[dict]` (every field)
- `wiki._client.health_check() -> bool`
- `wiki.LOCKED_FOLD_PHASES` re-export from `wiki/__init__.py`
- Protocol constants in `wiki/__init__.py`: `PROTOCOL_VERSION = 2`, new `OP_*` symbols, no `OP_READ`/`OP_WRITE`
- Extended `wiki._parse.parse_home_md(content) -> list[dict]` covering parenthetical layer headers, multi-paragraph briefs, info-only `##` skip, `[s] -> None`, `[abandoned]` preserved

Batch-local decisions (differ from `## Shared Decisions` in `00-overview.md`):

- **Identifier dispatch helper:** All public client methods that accept `int | str` delegate to a single private helper in `_store.py` (`_resolve_id_or_slug(db, identifier) -> int | None`) that returns the TinyDB doc_id. This avoids per-method type-branching. Identifier-by-int looks up by `doc_id`; identifier-by-str looks up by `slug` field. Missing identifier returns `None` for `get_task`/`remove_task`/`set_phase` callers to handle.
- **`upsert_task` return shape:** Returns the freshly-upserted task as a full dict (every TinyDB field). Callers in batch 2 and 3 use this to get the assigned `id` after creation.
- **`has_proposal` is computed at read time:** `Store.list_tasks_brief()` computes `has_proposal = bool(task.get("body"))` for each row; not stored as a separate column in TinyDB.

## Cards

### Card 1: `_store.py` — id-from-0, identifier-by-int-or-slug, list_tasks_brief / list_tasks_full

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_store.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Modify `Store.upsert_task` so the first task assigned when DB is empty has `id = 0` (current code uses `max_id + 1` with `max_id = 0`, producing id `1` for the first task). Use `max_id = max([t["id"] for t in db.all()], default=-1)` then `id = max_id + 1`. Add a private helper `_resolve_id_or_slug(db, identifier: int | str) -> int | None` returning the TinyDB doc_id for the matching task, or `None` if not found. Add public `Store.get_task(identifier: int | str) -> dict | None`, `Store.remove_task(identifier: int | str) -> None` (silent on miss), `Store.set_phase(identifier: int | str, phase: str | None) -> None` (silent on miss; phase `None` clears the status field). Add `Store.list_tasks_brief() -> list[dict]` returning per-task dicts with exactly the keys `{id, slug, title, group, brief, status, has_proposal}` where `has_proposal = bool(task.get("body"))`. Add `Store.list_tasks_full() -> list[dict]` returning every TinyDB field per task. Add `Store.upsert_tasks_batch(tasks: list[dict]) -> None` that upserts each task into TinyDB without triggering any render or commit (the server's batch handler does render+commit once at the end). Delete `Store.set(rel_path, content)` and `Store.get(rel_path)` — both belong to the removed `OP_READ`/`OP_WRITE` path and have no caller after this task lands. Preserve `Store.upsert_task` keyed by slug (existing slug -> update + preserve id; new slug -> assign next id).
- **Commit:** `feat(wiki/_store): add structured task ops and id-from-0`

### Card 2: `_render.py` — group order A-Z then None, empty-group skip, accept all A-Z, drop [s], emit [abandoned]

- **Context:**
  - `plugins/mill/scripts/wiki/_store.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_render.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace the hardcoded `group_order = [None, "A", "B", "C", "D", "Z"]` with logic that sorts groups alphabetically `A` through `Z` first, then ungrouped (`group is None`) last. Skip empty groups entirely — when no task has `group == X`, emit no `# Layer X` header and no entries for X. Accept any letter A-Z, not just the previous fixed subset. The status field in the rendered output must never emit `[s]` regardless of the input task's `status` value (treat any incoming `s` as `None`). Emit `[abandoned]` as a first-class status marker (same shape as `[active]`, `[done]`, etc.). Continue producing `Home.md`, `_Sidebar.md`, and `proposal-{slug}.md` (one per task whose `body` is non-empty). Two consecutive renders of the same input must produce byte-identical output (no timestamps, no nondeterministic ordering within a group — sort tasks within a group by `id` ascending). Return value is the existing `dict[str, str]` mapping relative path -> rendered content.
- **Commit:** `feat(wiki/_render): A-Z-then-null group order, empty-group skip, [abandoned] support`

### Card 3: `_parse.py` — extended parser for migration; drop [s], keep [abandoned]

- **Context:**
  - `plugins/mill/scripts/wiki/_store.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_parse.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** `parse_home_md(content: str) -> list[dict]` returns dicts with keys `{slug, title, group, brief, status}` (no `body`/`id` — those are seeded separately by the migration script). Recognise `# Layer ([A-Z])(?:\s+.*)?$` as a layer header — the parenthetical/freeform suffix (e.g. `# Layer D (isolated -- run alone)`) is allowed and ignored; group letter is the captured `[A-Z]`. Capture each task's brief verbatim across blank lines until the next `##` or `#` heading, then collapse the captured paragraphs to one space-joined paragraph for the `brief` field. Skip `##` headings whose next non-blank line is NOT a `[slug]` line or `[[slug]](proposal-slug.md)` line — these are info-only notes (e.g. `## (warn) wiki/config.yaml ...`) and must not produce a task entry. Parse `[s]` (legacy spawn-ready marker) as `status = None`. Parse `[abandoned]` as `status = "abandoned"`. Existing supported statuses (`active`, `done`, `pr-pending`, `ready-to-merge`, `blocked`) remain first-class. Titles may carry numeric prefix and group code (e.g. `## 30 (D) -- Foo`); parse without crash, retain the full title text after the leading numeric/group prefix is stripped if present. The function is invoked by the migration script (batch 2); the daemon never calls it at runtime.
- **Commit:** `feat(wiki/_parse): extended parser for migration; drop [s], keep [abandoned]`

### Card 4: `wiki/__init__.py` — protocol op constants, PROTOCOL_VERSION bump, LOCKED_FOLD_PHASES

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Bump `PROTOCOL_VERSION` from `1` to `2`. Remove the `OP_READ` and `OP_WRITE` constants. Add new constants `OP_UPSERT_TASK`, `OP_UPSERT_TASKS_BATCH`, `OP_SET_PHASE`, `OP_REMOVE_TASK`, `OP_GET_TASK`, `OP_LIST_TASKS_BRIEF`, `OP_LIST_TASKS_FULL`, `OP_HEALTH` — each a short string literal matching the op name (e.g. `OP_UPSERT_TASK = "upsert_task"`). Add a module-level tuple `LOCKED_FOLD_PHASES = ("active", "ready-to-merge", "pr-pending")` matching the canonical phase tuple referenced by `mill-fold`. Leave existing `FIELD_*`, `ERR_*`, exception classes (`WikiError`, `WikiNotFoundError`, `WikiConflictError`, `WikiPushError`, `WikiProtocolError`, `WikiStartupError`, `WikiPathError`) untouched.
- **Commit:** `feat(wiki/__init__): structured op constants, PROTOCOL_VERSION=2, LOCKED_FOLD_PHASES`

### Card 5: `_server.py` — replace _handle_read/_handle_write with per-op handlers; batch handler

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_store.py`
  - `plugins/mill/scripts/wiki/_render.py`
  - `plugins/mill/scripts/wiki/_sync.py`
  - `plugins/mill/scripts/_daemon.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_server.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Delete `_handle_read` and `_handle_write` entirely. Remove all dispatch entries for `OP_READ` and `OP_WRITE` from the request-router. Add one handler per new op:
  - `_handle_upsert_task(payload)` — payload is the full task dict; calls `Store.upsert_task`, then `_render_and_commit_all(slug_for_msg=payload["slug"])`. Response `{ok: true, task: <full dict>}`.
  - `_handle_upsert_tasks_batch(payload)` — payload is `{tasks: [...]}`; calls `Store.upsert_tasks_batch(tasks)`, then `_render_and_commit_all(slug_for_msg="batch")`. Response `{ok: true, count: <len>}`.
  - `_handle_set_phase(payload)` — payload `{id_or_slug, phase}`; calls `Store.set_phase`; on miss respond `{ok: false, error_type: "not_found", error: ...}`; on hit `_render_and_commit_all(slug_for_msg=str(id_or_slug))`. Response `{ok: true}`.
  - `_handle_remove_task(payload)` — payload `{id_or_slug}`; calls `Store.remove_task`; on miss `{ok: false, error_type: "not_found", ...}`; on hit `_render_and_commit_all(...)`. Response `{ok: true}`.
  - `_handle_get_task(payload)` — payload `{id_or_slug}`; returns `{ok: true, task: <dict or null>}`. No render, no commit.
  - `_handle_list_tasks_brief(payload)` — no payload; returns `{ok: true, tasks: <list of brief dicts>}`. No render, no commit.
  - `_handle_list_tasks_full(payload)` — no payload; returns `{ok: true, tasks: <list of full dicts>}`. No render, no commit.
  - `_handle_health(payload)` — returns `{ok: true}` immediately. No DB access, no git access.

  Factor the `render(all_tasks) -> atomic_write each file -> commit_push (with one rebase retry, as today)` sequence into a single private helper `_render_and_commit_all(slug_for_msg: str)` invoked by every mutating handler. The commit message uses the form `wiki: {slug_for_msg}` (matching the existing V3 commit-message shape from `_handle_write` so wiki history stays consistent). Unknown ops return `{ok: false, error_type: "protocol_error", error: "unknown op: {op}"}`. Keep the auth-token check, version-mismatch handling, `_last_pull` lazy refresh, and `.wiki-daemon.json` / `.wiki-daemon.log` lifecycle exactly as today.
- **Commit:** `feat(wiki/_server): structured op handlers, batch render+commit`

### Card 6: `_client.py` — drop read/write_commit_push, add structured methods, CAS_RETRIES=5, health via OP_HEALTH

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Bump module-level `CAS_RETRIES` from `3` to `5`. Delete public functions `read` and `write_commit_push`. Add public functions matching the External interface section above: `upsert_task(slug, *, title=None, brief=None, body=None, group=None, status=None) -> dict`, `upsert_tasks_batch(tasks: list[dict]) -> None`, `set_phase(id_or_slug, phase) -> None`, `remove_task(id_or_slug) -> None`, `get_task(id_or_slug) -> dict | None`, `list_tasks_brief() -> list[dict]`, `list_tasks_full() -> list[dict]`. Each constructs the request payload, calls `_ensure_daemon()` then `_connect_send_recv(op, payload)`, wraps `error_type == "conflict"` -> `WikiConflictError`, `error_type == "not_found"` -> `WikiNotFoundError`, `error_type == "push_error"` -> `WikiPushError`, `error_type == "protocol_error"` -> `WikiProtocolError`. Mutating methods (`upsert_task`, `upsert_tasks_batch`, `set_phase`, `remove_task`) catch `WikiConflictError` and retry up to `CAS_RETRIES` attempts; raise on final exhaustion. Read-only methods (`get_task`, `list_tasks_brief`, `list_tasks_full`) do not retry. Rewrite `health_check()` to send `OP_HEALTH` (no payload, no retry); on any error return `False`, on `{ok: true}` return `True`. Re-export `LOCKED_FOLD_PHASES` from `wiki/__init__.py` at module top so callers can `from wiki._client import LOCKED_FOLD_PHASES` if convenient (primary path is `from wiki import LOCKED_FOLD_PHASES`).
- **Commit:** `feat(wiki/_client): structured task API, CAS_RETRIES=5, OP_HEALTH`

### Card 7: `test-wiki-store.py` — id-from-0, identifier dispatch, brief/full shapes

- **Context:**
  - `plugins/mill/scripts/wiki/_store.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-store.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Extend existing tests so they assert: (a) `upsert_task` on empty DB assigns `id = 0`; (b) `upsert_task` on a DB with ids `{0, 1, 3}` assigns `id = 4` (`max + 1`); (c) `upsert_task` with an existing slug updates fields and preserves the original id; (d) `get_task(slug)` and `get_task(id)` both return the same record; missing identifier returns `None`; (e) `remove_task(slug)` and `remove_task(id)` both work; missing identifier returns silently (no exception); (f) `set_phase(slug_or_id, "active")` updates the status; `set_phase(slug_or_id, None)` clears it; (g) `list_tasks_brief()` returns dicts whose key set is exactly `{id, slug, title, group, brief, status, has_proposal}` — assert `"body" not in row` for every row; assert `has_proposal == True` when body is non-empty and `False` when body is `""`/missing; (h) `list_tasks_full()` returns dicts that contain `body`. Delete any test covering the removed `Store.set` / `Store.get` methods.
- **Commit:** `test(wiki/_store): cover id-from-0, identifier dispatch, brief/full shapes`

### Card 8: `test-wiki-render.py` — group order, empty-group skip, [s] never emitted, [abandoned] emitted, byte-identical renders

- **Context:**
  - `plugins/mill/scripts/wiki/_render.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-render.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Extend existing tests so they assert: (a) tasks grouped `B, A, C, None` render in order `A, B, C, None` (alphabetic then None last); (b) when no task has `group == "B"`, no `# Layer B` header appears in `Home.md`; (c) tasks with groups `M`, `Q`, `Z` all render (no rejection of letters outside the legacy `[A, B, C, D, Z]` set); (d) a task with `status == "s"` renders no status marker (assert the rendered line does not contain `[s]`); (e) a task with `status == "abandoned"` renders `[abandoned]`; (f) `proposal-{slug}.md` appears in render output when the task's `body` is non-empty; absent when `body` is `""` or missing; (g) two consecutive `render(same_tasks)` calls produce byte-identical dicts. Drop any test that asserted the old hardcoded group order.
- **Commit:** `test(wiki/_render): A-Z order, empty-group skip, status emission, byte-identical`

### Card 9: `test-wiki-parse.py` — extended parser features

- **Context:**
  - `plugins/mill/scripts/wiki/_parse.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-wiki-parse.py`
- **Deletes:** none
- **Requirements:** Create a new unit-test file `test-wiki-parse.py` registered with the existing `_test_registry` pattern used by sibling unit tests (see `test-wiki-store.py` for the registration shape). Cover: (a) `# Layer D (isolated -- run alone)` parses as group `D` with no crash; the parenthetical text is ignored; (b) `## (warn) wiki/config.yaml ...` (or any `##` heading whose next non-blank line is NOT a `[slug]` / `[[slug]](...)` line) produces no task entry — assert the returned list does not contain anything for that heading; (c) a task with a brief spanning three paragraphs separated by blank lines collapses into one space-joined paragraph in the `brief` field; (d) `[s]` parses to `status = None`; (e) `[abandoned]` parses to `status = "abandoned"`; (f) a title `## 30 (D) -- Adopt V3 wiki module in V2 scripts` parses without crash and returns a sensible `title` field. Each test case uses inline string fixtures; no on-disk files.
- **Commit:** `test(wiki/_parse): cover extended parser features`

### Card 10: `test-wiki-protocol.py` — each new op dispatches correctly, OP_READ/OP_WRITE rejected, auth + version preserved

- **Context:**
  - `plugins/mill/scripts/wiki/_server.py`
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-protocol.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Extend so the suite asserts: (a) each of `OP_UPSERT_TASK`, `OP_UPSERT_TASKS_BATCH`, `OP_SET_PHASE`, `OP_REMOVE_TASK`, `OP_GET_TASK`, `OP_LIST_TASKS_BRIEF`, `OP_LIST_TASKS_FULL`, `OP_HEALTH` reaches the correct handler and returns `{ok: true, ...}` on the happy path with a small fixture; (b) sending the literal op string `"read"` or `"write"` returns `{ok: false, error_type: "protocol_error", error: "unknown op: read"}` (and `"unknown op: write"`); (c) an unauthenticated request (bad/missing token) returns the existing unauthorised response unchanged; (d) connecting with `PROTOCOL_VERSION = 1` triggers the existing version-mismatch path (daemon respawn). Drop any test that exercises `OP_READ` / `OP_WRITE` happy paths.
- **Commit:** `test(wiki/_server): structured ops, removed-op rejection, auth + version preserved`

### Card 11: `test-wiki-e2e.py` — structured ops, concurrent CAS

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-wiki-e2e.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace every `_client.read(...)` / `_client.write_commit_push("Home.md", ...)` call with structured equivalents (`upsert_task`, `set_phase`, `list_tasks_brief`, `get_task`). The concurrent-write soak test must drive two subprocesses each calling `set_phase` on the same slug from different angles; assert at least one CAS conflict is observed and the retry path resolves it. Replace the existing local literal `max_retries = 5` with `from wiki._client import CAS_RETRIES` and reference the constant directly (no duplicate literal). The test must continue running end-to-end with a real spawned daemon, real TinyDB, real git repo.
- **Commit:** `test(wiki-e2e): structured ops, CAS_RETRIES via constant`

### Card 12: Audit and update remaining wiki tests for OP_READ/OP_WRITE usage

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-wiki-daemon.py`
  - `plugins/mill/integration_tests/test-wiki-daemon-tinydb.py`
  - `plugins/mill/integration_tests/test-wiki-noop-commit.py`
  - `plugins/mill/integration_tests/test-wiki-sync.py`
  - `plugins/mill/integration_tests/test-wiki-concurrency.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Grep each file for `OP_READ`, `OP_WRITE`, `_client.read`, `_client.write_commit_push`. For each occurrence, replace with the appropriate structured op:
  - Setting up state -> `upsert_task` or `upsert_tasks_batch`.
  - Asserting state -> `list_tasks_brief` / `list_tasks_full` / `get_task`.
  - Driving concurrent mutation -> `set_phase`.
  - Liveness probe -> `health_check` (which now sends `OP_HEALTH`).

  If a test exercised only the now-removed `OP_READ`/`OP_WRITE` semantic and has no V3 analogue (e.g. asserting raw-file write coalescing on the daemon side), delete that single test function (not the whole file) and leave a one-line `# removed: covered by test-wiki-protocol.py::test_unknown_op_rejection` referenced commit-message-only; do not write the comment into the file. The five files in Edits: above are the integration suite — they continue to spawn a real daemon. Do not break the existing assertions about commit messages, push behaviour, or noop-commit detection — only translate the protocol surface.
- **Commit:** `test(wiki): port remaining wiki tests to structured ops`

## Batch Tests

The batch verify command is `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` plus the integration tests touched in cards 11 and 12. The unit-test suite covers cards 7-10; the integration suite covers cards 11 and 12. The runner reports pass/fail per file. After this batch, every `wiki/*.py` and `test-wiki-*.py` should be green; no V2 caller has yet been ported, so other test files may still pass (they call `_wiki.py`/`_tasks_md.py` which still exist) or may have already been touched by parallel batch 3 work — that's batch 3's concern, not batch 1's.
