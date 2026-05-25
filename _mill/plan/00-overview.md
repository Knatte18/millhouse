# Plan: Green the unit test suite on wiki-v3-adoption so it can merge to main

```yaml
task: Green the unit test suite on wiki-v3-adoption so it can merge to main
slug: wiki-v3-test-suite-green
approved: false
started: 20260525-173416
parent: hanf/wiki-v3-adoption
root: ""
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

## Batch Index

```yaml
batches:
  - number: 1
    name: foundation
    file: 01-foundation.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-daemon.py
  - number: 2
    name: fixture-updates
    file: 02-fixture-updates.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  - number: 3
    name: gate-and-syntax-fixes
    file: 03-gate-and-syntax-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: verify-command shape

- **Decision:** Every `verify:` command in this plan (overview-level and per-batch) starts with the literal prefix `PYTHONPATH= ` (no value, single trailing space) so the subprocess loads worktree code rather than the cache `PYTHONPATH` propagated from mill-go's parent environment.
- **Rationale:** CLAUDE.md `## Script invocation` -> "Verify command shape" mandates this; `_plan_validate`'s `verify-not-isolated` check rejects plans whose verify omits the prefix.
- **Applies to:** all batches

### Decision: ASCII-only stdout

- **Decision:** All new or modified `print()` / `_log.info(...)` strings use ASCII characters only (`--` not `--` , `->` not `->`, plain quotes).
- **Rationale:** CLAUDE.md `## Conventions`: Windows cp1252 stdout crashes on non-ASCII. Existing daemon `_log.info` strings already comply; new shutdown / handler-close logs must too.
- **Applies to:** all batches

### Decision: test-fixture teardown order for daemon-touching tests

- **Decision:** Every test fixture that triggers `wiki.upsert_task` / `wiki.list_tasks_brief` / any other client call (which transparently spawns the daemon) must call `_test_helpers.wait_for_daemon_exit(wiki_path)` as the LAST statement inside its `with tempfile.TemporaryDirectory()` / `safe_temp_dir()` body, before the context manager's `__exit__` deletes the directory. The wait helper polls `.wiki-daemon.json` absence and returns silently on either success or timeout.
- **Rationale:** Without the wait, the daemon process is still alive (it auto-exits on `idle_timeout`, configured to ~1s in tests via `WIKI_DAEMON_IDLE_TIMEOUT`) when the temp-dir cleanup runs, and Windows refuses to delete a file held open by another process. `on_stop`'s handler-close (Card 1) releases the log lock, but only after the daemon's accept-loop times out; the wait synchronises teardown with that event.
- **Applies to:** batches 1 (helper definition + regression test), 2 (every fixture that uses the helper)

### Decision: wiki seeding via wiki.upsert_task, not direct tasks.json or Home.md edits

- **Decision:** Test fixtures that need a task visible to `wiki.list_tasks_brief` / `slug_from_branch` / `discover_active_worktrees` call `wiki.upsert_task(wiki_path, slug, title=title, status="active")` after `_test_helpers.init_wiki_repo(wiki_path)`. Fixtures must not hand-write `tasks.json` JSON and must not rely on `Home.md` text-parsing for visibility in code paths that go through the V3 client.
- **Rationale:** V3's source of truth is the TinyDB `tasks.json`; the daemon renders `Home.md` from it. Hand-writing TinyDB couples tests to internal layout; relying on Home.md parsing is V2 behaviour that the V3 client no longer implements.
- **Applies to:** batches 1 (helper that supports seeding), 2 (fixtures that need seeding), 3 (RC4 stays Home.md-only because `discover_active_worktrees` is tested against `parse_home_md` output directly, not against the live wiki client)

### Decision: env var WIKI_DAEMON_IDLE_TIMEOUT for test-fixture idle override

- **Decision:** `plugins/mill/scripts/wiki/_server.py`'s `__main__` block reads `idle_timeout` with precedence `WIKI_DAEMON_IDLE_TIMEOUT env -> sys.argv[2] -> 600 default`. Tests set the env var to `"1"` before any wiki client call so the daemon auto-exits ~1s after the last RPC. Production sets neither and gets the 600s default unchanged.
- **Rationale:** The client launcher (`_client._spawn_server`, `_client.py:434`) never passes `idle_timeout` on the cmdline -- the only way to override per-process is an env var the daemon reads on startup. Env var is the smallest production-code surface that supports this.
- **Applies to:** batch 1 (env var implementation), batch 2 (fixtures that set the env var)

## All Files Touched

- `plugins/mill/scripts/wiki/_server.py`
- `plugins/mill/unit_tests/_test_helpers.py`
- `plugins/mill/unit_tests/test-bg-launcher.py`
- `plugins/mill/unit_tests/test-fold.py`
- `plugins/mill/unit_tests/test-marker.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-review-cli.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-setup-hub-links.py`
- `plugins/mill/unit_tests/test-spawn-core.py`
- `plugins/mill/unit_tests/test-wiki-daemon.py`
