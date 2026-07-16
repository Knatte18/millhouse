All 3 of 3 cards committed, matching the batch file's three `## Cards` entries (Card 6, Card 7, Card 8). Verify passed (24 tests, all PASS). Working tree is clean with no uncommitted tracked changes.

Summary of changes:
- `plugins/mill/scripts/_daemon.py` — Card 6: wrapped `json.loads(msg_text)` in `_handle_connection` with its own `try/except json.JSONDecodeError`, logging at `debug` (with payload length) and returning early without a response; the outer `except Exception` still handles every other failure at `error` severity unchanged.
- `plugins/mill/unit_tests/test-wiki-daemon.py` — Card 7: added blocks (w) and (x) covering empty-payload and malformed-nonempty-payload connections, asserting no `sendall`, connection still closed, `debug` logged, `error` not logged.
- `plugins/mill/scripts/wiki/_client.py` — Card 8: removed the redundant bare-connect `socket.create_connection(...); sock.close()` probe in `_ensure_daemon`'s non-stale-state branch and the now-unreachable outer `except OSError:` wrapper, preserving the `_is_stale`/unlink cleanup at the end of the un-nested block. `import socket` remains (still used by `wait_for_socket_reachable` and `_is_stale`).

{"status":"success","commit_sha":"eed505d9","session_id":"36127d0b-5b1b-422f-b910-7753d8c7206f"}
