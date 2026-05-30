# Batch: wiki-client-robustness

```yaml
task: Wiki-daemon + bg-worker + test-suite robustness on Windows
batch: wiki-client-robustness
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-wiki-daemon.py
depends-on: []
```

## Batch Scope

Delivers the two client-side wiki-daemon robustness fixes (#400, #395), both of
which live in `wiki/_client.py` and share >80% of their context, so they form
one batch. #400 adds a `WikiBusyError` exception and a bounded recv-timeout
retry around the per-op dispatch so a busy-but-alive daemon no longer surfaces a
bare `TimeoutError`. #395 extracts the existing `_ensure_daemon` socket-poll into
a reusable `wait_for_socket_reachable` helper and lengthens the Windows spawn
budget. No external interface is consumed by later batches. Batch-local
posture: the retry wraps ONLY the op-dispatch `_connect_send_recv` call, never
the fast health probe inside `_ensure_daemon`.

## Cards

### Card 1: Add `WikiBusyError` exception

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new exception class `WikiBusyError(WikiError)` to
  `wiki/__init__.py`, placed alongside the existing subclasses (after
  `WikiStartupError` / `WikiPathError` in the error-types block at lines 45-75),
  with a one-line docstring "Daemon was alive but stayed busy past the retry
  budget." If `wiki/__init__.py` exposes an `__all__`, add `"WikiBusyError"` to
  it. Do not change any other exception. The class must be importable as
  `from wiki import WikiBusyError`.
- **Commit:** `feat(wiki): add WikiBusyError exception`

### Card 2: Bounded recv-timeout retry raising `WikiBusyError`

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `wiki/_client.py`: (1) add `WikiBusyError` to the
  `from wiki import (...)` import block (lines 13-37). (2) Wrap the op-dispatch
  call to `_connect_send_recv` in `_dispatch` (the call at line 118, inside the
  daemon-TCP branch after `_ensure_daemon`) in a bounded retry: 3 attempts with
  `time.sleep` backoff of 2s, 4s, 8s between attempts, catching `TimeoutError`
  (which since Python 3.10 also covers `socket.timeout`); on the final attempt's
  timeout raise `WikiBusyError` with a message naming the op. Do NOT retry other
  `OSError` subtypes — only the timeout. (3) Pass an explicit per-attempt
  `timeout=3.0` to that `_connect_send_recv` call so a stalled daemon fails fast
  enough for retries to matter (worst case ~23s before `WikiBusyError`). Leave
  the `_connect_send_recv` default signature and the health-probe call inside
  `_ensure_daemon` (the `timeout=1.0` call) UNCHANGED — the retry must not wrap
  the health probe. Keep all `print`/log strings ASCII.
- **Commit:** `fix(wiki): retry recv timeouts and raise WikiBusyError on exhaustion`

### Card 3: Extract `wait_for_socket_reachable`; bump Windows spawn timeout

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `wiki/_client.py`: (1) Add a module-level helper
  `wait_for_socket_reachable(host: str, port: int, *, timeout: float, interval: float = 0.1) -> bool`
  that polls `socket.create_connection((host, port), timeout=0.5)` every
  `interval` seconds until success (returns `True`) or the `timeout` budget
  expires (returns `False`); it must not raise on `OSError`/`socket.timeout`
  during polling. (2) Refactor the `_ensure_daemon` spawn-wait loop (lines
  521-535) to use it: because host/port are only known after the daemon writes
  `.wiki-daemon.json`, keep the outer loop that re-reads the state file via
  `_read_state_file()` and call `wait_for_socket_reachable(state["host"],
  state["port"], timeout=...)` once a state dict with host/port is available;
  return `(host, port, token)` on reachable, fall through to the existing
  `WikiStartupError("daemon did not start within timeout")` on budget
  exhaustion. Preserve existing behavior exactly otherwise. (3) Change
  `SPAWN_TIMEOUT` (line 39) so the Windows budget is ~20s: set
  `SPAWN_TIMEOUT = 20 if sys.platform == "win32" else 10`. Keep strings ASCII.
- **Commit:** `fix(wiki): add wait_for_socket_reachable and raise Windows spawn timeout`

### Card 4: Tests for retry, `WikiBusyError`, and spawn helper

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-daemon.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Extend `test-wiki-daemon.py` (follow its existing `main()` +
  `ok()/fail()` + `unittest.mock.patch` style; do NOT convert to unittest
  classes) with cases: (a) a transient recv `TimeoutError` that clears within 3
  attempts → op succeeds, `WikiBusyError` NOT raised; (b) persistent recv
  `TimeoutError` → exactly 3 attempts then `WikiBusyError` raised; (c) backoff
  sequence is `[2, 4, 8]` — patch `wiki._client.time.sleep` and assert the
  recorded call args (do not actually sleep); (d) the `_ensure_daemon` health
  probe is single-shot (NOT wrapped by the busy-retry); (e) `WikiBusyError` is a
  subclass of `WikiError` and importable from `wiki`; (f)
  `wait_for_socket_reachable` returns `True` for a bound listening socket and
  `False` (within budget, no raise) for a closed/refused port; (g)
  `SPAWN_TIMEOUT` is 20 under a patched `sys.platform == "win32"`. Mock sockets
  / `create_connection` as the existing daemon tests do; spawn no real
  processes.
- **Commit:** `test(wiki): cover WikiBusyError retry and wait_for_socket_reachable`

## Batch Tests

`verify` runs `test-wiki-daemon.py` (the file owning all `_client.py` /
`_ensure_daemon` daemon tests) via `run-all.py --only`. Card 4 adds the new
cases; the existing daemon-respawn cases (h/i/j and others) must stay green,
proving the `_ensure_daemon` refactor preserved behavior. All socket and
`time.sleep` interactions are mocked — no real daemon, no real sleeping.
