# Batch: wiki-daemon-fixes

```yaml
task: V3 wiki adoption follow-up bugs
batch: wiki-daemon-fixes
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Fixes the three wiki-daemon/server bugs that share `plugins/mill/scripts/wiki/_client.py` and `plugins/mill/scripts/wiki/_server.py`: #382 (health-exchange replaces bare TCP ping), #383 (remove-task always re-renders), and #384 (orphan `proposal-*.md` deletion). Tests are co-located with the prod fix in this batch. The batch is one Sonnet unit because all three bugs live in a tight 2-file surface, share the same domain model (the daemon protocol and render pipeline), and their test fixtures use the same `_test_helpers.safe_temp_dir` / wiki seed pattern.

External interface: none changes. Wire protocol, op constants, and public client API are unchanged. The only signature change is `_connect_send_recv` gaining an optional `timeout=10.0` parameter — strictly additive.

Batch-local decisions:

- The orphan-detection glob (`wiki_path.glob("proposal-*.md")`) runs once per `_render_and_commit_all` call regardless of operation type, so any mutation path (`upsert`, `set_phase`, `remove`, `merge`, `rerender`) self-reconciles. This is intentional — see #383 discussion.
- The `_connect_send_recv` `timeout` parameter applies to the `socket.create_connection` step and is passed through unchanged. The send/recv loop has no separate timeout — the connection timeout subsumes blocking time for localhost JSON round-trips.

## Cards

### Card 1: Add timeout parameter to _connect_send_recv and use OP_HEALTH in _ensure_daemon

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/_daemon.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Change `_connect_send_recv(host: str, port: int, msg: dict) -> dict` (currently at `_client.py:523`) to `_connect_send_recv(host: str, port: int, msg: dict, *, timeout: float = 10.0) -> dict`. Replace the hardcoded `10.0` at `_client.py:537` with `timeout`. All existing call sites continue to work because the new parameter is keyword-only with the original default.
  - In `_ensure_daemon` (`_client.py:425`), inside the `else:` branch that currently does only `socket.create_connection(...)` + `sock.close()` + `return ...` (lines 460–471), replace the bare-connect-and-return with: connect (keep the existing 0.5s TCP timeout), close the socket, then issue a follow-up `_connect_send_recv(state["host"], state["port"], req, timeout=1.0)` where `req = {FIELD_OP: OP_HEALTH, FIELD_TOKEN: state["token"], "payload": {}}`. Wrap the `_connect_send_recv` call in `try/except OSError`. On `OSError` OR a response whose `FIELD_OK` value is not `True`: if `_is_stale(state)` returns `True`, unlink the state file; either way, fall through to `_spawn_server(wiki_path)`. On a successful health response (`FIELD_OK: True`), `return (state["host"], state["port"], state["token"])` as before.
  - Do NOT touch the spawn-loop (`_client.py:476–488`) — its bare TCP connect is intentional (the daemon we just spawned writes the state file, so the port is ours).
  - Do NOT touch `_is_stale` (`_client.py:597–607`) — its bare TCP connect is a hint used only before respawn, not a gate.
- **Commit:** `fix(wiki): verify daemon with OP_HEALTH exchange instead of bare TCP ping (#382)`

### Card 2: Add unit tests for OP_HEALTH-exchange daemon verification

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/_daemon.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-daemon.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add new test cases following the existing `main()` + `ok()` / `fail()` shape in `test-wiki-daemon.py`. Three new cases, appended after the existing block (use the next available `(letter)` marker):
    1. **Stale-port-reuse case** — write a valid state file with `protocol_version` matching `PROTOCOL_VERSION`. Patch `wiki._client.socket.create_connection` to succeed (returns a `MagicMock` whose `.close()` is a no-op) AND patch `wiki._client._connect_send_recv` to raise `OSError`. Patch `wiki._client._spawn_server` to a `MagicMock` (no-op). Patch `wiki._client._is_stale` to return `True`. Patch `wiki._client.SPAWN_TIMEOUT` to `0.01` so the post-spawn polling loop completes in milliseconds when the mocked `_spawn_server` writes no new state file. Wrap the `_ensure_daemon(wiki_path)` call in `try: ... except wiki.WikiStartupError: pass` — the patched no-op `_spawn_server` never produces a fresh state file, so `_ensure_daemon` correctly raises `WikiStartupError` after the (mocked-short) timeout. After the except, assert that the original state file was unlinked AND the `_spawn_server` MagicMock was called once. Import `WikiStartupError` from the `wiki` package at the top of the file alongside the existing imports.
    2. **Non-ok-health-response case** — same setup as case 1, but `_connect_send_recv` returns `{FIELD_OK: False, FIELD_ERROR: "test"}` instead of raising. Same patches (including `SPAWN_TIMEOUT = 0.01` and the `WikiStartupError` catch), same expected outcome (state file unlinked, `_spawn_server` called once).
    3. **Successful-health case** — `_connect_send_recv` returns `{FIELD_OK: True}`. No `SPAWN_TIMEOUT` patch needed because the healthy branch returns before entering the spawn loop. Assert `_ensure_daemon` returns the host/port/token tuple from the state file AND `_spawn_server` was NOT called.
  - For the temp wiki directory, follow the existing `tmp = Path(tempfile.mkdtemp())` + `try/finally + shutil.rmtree(tmp, ignore_errors=True)` pattern used by tests `(a)`-`(f)` in this file. Do NOT use `_test_helpers.safe_temp_dir` (it is a context manager that does its own cleanup via `safe_rmtree`, which collides with the `try/finally + shutil.rmtree` pattern). Batch 3 converts every `shutil.rmtree` in this file in one pass, including the new cases.
  - For patching, follow the `unittest.mock.patch` pattern (import via `from unittest.mock import patch, MagicMock`). The existing test file does not import mock; add the import at the top after the existing `from _test_helpers import safe_temp_dir` line. Also add `from wiki import PROTOCOL_VERSION, WikiStartupError` to the existing wiki imports (`PROTOCOL_VERSION` is needed because the state-file fixture writes `protocol_version=PROTOCOL_VERSION`; `WikiStartupError` is caught by cases 1 and 2 around the `_ensure_daemon` call).
- **Commit:** `test(wiki): cover OP_HEALTH stale-port-reuse and respawn paths (#382)`

### Card 3: Always re-render in _handle_remove_task even when slug is absent

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_store.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_server.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `_handle_remove_task` (`_server.py:178`), restructure so `self._render_and_commit_all` is called regardless of whether the task existed. Keep the early `self._store.get_task(id_or_slug)` lookup. If the lookup returns `None`: call `_render_and_commit_all(slug_for_msg=f"remove-noop-{id_or_slug}")`, then return `{FIELD_OK: False, FIELD_ERROR_TYPE: ERR_NOT_FOUND, FIELD_ERROR: f"task not found: {id_or_slug}"}` (unchanged). If the lookup returns a task: call `self._store.remove_task(id_or_slug)`, then `_render_and_commit_all(slug_for_msg=str(id_or_slug))`, then return `{FIELD_OK: True}`. Both `_render_and_commit_all` invocations are inside the existing `try/except WikiPushError as e/except Exception as e` block so push-failure handling is unchanged.
  - The `slug_for_msg` for the noop path uses the `remove-noop-` prefix so the commit message is distinguishable in git log; the existing path uses the slug unchanged.
- **Commit:** `fix(wiki): re-render on remove-task miss to reconcile partial-failure state (#383)`

### Card 4: Delete orphan proposal-*.md files in _render_and_commit_all

- **Context:**
  - `plugins/mill/scripts/wiki/_render.py`
  - `plugins/mill/scripts/wiki/_sync.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_server.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `_render_and_commit_all` (`_server.py:303`), after the `rendered = render(self._store.all_tasks())` line and before the `for rel_path, content in rendered.items(): atomic_write(...)` loop, add: compute `existing = {p.name for p in self._wiki_path.glob("proposal-*.md")}` (returns relative filenames, NOT absolute paths); compute `rendered_proposals = {k for k in rendered.keys() if k.startswith("proposal-")}`; `orphans = sorted(existing - rendered_proposals)` (sort for deterministic commit order). For each name in `orphans`: `(self._wiki_path / name).unlink(missing_ok=True)`.
  - Change `commit_paths = list(rendered.keys()) + ["tasks.json"]` to `commit_paths = list(rendered.keys()) + orphans + ["tasks.json"]` then `commit_paths = list(dict.fromkeys(commit_paths))` (existing dedup line, unchanged position). The orphan paths must be staged by `commit_push` so git records the deletion.
  - Do NOT touch `wiki/_render.py` — `render()` stays a pure function.
- **Commit:** `fix(wiki): delete orphan proposal-*.md files on render (#384)`

### Card 5: Add unit tests for remove-task re-render and orphan-deletion

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_store.py`
  - `plugins/mill/scripts/wiki/_render.py`
  - `plugins/mill/scripts/wiki/_sync.py`
  - `plugins/mill/scripts/wiki/_server.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-protocol.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Append new test cases to `test-wiki-protocol.py` using the existing `main()` + `ok()` / `fail()` pattern. Construct a `WikiServer` instance against a tempdir wiki containing a minimal git repo (use `_test_helpers.safe_temp_dir` plus the existing wiki-bootstrap helpers — read the existing tests in `test-wiki-protocol.py` to find the local helper they use; if none exists, inline a minimal `git init` + initial commit setup, matching the style of `test-wiki-store.py`).
  - Two new cases for #383:
    1. **Remove-missing-rerenders case** — seed the store with one task. Call `_handle_remove_task({"id_or_slug": "nonexistent-slug"})`. Patch `WikiServer._render_and_commit_all` to a spy (use `unittest.mock.patch.object`). Assert the spy was called exactly once, AND the response is `{FIELD_OK: False, FIELD_ERROR_TYPE: ERR_NOT_FOUND, ...}`.
    2. **Remove-existing-rerenders case** — seed the store with one task slug "x". Call `_handle_remove_task({"id_or_slug": "x"})`. Same spy assertion (called once), response is `{FIELD_OK: True}`.
  - One new case for #384:
    3. **Orphan-deletion case** — seed the wiki dir with `proposal-old-slug.md` (any content) AND seed the store with one task whose slug is `new-slug` (no body, so render does NOT emit `proposal-new-slug.md`). Call `_handle_rerender({})`. After the call, assert `(wiki_path / "proposal-old-slug.md").exists()` is `False`. Spy on `commit_push` via `patch("wiki._server.commit_push", ...)` — NOT `wiki._sync.commit_push` — because `_server.py` line 33 does `from wiki._sync import ... commit_push`, binding the name in `wiki._server`'s namespace; patching the source module would not intercept the call. Assert the spy's call argument list (`spy.call_args[0]`) contains `"proposal-old-slug.md"` in the `paths` positional argument (second arg per `commit_push(wiki_path, commit_paths, message)`).
  - Imports to add at top of file (after the existing imports): `from unittest.mock import patch, MagicMock` and `from _test_helpers import safe_temp_dir`, and any wiki-server imports needed (`from wiki._server import WikiServer`, `from wiki._store import Store`).
- **Commit:** `test(wiki): cover remove-task rerender and proposal-orphan deletion (#383, #384)`

## Batch Tests

Batch-level `verify:` runs the full unit-test suite (`run-all.py`). New cards land in `test-wiki-daemon.py` (Card 2) and `test-wiki-protocol.py` (Card 5). The existing `test-wiki-render.py` covers `render()` purity and is unaffected — Card 4 deliberately keeps `render()` unchanged so its tests stay green.
