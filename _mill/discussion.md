# Discussion: Unhandled exceptions in mill-go orchestration components should degrade gracefully

```yaml
task: Unhandled exceptions in mill-go orchestration components should degrade gracefully
slug: mill-orchestration-crash-hardening
status: discussing
parent: hanf/linux-port-more
```

## Problem

Two unrelated classes of orchestration-support code raise unhandled/noisy exceptions during
ordinary, healthy `mill-go` runs, consolidated from seven closed GitHub issues (#661, #657,
#655, #647, #654, #652, #646):

1. **psmux cleanup crash.** `_llm_claude.cleanup_session()` unconditionally calls
   `_psmux.list_sessions()`, which shells out to the `psmux` binary. Under `llm.claude.dispatch:
   agent` (and `subprocess`), no psmux session is ever created — dispatch never touches psmux —
   and the binary may not even be installed on the machine. Every per-batch cleanup call and
   every holistic-round cleanup call raises `FileNotFoundError`, printing a full Python
   traceback to stderr. This currently happens 5+ times per full mill-go run. It is
   functionally harmless today only because every call site in `mill-go/SKILL.md` wraps the
   invocation in `\|\| true` — a band-aid at the call site rather than a fix in the helper.

2. **wiki daemon JSONDecodeError noise.** The generic daemon base's `_handle_connection`
   (`_daemon.py`, shared by the wiki daemon and reusable by future V3 daemons) logs
   `[wiki] exception in _handle_connection: JSONDecodeError('Expecting value: line 1 column 1
   (char 0)')` at error level on every empty-payload connection. Traced to the actual trigger:
   `wiki/_client.py`'s `_ensure_daemon()` performs a bare TCP reachability probe
   (`socket.create_connection(...)` immediately followed by `sock.close()`, zero bytes sent)
   before its real health-check request. The daemon's `conn.recv()` returns `b""` on that
   probe, so `json.loads("")` raises. It never crashes the daemon (already caught by a generic
   `except Exception`) but logs at error severity for a connection that isn't actually an
   error, and could mask a genuine connection fault under different timing.

Both are graceful-degradation gaps in code that other issues already flagged individually;
this task fixes the two root causes once instead of leaving four more band-aided call sites to
accumulate.

## Scope

**In:**
- `_llm_claude.cleanup_session()`: no-op early-return when the resolved dispatch mode is not
  `"psmux"`.
- `_psmux.list_sessions()`: catch `FileNotFoundError` (missing binary) and treat it the same as
  the existing `"no server running"` case — return `[]`.
- Remove the `\|\| true` band-aids at both `cleanup_session` invocation sites in
  `mill-go/SKILL.md` (per-batch cleanup block, holistic cleanup block) now that the call no
  longer raises under either failure mode.
- `wiki/_client.py`'s `_ensure_daemon()`: remove the redundant bare-connect probe (the
  subsequent `_connect_send_recv` call already performs the connection attempt and raises
  `OSError` on unreachability).
- `_daemon.py`'s `_handle_connection`: distinguish an empty/malformed payload (benign —
  `json.JSONDecodeError` from `json.loads()` on an empty or non-JSON `msg_text`) from a genuine
  handler error. Log the former at a lower severity (or not at all) instead of `error`.

**Out:**
- No audit of other subprocess call sites or daemon implementations beyond these two reported
  bugs — "orchestration components" in the task title refers to these two consolidated bug
  clusters, not a general robustness sweep. If other unguarded-subprocess or unguarded-parse
  sites exist elsewhere, they are not in scope here (file separately if found).
- No change to `_subprocess_util.run`'s general `Popen` exception handling (it already logs a
  spawn breadcrumb and re-raises by design — that behavior is correct and used by many callers
  that *should* see the exception).
- No change to the wiki daemon's auth/token or protocol-version handling.
- No change to `psmux` dispatch mode itself, or to any other `_psmux.py` function
  (`new_session`, `send_keys`, `capture_pane`, etc.) beyond `list_sessions`.

## Decisions

### cleanup_session dispatch-mode gate

- Decision: `cleanup_session(session_id)` resolves the current dispatch mode itself (git_root →
  `_config.load_config(_paths.resolve_hub_path(), git_root)` →
  `_agent_dispatch.resolve_dispatch_mode(cfg)`) and returns immediately, before importing
  `_psmux` or touching `session_id`, when the mode is not `"psmux"`. Reuse the exact
  try/except-wrapped pattern already used by `_get_via_psmux_flag()` in the same file
  (`_llm_claude.py`) — on any exception during resolution (missing config, cwd outside a git
  worktree), fall through to the existing behavior rather than raising, matching that helper's
  "returns False on any error" contract translated to "don't skip cleanup if we can't tell."
- Rationale: matches issue #655's fix suggestion; eliminates the subprocess call entirely for
  the common `agent`/`subprocess` dispatch cases, not just the crash. No signature change to
  `cleanup_session` and no caller changes in `mill-go/SKILL.md` — the check lives inside the
  helper, so every current and future caller is protected.
- Rejected: threading a `cfg`/`dispatch_mode` parameter through `cleanup_session`'s signature
  and both `mill-go/SKILL.md` call sites — more invasive, and the existing
  `_get_via_psmux_flag()` precedent shows self-contained resolution is the file's established
  pattern.

### list_sessions FileNotFoundError handling

- Decision: in `_psmux.list_sessions()`, catch `FileNotFoundError` around the
  `_subprocess_util.run(argv, ...)` call (the same `try` block that already catches
  `PsmuxError` for `"no server running"`) and return `[]`.
- Rationale: defense-in-depth for the case where dispatch mode genuinely is `"psmux"` but the
  binary isn't installed (operator misconfiguration) — degrades cleanly instead of raising a
  raw traceback, consistent with the existing "no server running" → empty-list precedent in the
  same function.
- Rejected: catching `FileNotFoundError` only at the `cleanup_session` call site instead of
  inside `list_sessions` — `list_sessions()` is public API (used elsewhere per its docstring
  "Public API: eight functions... list_sessions"), so fixing it at the source benefits every
  caller, not just `cleanup_session`.

### Remove `|| true` band-aids

- Decision: remove `\|\| true` from both cleanup-block Bash invocations in
  `mill-go/SKILL.md` (`plugins/mill/skills/mill-go/SKILL.md`, per-batch cleanup block and
  holistic cleanup block).
- Rationale: the band-aid existed solely to swallow the now-fixed `FileNotFoundError`; keeping
  it after the fix hides any other unrelated exception at that call site from the operator,
  which is the opposite of "should degrade gracefully" — real errors should surface.
- Rejected: leaving `\|\| true` in place as a permanent safety net — rejected because
  `cleanup_session` is documented as "idempotent and failure-swallowing" internally already; an
  external `\|\| true` duplicates that contract at the shell layer and masks bugs in the
  contract itself.

### Remove the redundant bare-connect probe in `_ensure_daemon`

- Decision: delete the `sock = socket.create_connection((state["host"], state["port"]),
  timeout=0.5); sock.close()` block in `wiki/_client.py:_ensure_daemon()`. The subsequent
  `_connect_send_recv(state["host"], state["port"], req, timeout=1.0)` call already performs an
  equivalent `socket.create_connection` internally and raises `OSError` on failure, which is
  already caught by the surrounding `except OSError: pass`. After removing the probe, the
  outer `try/except OSError` wrapper (that previously existed to catch the bare probe's
  failure) becomes dead code with nothing left inside it that can raise `OSError` before the
  inner try/except already handles it — simplify by removing the now-unreachable outer
  `except OSError:` branch too, keeping only the inner try/except around
  `_connect_send_recv` and the `if _is_stale(state): state_file.unlink(missing_ok=True)`
  fallback reachable from both the inner-except path and (if resolution genuinely can't
  connect at all) preserved via the inner call's own `OSError` handling.
- Rationale: the bare probe is dead weight — it exists only to trigger a reachability check
  that the real request already performs, and its only observable side effect today is
  causing the daemon to log a spurious `JSONDecodeError`. Removing it is a strict
  simplification, not a behavior change to the actual health-check contract (the return value
  and staleness-cleanup behavior of `_ensure_daemon` are unaffected).
- Rejected: keeping the probe and just tolerating the daemon-side log noise — rejected because
  the probe adds a full round-trip TCP connect/close for zero information (the value it would
  provide — "is the port reachable" — is a strict subset of what `_connect_send_recv` already
  answers).
- **Scope note:** two sibling bare-connect probes exist elsewhere in `wiki/_client.py` —
  `wait_for_socket_reachable()` (polls raw reachability right after spawning the daemon, before
  a token exists to send an authenticated request) and `_is_stale()` (checks whether a
  previously-recorded daemon is still alive). Unlike the `_ensure_daemon` probe, neither is
  redundant with an adjacent real request — each is the *only* reachability check in its
  context — so **both remain unchanged**, in scope here only as documented callers that will
  keep hitting the daemon's empty-payload path. This is precisely why the
  `_handle_connection` decision below is not merely defense-in-depth for a hypothetical future
  client: it is required for two other call sites that already exist today.

### `_handle_connection` empty/malformed-payload handling

- Decision: in `_daemon.py:_handle_connection`, wrap the `msg_text = ...; msg =
  json.loads(msg_text)` parse in its own `try/except json.JSONDecodeError`, distinct from the
  existing outer `except Exception` that handles genuine `handle_request` errors. On
  `JSONDecodeError` (covers both a fully empty payload and a malformed/partial one), close the
  connection without attempting to send a response (the client that sent no bytes is not
  waiting for one) and log at `self._logger.debug(...)` instead of `self._logger.error(...)`.
  Leave the outer `except Exception` (covering `handle_request` failures and any other
  unexpected error) logging at `error` level as it does today.
- Rationale: `_daemon.py` is the generic daemon base documented in `CLAUDE.md` as "reusable by
  future V3 modules" — hardening it here benefits every future daemon subclass, not just the
  wiki daemon, and it is defense-in-depth beyond the specific bare-probe trigger being removed
  in `wiki/_client.py` (any other client, present or future, that connects without sending a
  full JSON payload degrades quietly instead of logging at error severity).
- Rejected: fixing only the client-side probe and leaving `_daemon.py` unchanged — rejected
  because the daemon-side fix is the more defensive layer (protects against any empty/malformed
  connection, not just this one known call site) and the task title explicitly calls out
  "orchestration components" degrading gracefully, which favors hardening the reusable base
  over patching one caller.
- Rejected: silencing all exceptions in `_handle_connection` uniformly at debug level —
  rejected because a genuine `handle_request` failure (a real server-side bug) should still be
  visible to the daemon's log at error severity; only the specific "client sent nothing/garbage
  before we could even parse it" case should be downgraded.
- **Response-drop scope note:** today's outer `except Exception` sends a `server_error` reply
  even on a parse failure. The new `JSONDecodeError` branch deliberately drops that reply for
  *both* sub-cases it covers — the fully-empty payload (`msg_text == ""`, from the three
  bare-connect probes: the two documented in the previous decision's scope note, plus any
  probe not yet removed) and a malformed-but-nonempty payload. This is intentional, not an
  oversight to fix later: no known in-repo sender ever transmits malformed-but-nonempty JSON to
  this port — the only senders are well-formed authenticated requests (which parse fine and
  never reach this branch) and the zero-byte reachability probes. A plan writer must not
  restore the old `sendall` inside this new branch on the theory that a "real" malformed client
  might be waiting for a reply; if such a sender is ever identified, that would be a new,
  separate decision.

## Technical context

- `_llm_claude.py` already has the exact pattern needed for the dispatch-mode gate:
  `_get_via_psmux_flag()` (around line 99) does
  `_paths.resolve_git_root(Path.cwd())` → `_config.load_config(_paths.resolve_hub_path(),
  git_root)` → `_agent_dispatch.resolve_dispatch_mode(cfg)` inside a `try/except (Exception,
  SystemExit): return False`. `cleanup_session` (line 525) should follow the same shape.
- `_agent_dispatch.VALID_DISPATCH_MODES = {"subprocess", "psmux", "agent"}` — three modes, not
  two; the gate must check `mode == "psmux"` (or `!= "psmux"` for the early return), not
  `mode == "agent"` as issue #655 phrased it, since `subprocess` mode also never uses psmux.
- `_psmux.list_sessions()` (line 126) already has the exact precedent for the
  `FileNotFoundError` handling: it catches `PsmuxError` and special-cases `"no server
  running"` in the message to return `[]` instead of re-raising. Add `FileNotFoundError` as a
  sibling except clause (or a combined `except (PsmuxError, FileNotFoundError) as e` with a
  branch) returning `[]`.
- `_subprocess_util.run()` (line 40) does not itself catch `FileNotFoundError` from
  `subprocess.Popen` — it logs a breadcrumb (`[subprocess] Popen raised: ...`) and re-raises by
  design (many callers need to see spawn failures). The fix belongs in `_psmux.py`, not
  `_subprocess_util.py`.
- `mill-go/SKILL.md` cleanup-block invocation sites: `plugins/mill/skills/mill-go/SKILL.md`
  around line ~193 (per-batch cleanup block) and ~540 (holistic cleanup block). Both currently
  end the Bash tool call with `\|\| true`.
- `wiki/_client.py:_ensure_daemon()` (around line 606) contains the bare probe inside the
  `else:` branch of the `protocol_version` check, itself inside `if state_file.exists(): if
  state: ...`.
- `_daemon.py:_handle_connection()` (line 131) is the sole definition — no per-daemon override
  exists (`wiki/_server.py`'s `WikiServer` subclasses `DaemonBase` but does not override
  `_handle_connection`, only `handle_request`/`on_start`/`on_stop`). Fixing it here fixes it for
  the wiki daemon and any future `DaemonBase` subclass simultaneously.

## Constraints

No `CONSTRAINTS.md` present at the hub root.

## Testing

- **`_psmux.py` (TDD candidate):** `plugins/mill/unit_tests/test-psmux-driver.py` already
  mocks `_subprocess_util.run` and tests `list_sessions` for normal output, empty output, and
  "no server running". Add a case that makes the mocked `_subprocess_util.run` raise
  `FileNotFoundError` and asserts `list_sessions()` returns `[]` without raising.
- **`_llm_claude.cleanup_session` (TDD candidate):** no existing test file covers
  `cleanup_session` directly (`grep` found none). Add coverage — likely in a new or existing
  `_llm_claude`-focused test file — for: (a) dispatch mode `"agent"` → `cleanup_session` returns
  without importing/calling `_psmux` at all (mock `_psmux` and assert it's never touched, or
  patch `_agent_dispatch.resolve_dispatch_mode` to return `"agent"` and assert no subprocess is
  spawned); (b) dispatch mode `"psmux"` with `_psmux.list_sessions` raising `FileNotFoundError`
  → `cleanup_session` returns cleanly (via the `list_sessions` fix, not a new catch in
  `cleanup_session` itself); (c) existing idempotent/no-op-on-`None`-session_id behavior
  continues to pass.
- **`_daemon.py` (TDD candidate):** `plugins/mill/unit_tests/test-wiki-daemon.py` has a
  `TestDaemon(DaemonBase)` fixture already but no test currently exercises
  `_handle_connection` with a real socket pair. Add a test that opens a connection to a running
  `TestDaemon` instance (or drives `_handle_connection` directly with a mock socket whose
  `recv()` returns `b""` once) and asserts: no exception propagates, the logger records at
  `debug` (not `error`), and the connection is closed without a `sendall` attempt. Add a
  second case with a malformed-but-nonempty payload (e.g. `b"not json"`) to confirm it takes
  the same low-severity path.
- **`wiki/_client.py:_ensure_daemon` :** existing coverage is likely indirect (via
  `test-wiki-client-retry.py` and integration tests) — after removing the bare probe, re-run
  that suite to confirm `_ensure_daemon`'s staleness-cleanup and successful-reconnect paths are
  unaffected (the probe's removal should be behavior-neutral for those tests). No new test is
  required solely for the probe removal since it's a pure simplification with no new branch;
  the `_daemon.py` test above (with a real socket) provides the end-to-end evidence that no
  `JSONDecodeError` is logged for a normal health-check round-trip.
- Follow `mill:python-testing` conventions; unit tests use tempfile/mock fixtures per
  `plugins/mill/unit_tests/` convention (no real git/LLM/psmux processes).

## Q&A log

- **Q:** How should `cleanup_session` stop crashing when `psmux` is absent? **A:** [auto-pick]
  Two-layer fix — dispatch-mode gate in `cleanup_session` (reusing `_get_via_psmux_flag()`'s
  pattern) plus `FileNotFoundError` handling in `list_sessions()`. **Why:** addresses all four
  issues' root causes (three bug reports about the crash, one enhancement about the redundant
  subprocess call), reuses an existing in-file pattern instead of inventing a new one, no
  signature/caller changes needed.
- **Q:** Remove the `\|\| true` band-aids at the two `mill-go/SKILL.md` invocation sites now
  that the root cause is fixed? **A:** [auto-pick] Remove both. **Why:** the band-aid
  compensated for exactly the exception this fix eliminates; retaining it after the fix just
  hides future unrelated bugs at that call site.
- **Q:** Fix scope for the wiki daemon `JSONDecodeError` noise (root cause: bare reachability
  probe in `_ensure_daemon` triggers an empty-payload parse in `_handle_connection`)? **A:**
  [auto-pick] Both — remove the redundant client-side probe and harden `_daemon.py`'s
  `_handle_connection` to log empty/malformed payloads at low severity. **Why:** `_daemon.py`
  is documented as a reusable base for future V3 modules, so hardening it protects against any
  other benign empty connection beyond this one trigger; removing the dead probe eliminates the
  actual cause and simplifies `_ensure_daemon`'s now-unreachable outer `except OSError` branch.
