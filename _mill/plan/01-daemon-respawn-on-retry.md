# Batch: daemon-respawn-on-retry

```yaml
task: Fix daemon health-check race, finalize env-var delivery, skills-index drop, and encoding crash
batch: daemon-respawn-on-retry
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-client-retry.py
depends-on: []
```

## Batch Scope

Fixes #594: `_dispatch()` in `wiki/_client.py` currently resolves `(host, port, token)` via `_ensure_daemon(wiki_path)` exactly once, before its 4-attempt retry loop. If the daemon process dies between a caller's `health_check()` call and a subsequent op (e.g. `set_phase()`), every retry attempt hammers the same dead socket for the full `[2, 4, 8]`-second backoff budget and then raises `WikiBusyError`, even though `_ensure_daemon()` is idempotent, cheap to re-invoke, and would have respawned the daemon. This batch makes the retry loop re-invoke `_ensure_daemon()` specifically on `ConnectionRefusedError` (not `TimeoutError`/`ConnectionResetError`, which imply a live-but-slow/reset daemon that doesn't need respawning), and makes a respawn failure (`WikiStartupError`) propagate immediately as terminal rather than being silently retried against the remaining backoff budget. No caller code (mill-go, mill-start, etc.) needs to change — `health_check()` and every other op route through the same `_dispatch()` chokepoint.

## Cards

### Card 1: Respawn daemon mid-retry on ConnectionRefusedError in `_dispatch()`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_dispatch()`'s retry loop (the `for attempt in range(4):` block, currently catching `except (TimeoutError, ConnectionResetError, ConnectionRefusedError):`), split the exception handling so that when the caught exception is specifically a `ConnectionRefusedError` AND `attempt < 3` (i.e. another attempt will actually follow — skip the respawn on the terminal attempt since no further connect happens before `raise WikiBusyError(...)` fires), before the existing `time.sleep(backoff_sleeps[attempt])` logic runs, re-invoke `host, port, token = _ensure_daemon(wiki_path)` and update `req[FIELD_TOKEN] = token` so the next attempt targets the freshly-resolved daemon. Do not wrap this re-invocation in a try/except that catches `WikiStartupError` — let `WikiStartupError` propagate directly out of `_dispatch()` uncaught, bypassing the remaining retry attempts and the `WikiBusyError` path entirely (a respawn failure means retrying the same dead target cannot succeed). For `TimeoutError` and `ConnectionResetError`, keep the existing behavior unchanged — no `_ensure_daemon()` re-invocation, same sleep-and-retry against the same `host`/`port`/`token`.
- **Commit:** `fix(wiki): respawn daemon mid-retry on ConnectionRefusedError (#594)`

### Card 2: Cover respawn-on-retry and respawn-failure paths in `test-wiki-client-retry.py`

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-client-retry.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `WikiStartupError` to the existing `from wiki import WikiBusyError` import line (alongside `WikiBusyError`). Add three new test cases to `main()`, following the file's existing `try:`/`ok()`/`except Exception as exc: fail()` pattern, `safe_temp_dir()` fixture style, and — matching every one of the file's 8 existing cases — wrapping each new case's assertions in `patch.dict(os.environ, {"WIKI_DAEMON_INPROCESS": ""})` alongside the other patches (without it `_dispatch` takes the in-process branch and never reaches the retry loop, so the new cases would silently not exercise Card 1's code): (a) **"ConnectionRefusedError respawns via _ensure_daemon before retrying"** — patch `_client._ensure_daemon` with a `side_effect` list `[("127.0.0.1", 9999, "token-a"), ("127.0.0.1", 8888, "token-b")]`; patch `_client._connect_send_recv` to raise `ConnectionRefusedError` when called with port `9999` and return `{"ok": True}` when called with port `8888`; assert `_dispatch(wiki_path, "test_op", {})` returns `{"ok": True}` and `_ensure_daemon` was called exactly twice. (b) **"TimeoutError does not trigger extra _ensure_daemon call"** — patch `_ensure_daemon` with a call counter (still returning a fixed valid tuple on every call); patch `_connect_send_recv` to raise `TimeoutError` on the first call and return `{"ok": True}` on the second; assert `_dispatch(...)` succeeds and `_ensure_daemon`'s call counter is exactly `1` (not re-invoked for `TimeoutError`). (c) **"Respawn failure (WikiStartupError) propagates immediately as terminal"** — patch `_ensure_daemon` with a `side_effect` list `[("127.0.0.1", 9999, "token-a"), WikiStartupError("daemon did not start within timeout")]`; patch `_connect_send_recv` to always raise `ConnectionRefusedError`; patch `time.sleep` to record calls as the existing tests do; assert `_dispatch(wiki_path, "test_op", {})` raises `WikiStartupError` (not `WikiBusyError`) via `try/except WikiStartupError`, and assert `len(sleep_calls) == 0` (the respawn failure fires on `attempt == 0`, which is `< 3`, so it happens before any backoff sleep in the loop body — consistent with Card 1's `attempt < 3` respawn gate).
- **Commit:** `test(wiki): cover daemon respawn-on-retry and respawn-failure paths (#594)`

## Batch Tests

`verify:` runs the full `test-wiki-client-retry.py` file (single-file scope, matches the existing convention for this file) — covers the existing 8 retry/backoff/timeout cases plus the 3 new cases added by Card 2, exercising both the pre-existing retry semantics and the new respawn-on-`ConnectionRefusedError` / respawn-failure-is-terminal behavior added by Card 1.
