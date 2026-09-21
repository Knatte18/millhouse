# Batch: wiki-daemon-reliability

```yaml
task: "Misc infra/wiki/PR/self-hosting reliability bugs"
batch: wiki-daemon-reliability
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-wiki-health-check.py test-wiki-sync.py test-wiki-daemon.py
depends-on: []
```

## Batch Scope

Fixes two wiki-daemon reliability bugs from `_mill/discussion.md`: #1107 (a fresh-spawn readiness
race in `_ensure_daemon`) and #1103 (diagnosability gaps in `commit_push`'s rebase-failure message
and `_render_and_commit_all`'s silent pre-render pull failure). Both live in `plugins/mill/scripts/wiki/`.
No external interface changes — every fix is internal to the wiki daemon client/server/sync layer;
`_client.health_check`'s public return type and `commit_push`'s exception type are both unchanged.

## Cards

### Card 1: `_ensure_daemon` post-spawn readiness race (#1107)

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/unit_tests/test-wiki-health-check.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `wiki/_client.py`'s `_ensure_daemon`, the post-spawn wait loop currently is:
  ```python
    _spawn_server(wiki_path)

    deadline = time.monotonic() + SPAWN_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(0.1)
        state = _read_state_file()
        if state:
            if wait_for_socket_reachable(state["host"], state["port"], timeout=deadline - time.monotonic()):
                return (state["host"], state["port"], state["token"])

    raise WikiStartupError("daemon did not start within timeout")
  ```
  `wait_for_socket_reachable` only proves the OS-level listen socket accepts a TCP connection, not
  that the daemon's request-handling path is ready to answer — a connection can be accepted into the
  backlog before the server has finished its own startup. Replace the `wait_for_socket_reachable`
  check with an actual health probe, reusing the exact request shape `_ensure_daemon` already builds
  earlier in this same function for the "is an existing daemon still alive" reuse check
  (`req = {FIELD_OP: OP_HEALTH, FIELD_TOKEN: state["token"], "payload": {"liveness_only": True}}`,
  sent via `_connect_send_recv(state["host"], state["port"], req, timeout=1.0)`, catching `OSError`):
  on a caught `OSError` or a response whose `resp.get(FIELD_OK)` is not `True`, keep polling (the
  existing `time.sleep(0.1)` / `deadline` loop) rather than returning immediately; only return
  `(state["host"], state["port"], state["token"])` once the probe itself reports `FIELD_OK: True`.
  The overall `deadline`/`WikiStartupError("daemon did not start within timeout")` timeout behavior
  is unchanged — only the per-iteration readiness check changes from a socket check to a health
  probe. `wait_for_socket_reachable` may become unused after this change; if so, leave it defined
  (it is still part of this module's public-ish surface per other call sites) rather than deleting it
  as an out-of-scope cleanup.
- **Commit:** `fix(wiki): probe daemon health instead of socket reachability after spawn (#1107)`

### Card 2: wiki stale-clone recovery visibility (#1103)

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/_safe_rmtree.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_sync.py`
  - `plugins/mill/scripts/wiki/_server.py`
  - `plugins/mill/unit_tests/test-wiki-sync.py`
  - `plugins/mill/unit_tests/test-wiki-daemon.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Two independent, narrow fixes in the same issue:
  1. In `wiki/_sync.py`'s `commit_push`, the final rebase-failure branch currently raises
     `WikiPushError(f"git pull --rebase failed: {rebase.stderr.strip()!r}")` after the `git rebase
     --abort` call. Extend the message to name the known-working recovery path: state that a
     subsequent `git reset --hard` recovery attempt can fail on Windows with `unable to unlink old
     'tasks.json'` because the wiki daemon itself holds that file open, and that running
     `millpy-wiki-shutdown.py` first releases the daemon's handle before a manual `git reset --hard`
     is attempted. Keep the original `rebase.stderr.strip()!r` content in the message — this is an
     addition, not a replacement.
  2. In `wiki/_server.py`'s `_render_and_commit_all`, the pre-render pull block currently is:
     ```python
        if not skip_git and not skip_push:
            self._store.close()
            try:
                pull(self._wiki_path)
                self._last_pull = time.monotonic()
            except WikiPushError:
                pass
            finally:
                self._store.reload()
     ```
     Change `except WikiPushError: pass` to `except WikiPushError as e:` and print the caught error to
     stderr (ASCII-only, e.g. `print(f"[wiki] pre-render pull failed (continuing with existing local
     state): {e}", file=sys.stderr)`) before falling through — `sys` is already imported in this
     module. The control flow (render/commit proceeds regardless of this pull's outcome) is
     unchanged; only the silence is fixed.
- **Commit:** `fix(wiki): surface stale-clone recovery hint and pre-render pull failures (#1103)`

## Batch Tests

- Card 1: extend `plugins/mill/unit_tests/test-wiki-health-check.py` (the existing `main()`/`ok()`/`fail()`
  harness — see cases `(f1)`/`(f2)` for the exact mocking pattern) with a new case simulating a
  slow-starting daemon: patch `wiki._client._spawn_server`, `wiki._client.wait_for_socket_reachable`
  (forced `True` immediately, so the loop reaches the health-probe check on its very first
  iteration) and `wiki._client._connect_send_recv` with a `side_effect` list returning `{FIELD_OK:
  False}` twice then `{FIELD_OK: True}`; assert `_ensure_daemon` returns successfully only after the
  third probe (i.e. it retried past the two `False` responses within `SPAWN_TIMEOUT` rather than
  raising or returning prematurely on the first one).
- Card 2, sub-fix 1: extend `plugins/mill/unit_tests/test-wiki-sync.py`'s `main()` harness with a new
  case that forces `commit_push`'s rebase-retry path to fail (mock `_run` so the push reports
  `non-fast-forward` and the subsequent `git pull --rebase` reports non-zero) and asserts the raised
  `WikiPushError`'s message contains `millpy-wiki-shutdown.py`.
- Card 2, sub-fix 2: extend `plugins/mill/unit_tests/test-wiki-daemon.py`'s `main()` harness (see the
  existing `(z1)`/`(z2)` cases for the exact `patch("wiki._server.pull", ...)` pattern) with a new
  case where `pull` raises `WikiPushError`, asserting the error text is written to `sys.stderr`
  (patch `sys.stderr` with `io.StringIO()` and check its contents) rather than being silently
  swallowed, and that `_render_and_commit_all` still completes normally afterward (render/commit
  proceed).
