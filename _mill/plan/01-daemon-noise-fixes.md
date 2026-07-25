# Batch: daemon-noise-fixes

```yaml
task: "Wiki daemon error-log leak and stale plugin-cache config validation produce misleading noise"
batch: "daemon-noise-fixes"
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-daemon.py
depends-on: []
```

## Batch Scope

This batch delivers all three daemon-side noise fixes from `discussion.md` §Scope-In,
which are decisions that only make sense together (per `daemon-logger-consolidation`'s
rationale: fixing stdio redirection without logger consolidation would make ALL daemon
diagnostics invisible, not just the noisy ones): (1) widen `_handle_connection`'s benign
exception classification from the single `json.loads` line to the whole pre-dispatch
recv/decode region; (2) redirect the spawned daemon's stdout/stderr to `DEVNULL` instead
of inheriting the client's fds; (3) consolidate `DaemonBase`'s connection-level logger
onto `WikiServer`'s existing `"wiki-server"` rotating-file logger via a name-only rename,
and delete the now-dead `logging.basicConfig` call in `DaemonBase.run()`. There is no
external interface change — this batch only changes internal logging/process behavior.
No batch-local decisions beyond `## Shared Decisions` in the overview.

## Cards

### Card 1: Widen `_handle_connection`'s pre-dispatch exception classification

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_daemon.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `DaemonBase._handle_connection` (`_daemon.py:131-179`), restructure
  so that the entire pre-dispatch region — the recv loop (`chunks = []` through
  `msg_text = b"".join(chunks).decode("utf-8")`) and `json.loads(msg_text)` — is wrapped
  in one inner `try` block that catches the tuple `(OSError, json.JSONDecodeError,
  UnicodeDecodeError)` (note `ConnectionResetError`/`BrokenPipeError` are `OSError`
  subclasses, already covered). On catch: log
  `self._logger.debug(f"benign connection error before dispatch: {exc!r}")` and `return`
  immediately — no response is attempted, matching today's empty/malformed-payload
  behavior (the existing `finally: conn.close()` at the outer method level still runs).
  Replace the current narrower `try: msg = json.loads(msg_text) except
  json.JSONDecodeError: ...` block with this wider one; the recv loop itself currently
  has no exception handling at all and must be pulled inside the same inner `try`. Do
  NOT change anything from the token check (`if msg.get("token") != self._token:`)
  onward — that code, together with `self.handle_request(msg)` and the `conn.sendall`
  calls, stays exactly as-is under the existing outer `except Exception as exc:` handler,
  which keeps logging at `self._logger.error(f"exception in _handle_connection: {exc!r}")`
  and attempting the `server_error` response for ANY exception raised from
  `self.handle_request(msg)` onward — including one of the same benign types (e.g. a real
  `OSError` from a git/file failure inside request handling). The classification is by
  source region (pre-dispatch vs. dispatch-and-beyond) first, exception type only narrows
  within the pre-dispatch region.
- **Commit:** `fix(daemon): classify benign connection errors across the whole pre-dispatch region`

### Card 2: Redirect spawned daemon's stdio to DEVNULL

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_spawn_server` (`wiki/_client.py:666-694`), add
  `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL` to both `subprocess.Popen` calls,
  preserving every existing kwarg: the Windows branch's `Popen(launch_cmd, env=env,
  close_fds=True, creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP |
  CREATE_BREAKAWAY_FROM_JOB)` (line 687-692) and the POSIX branch's `Popen(cmd, env=env,
  close_fds=True, start_new_session=True)` (line 694). Do not redirect to a file — the
  daemon-logger-consolidation fix (Card 3) makes the rotating log file the one
  destination for daemon diagnostics, so a second raw-stdio capture file would be
  redundant.
- **Commit:** `fix(wiki-client): redirect spawned daemon stdio to DEVNULL instead of inheriting client fds`

### Card 3: Consolidate daemon connection-level logger onto `wiki-server`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/_server.py`
  - `plugins/mill/scripts/_daemon.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `WikiServer.__init__` (`wiki/_server.py:58`), change
  `super().__init__("wiki", wiki_path / ".wiki-daemon.json", idle_timeout)` to
  `super().__init__("wiki-server", wiki_path / ".wiki-daemon.json", idle_timeout)`. This
  is a rename only — `DaemonBase.__init__` (`_daemon.py:18-31`) sets
  `self._logger = logging.getLogger(self._name)`, and `logging.getLogger(name)` returns
  the same process-wide singleton regardless of construction order, so `self._logger`
  inside `_handle_connection` will now resolve to the identical `Logger` object
  `WikiServer.__init__` configures at lines 64-85 (the `"wiki-server"` logger with its
  `RotatingFileHandler` at `<wiki_path>/.wiki-daemon.log` and `propagate=False`) — no
  `DaemonBase` signature or behavior change beyond the string passed in. Grep-confirmed
  (repo-wide) that no other code references `logging.getLogger("wiki")` by that literal
  name. Then, in `DaemonBase.run()` (`_daemon.py:64-65`), delete the dead-code block:
  ```
  if not logging.root.handlers:
      logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
  ```
  This becomes a no-op once the connection-level logger shares `"wiki-server"`'s
  `propagate=False` handler; `WikiServer` is the only `DaemonBase` subclass that exists,
  and grep confirms nothing else in `wiki/_server.py`'s process makes a bare root-level
  `logging.*` call depending on it.
- **Commit:** `fix(daemon): consolidate connection-level logger onto wiki-server's rotating file handler`

### Card 4: Test coverage for the three daemon noise fixes

- **Context:**
  - `plugins/mill/scripts/_daemon.py`
  - `plugins/mill/scripts/wiki/_server.py`
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-daemon.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add five new cases to `test-wiki-daemon.py`'s flat `main()` function,
  immediately after the existing `(x)` case (after line 683), following the exact
  try/ok()/fail() pattern already used throughout the file:
  1. **Recv-loop benign error → debug, no ERROR, no crash.** Model on `(w)`/`(x)`
     (lines 643-683): build a `TestDaemon`, set `daemon._token = "tok"`, set
     `mock_conn.recv.side_effect = OSError("connection reset")` (raised on the first
     `recv()` call, before `handle_request` is ever entered), patch
     `daemon._logger.debug`/`daemon._logger.error`, call
     `daemon._handle_connection(mock_conn)`, and assert: `mock_conn.sendall` NOT called,
     `mock_conn.close` called, `debug` called, `error` NOT called. This is the recv-loop
     half of the widened pre-dispatch region that `(w)`/`(x)` don't cover (those only
     exercise the `json.loads` line).
  2. **`handle_request` raising a benign type → still ERROR + response attempt.** Build a
     `TestDaemon`, set `daemon._token = "tok"`, set `mock_conn.recv.side_effect =
     [json.dumps({"token": "tok"}).encode("utf-8"), b""]` so the token check passes and
     dispatch is reached, then `patch.object(daemon, "handle_request",
     side_effect=OSError("disk full"))`, patch `daemon._logger.debug`/`error`, call
     `daemon._handle_connection(mock_conn)`, and assert: `mock_conn.sendall` called
     (server_error response attempted), `error` called, `debug` NOT called. Proves the
     benign-type list does not extend past the dispatch boundary.
  3. **`handle_request` raising a non-benign type → ERROR (baseline, unaffected).** Same
     setup as case 2 but `patch.object(daemon, "handle_request",
     side_effect=KeyError("missing"))`; assert the same outcomes (`sendall` called,
     `error` called, `debug` NOT called) — confirms genuine bugs of any type stay visible
     once inside `handle_request`, unchanged by this batch.
  4. **Logger consolidation: connection-level logger reaches the `wiki-server` rotating
     file, not root/stderr.** Model the `WikiServer` construction on the existing `(g)`
     case (lines 177-209: temp `wiki_path` with a `tasks.json` stub, `WIKI_DAEMON_SKIP_GIT`
     popped/restored around construction so the real `RotatingFileHandler` path is
     exercised). After constructing `wiki_server = WikiServer(wiki_path, idle_timeout=1)`,
     assert `wiki_server._logger is wiki_server._log` (same singleton object — proves
     `DaemonBase`'s connection-level logger and `WikiServer`'s business-logic logger are
     now literally the same `Logger`) and `wiki_server._logger.name == "wiki-server"`.
  5. **`_spawn_server` stdio redirection, both platform branches.** In a new case, patch
     `wiki._client.subprocess.Popen` and call `_client._spawn_server(<a Path, no real
     process needs to spawn>)` twice: once with `patch.object(sys, "platform", "linux")`
     forced, asserting the mock was called with a plain `cmd` list (not `launch_cmd`) and
     kwargs including `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
     close_fds=True, start_new_session=True`; once with `patch.object(sys, "platform",
     "win32")` forced, asserting the mock was called with the `cmd /c start ... /B /MIN`
     -prefixed `launch_cmd` list and kwargs including `stdout=subprocess.DEVNULL,
     stderr=subprocess.DEVNULL, close_fds=True, creationflags=...` (creationflags present,
     exact bitmask not asserted). Reset the mock between the two sub-cases. This is a new
     `import subprocess` reference from the test module scope for the `DEVNULL` sentinel
     comparison — `subprocess` is already a stdlib import available to add if not already
     imported in this file.
- **Commit:** `test(daemon): cover pre-dispatch exception classification, logger consolidation, and stdio redirection`

## Batch Tests

`verify:` runs the whole of `plugins/mill/unit_tests/test-wiki-daemon.py` — this is the
single file covering all `DaemonBase`/`WikiServer`/`wiki._client` daemon behavior, and
every card in this batch (1-4) touches only files that file already exercises. No other
test file imports `_daemon.py`, `wiki/_server.py`, or the `_spawn_server` path in
`wiki/_client.py`, so the scope is already minimal without needing `run-all.py --only`.
