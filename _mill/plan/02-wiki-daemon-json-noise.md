# Batch: wiki-daemon-json-noise

```yaml
task: "Unhandled exceptions in mill-go orchestration components should degrade gracefully"
batch: "wiki-daemon-json-noise"
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-wiki-daemon.py test-wiki-client-retry.py
depends-on: []
```

## Batch Scope

This batch fixes the wiki daemon `JSONDecodeError` log noise (GitHub issues #654, #652,
#646): `_daemon.py`'s generic `_handle_connection` logs
`[wiki] exception in _handle_connection: JSONDecodeError('Expecting value: line 1 column 1
(char 0)')` at `error` severity on every empty-payload connection — traced to
`wiki/_client.py:_ensure_daemon()`'s redundant bare-connect reachability probe (connects,
immediately closes, sends zero bytes) that runs right before the real health-check request,
which already performs an equivalent connection attempt. Two other legitimate bare-connect
probes elsewhere in `wiki/_client.py` (`wait_for_socket_reachable()`,
`_is_stale()` — documented in `_mill/discussion.md`'s "Remove the redundant bare-connect probe
in `_ensure_daemon`" Decision's scope note) are NOT touched by this batch and remain, which is
exactly why the daemon-side fix is required rather than optional. This batch removes the one
redundant probe and hardens `_daemon.py:_handle_connection` to log empty/malformed payloads at
`debug` severity without attempting a response, while every genuine `handle_request` failure
still logs at `error` severity exactly as today. No external interface changes —
`_ensure_daemon`'s return value and staleness-cleanup behavior, and `_handle_connection`'s
handling of well-formed authenticated requests, are unaffected. All batch-local decisions are
documented per-card below (no deviations from the overview's Shared Decisions).

## Cards

### Card 6: `_handle_connection` logs empty/malformed payloads at debug, not error

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_daemon.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_daemon.py`'s `_handle_connection(self, conn)` method (line 131), wrap
  the existing `msg = json.loads(msg_text)` line in its own nested `try/except
  json.JSONDecodeError` block, distinct from the outer `except Exception as exc:` that already
  wraps the whole method body. On `json.JSONDecodeError`, call
  `self._logger.debug(...)` with a one-line message noting the connection sent an
  empty/malformed payload (include `len(msg_text)` in the message for diagnostics), then
  `return` immediately — do NOT attempt `conn.sendall(...)` for this case (the method's
  existing `finally: conn.close()` clause still runs on this early `return`, so the connection
  is still closed). Do not modify the outer `except Exception as exc:` block (the
  `auth_error`/`server_error` response construction and `self._logger.error(f"exception in
  _handle_connection: {exc!r}")` call) — it must continue to catch and report every OTHER
  exception exactly as today, including any exception raised by `self.handle_request(msg)` or
  by `conn.sendall(...)` itself. The `msg_text = b"".join(chunks).decode("utf-8")` line, the
  token check (`if msg.get("token") != self._token: ...`), the `self.handle_request(msg)`
  dispatch, and the success-path `conn.sendall(...)` remain unchanged in shape and order —
  only the single `msg = json.loads(msg_text)` statement needs the new inner try/except wrapped
  around it.
- **Commit:** `fix(daemon): log empty/malformed connection payloads at debug, not error`

### Card 7: test coverage for `_handle_connection`'s empty/malformed-payload handling

- **Context:**
  - `plugins/mill/scripts/_daemon.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-daemon.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `test-wiki-daemon.py`, immediately after the existing
  `# --- (v) SPAWN_TIMEOUT platform-guarded assertion ---` block and before the final
  `print("", file=sys.stderr)` / pass-fail summary block, add two new `try/except`-wrapped
  blocks using the file's existing `ok(name)` / `fail(name, exc)` helper convention (no new
  helpers needed). **Block (w) — empty payload:** create a `tmp = Path(tempfile.mkdtemp())`
  temp dir with the existing `_safe_rmtree.safe_rmtree(tmp, allowed_root=tmp,
  ignore_errors=True)` cleanup pattern (matching every other block in this file); construct
  `daemon = TestDaemon("test", tmp / "state.json", 30)` and set `daemon._token = "tok"`;
  build `mock_conn = MagicMock()` (already imported at module level) with
  `mock_conn.recv.return_value = b""` (simulating a connection that sends zero bytes before
  the server's first `recv` call returns empty, matching the real bare-connect-probe
  scenario); use `patch.object(daemon._logger, "debug") as mock_debug` and
  `patch.object(daemon._logger, "error") as mock_error` (both already imported at module
  level) around a call to `daemon._handle_connection(mock_conn)`; then assert all four:
  `not mock_conn.sendall.called` (no response attempted), `mock_conn.close.called` (connection
  still closed via the `finally` clause), `mock_debug.called` (logged at debug), and
  `not mock_error.called` (NOT logged at error) — call `ok("_handle_connection empty payload
  -> debug log, no response, no crash")` on success. **Block (x) — malformed-nonempty
  payload:** identical structure and assertions to block (w), except
  `mock_conn.recv.side_effect = [b"not valid json", b""]` (first `recv` call returns
  non-empty-but-invalid-JSON bytes, second call returns empty signaling the peer closed) —
  call `ok("_handle_connection malformed-nonempty payload -> debug log, no response, no
  crash")` on success. Both blocks wrap their body in `try: ... except Exception as exc:
  fail("<matching name>", exc)` per the file's existing convention.
- **Commit:** `test(daemon): cover _handle_connection empty and malformed payload handling`

### Card 8: remove the redundant bare-connect probe in `_ensure_daemon`

- **Context:**
  - `plugins/mill/scripts/_daemon.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `wiki/_client.py`'s `_ensure_daemon()` function (~line 606), inside the
  `if state_file.exists(): if state: if state.get("protocol_version") != PROTOCOL_VERSION: ...
  else: ...` structure, the `else:` branch currently reads:
  ```
  else:
      try:
          sock = socket.create_connection(
              (state["host"], state["port"]), timeout=0.5
          )
          sock.close()
          req = {FIELD_OP: OP_HEALTH, FIELD_TOKEN: state["token"], "payload": {}}
          try:
              resp = _connect_send_recv(state["host"], state["port"], req, timeout=1.0)
              if resp.get(FIELD_OK) is True:
                  return (state["host"], state["port"], state["token"])
          except OSError:
              pass
          if _is_stale(state):
              state_file.unlink(missing_ok=True)
      except OSError:
          if _is_stale(state):
              state_file.unlink(missing_ok=True)
  ```
  Replace it with:
  ```
  else:
      req = {FIELD_OP: OP_HEALTH, FIELD_TOKEN: state["token"], "payload": {}}
      try:
          resp = _connect_send_recv(state["host"], state["port"], req, timeout=1.0)
          if resp.get(FIELD_OK) is True:
              return (state["host"], state["port"], state["token"])
      except OSError:
          pass
      if _is_stale(state):
          state_file.unlink(missing_ok=True)
  ```
  This removes the bare `socket.create_connection(...); sock.close()` probe (the sole
  observable effect of which today is triggering the daemon's empty-payload JSONDecodeError —
  see `_daemon.py:_handle_connection`, hardened by Card 6) and removes the now-dead outer
  `except OSError:` wrapper — with the probe gone, nothing in the remaining body can raise an
  `OSError` before the inner `try/except OSError` (around `_connect_send_recv`) already
  catches it, so the outer wrapper's `except OSError:` branch was unreachable and its
  `if _is_stale(state): state_file.unlink(...)` body is preserved by leaving the identical
  `if _is_stale(state): state_file.unlink(missing_ok=True)` call at the end of the un-nested
  block, now reachable from both the inner-except path and the case where
  `_connect_send_recv` raised nothing but `resp.get(FIELD_OK)` was not `True`. Do not change
  the `if` branch above this `else:` (the `protocol_version` mismatch handling), and do not
  change `wait_for_socket_reachable()` or `_is_stale()` themselves — both are documented as
  remaining, legitimate bare-connect probes per `_mill/discussion.md` and are out of scope for
  this card. `socket` remains imported and used elsewhere in this module (by
  `wait_for_socket_reachable` and `_is_stale`) — do not remove the `import socket` statement.
- **Commit:** `fix(wiki-client): remove redundant bare-connect probe in _ensure_daemon`

## Batch Tests

`verify:` runs `test-wiki-daemon.py` (Cards 6-7, new debug/error-log assertions for
`_handle_connection`) and `test-wiki-client-retry.py` (regression check for Card 8 — this file
is not edited by this batch, but it is the existing indirect coverage for
`_ensure_daemon`'s staleness-cleanup and successful-reconnect paths per
`_mill/discussion.md`'s Testing section; re-running it confirms the probe removal is
behavior-neutral for those paths) via `run-all.py --only`, scoped to exactly these two files.
