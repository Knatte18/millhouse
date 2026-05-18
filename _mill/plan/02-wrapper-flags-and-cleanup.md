# Batch: wrapper-flags-and-cleanup

```yaml
task: Keep psmux TUI alive across calls for session continuity
batch: wrapper-flags-and-cleanup
number: 2
cards: 4
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-claude-sub.py
depends-on: [1]
```

## Batch Scope

Wraps `millpy-claude-sub.py` with the keepalive primitives. Adds two new CLI flags (`--psmux-session NAME`, `--keep-alive`), implements the reuse short-circuit that skips create/launch when a named session already exists and is idle, and refactors cleanup so the success-path kill is gated by `--keep-alive` and the error-path kill is gated by `session_owned_by_us`. Reads the new `reuse_idle_timeout_s` key from the deep-merged config with a module-level default of `10` as the fallback. No callers exercise the new flags yet — `_llm_claude` is updated in batch 3 — so behaviour for one-shot invocations stays bit-for-bit identical to the pre-batch wrapper (regression-guarded by Test S6). All new test coverage lives in the new `test-claude-sub.py` file; `test-llm-claude.py` is untouched in this batch.

External interface for batch 3: the wrapper accepts `--psmux-session NAME` (any string; `_llm_claude` will always pass `mill-{session_id[:12]}`) and `--keep-alive` (presence flag). When both are provided and the named session exists & is idle, the wrapper reuses it; on any wrapper-internal failure the session is left intact iff the wrapper did not create it. Batch-local decision: `_wait_for_marker_in_pane` ("CLAUDE_READY" step) is skipped on the reuse path — the claude binary is already running inside the reused session, so the boot check would never see the marker.

## Cards

### Card 4: add `--psmux-session` and `--keep-alive` argparse flags

- **Context:**
  - `mill-config.yaml`
  - `plugins/mill/scripts/_psmux.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/millpy-claude-sub.py`, extend `_make_parser()`: add `parser.add_argument("--psmux-session", default=None, help="Reuse the named psmux session if it exists; create it under this name if not. Default: auto-generated 'mill-<uuid8>'.")` and `parser.add_argument("--keep-alive", action="store_true", help="On success, leave the psmux session running for reuse by a later call.")`. Inside `main()`, replace the unconditional `session_name = f"mill-{uuid.uuid4().hex[:8]}"` (currently Step 2) with `session_name = args.psmux_session if args.psmux_session is not None else f"mill-{uuid.uuid4().hex[:8]}"`. The begin/end marker generation stays unchanged. Do not yet implement the reuse short-circuit or the cleanup gating — those land in cards 5 and 6; this card adds the flags and the name-source switch only.
- **Commit:** `claude-sub: add --psmux-session and --keep-alive flags`

### Card 5: implement reuse short-circuit when the named session already exists

- **Context:**
  - `mill-config.yaml`
  - `plugins/mill/scripts/_psmux.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-claude-sub.py`, add a module-level constant `REUSE_IDLE_TIMEOUT_S_DEFAULT = 10` (sibling of the existing `BOOT_READY_TIMEOUT_S`). Add a module-private helper `def _resolve_reuse_idle_timeout_s() -> float:` that calls `_paths.resolve_git_root()` and `_config.load_config(git_root, git_root)`, then returns `float(cfg.get("llm", {}).get("claude", {}).get("psmux", {}).get("reuse_idle_timeout_s", REUSE_IDLE_TIMEOUT_S_DEFAULT))`; wrap the load in `try: ... except (Exception, SystemExit): return float(REUSE_IDLE_TIMEOUT_S_DEFAULT)` so a missing/broken config gracefully falls back. In `main()`, after the prompt-file write and inside the existing `try:` block, before the current Step 6 (`_psmux.new_session`): if `args.psmux_session is not None`, call `existing = _psmux.list_sessions()`; if `args.psmux_session in existing`, call `timeout = _resolve_reuse_idle_timeout_s()` then `if not _wait_for_idle_prompt(session_name, timeout): raise RuntimeError(f"cannot reuse psmux session {session_name}: not idle within {int(timeout)}s")`; on success skip directly to Step 10 (paste prompt + Enter). If `args.psmux_session in existing` is false, fall through to the existing Step 6 (`new_session`). Track creation: introduce `session_owned_by_us: bool = False` immediately above the inner `try:` block; set it to `True` on the line immediately after `_psmux.new_session(...)` succeeds; leave it `False` on the reuse short-circuit path. Add an ASCII-only stderr log line `print(f"[millpy-claude-sub] reusing psmux session {session_name}", file=sys.stderr)` immediately before jumping to Step 10. Do not wrap the `_psmux.list_sessions()` call in a try/except — `_psmux.list_sessions()` already swallows the "no psmux server running" failure (`_psmux.py:127-130`) and returns `[]`; any other `PsmuxError` must propagate so the wrapper exits non-zero with a clear stderr line (the outer `except Exception` block already prints it).
- **Commit:** `claude-sub: reuse existing psmux session when --psmux-session names one`

### Card 6: refactor cleanup — gate success kill on --keep-alive, error kill on session_owned_by_us

- **Context:**
  - `plugins/mill/scripts/_psmux.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-claude-sub.py` `main()`, restructure the cleanup logic of the outer `try/except/finally` block. Keep `prompt_path.unlink(missing_ok=True)` in `finally:` (independent of session lifetime). REMOVE the existing `_psmux.kill_session(session_name)` from `finally:`. Replace it with two explicit kills: (a) on the success-return path inside the `try:` block, immediately before `return 0`, add `if not args.keep_alive: _psmux.kill_session(session_name)`; (b) inside the `except Exception as exc:` block, immediately before `return 1`, add `if session_owned_by_us: _psmux.kill_session(session_name)`. Wrap each of those two new `kill_session` calls in `try: ... except _psmux.PsmuxError: pass` so cleanup never masks the original return code. The `session_owned_by_us` flag introduced in card 5 is the gate for the error-path kill — a reused session is never killed by the wrapper. Add ASCII-only stderr log lines `print(f"[millpy-claude-sub] keepalive: leaving psmux session {session_name} running", file=sys.stderr)` in branch (a) when the kill is skipped, and `print(f"[millpy-claude-sub] error cleanup: killed psmux session {session_name}", file=sys.stderr)` in branch (b) when the kill ran.
- **Commit:** `claude-sub: split cleanup into success/error paths gated by ownership`

### Card 7: write `test-claude-sub.py` (S1–S9)

- **Context:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
  - `plugins/mill/scripts/_psmux.py`
  - `plugins/mill/scripts/_psmux_capture.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/unit_tests/test-millpy-bg.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
  - `plugins/mill/unit_tests/_test_cfg.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-claude-sub.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-claude-sub.py` modelled on `test-millpy-bg.py` (argv-driven CLI test pattern) and `test-llm-claude.py` (mocking style). Set `sys.path` to include the scripts dir, import `millpy-claude-sub` as a module (use `importlib.util` since the filename contains a hyphen — see `test-millpy-bg.py` for the pattern). Mock `_psmux.new_session`, `_psmux.set_history_limit`, `_psmux.send_keys`, `_psmux.load_buffer`, `_psmux.paste_buffer`, `_psmux.capture_pane`, `_psmux.list_sessions`, `_psmux.kill_session`, and the module-level functions `_wait_for_marker_in_pane`, `_wait_for_idle_prompt`. Drive `main()` by setting `sys.argv` and feeding stdin via `io.StringIO` patched onto `sys.stdin`. Capture stdout/stderr to assert behaviour. Tests to implement:
  - **S1 — existing-idle short-circuit:** argv contains `--psmux-session existing-idle` (no `--keep-alive`); `list_sessions` returns `["existing-idle"]`; `_wait_for_idle_prompt` returns True; `capture_pane` returns canned text containing the markers (drive via `_psmux_capture.extract_response` mocked to return `"ok"`). Assert `new_session`, `set_history_limit`, and `_wait_for_marker_in_pane` are NOT called; `load_buffer`, `paste_buffer`, and the `Enter` `send_keys` ARE called. `main()` returns 0.
  - **S2 — existing-busy raise:** `--psmux-session existing-busy`; `list_sessions` returns `["existing-busy"]`; `_wait_for_idle_prompt` returns False. Assert `main()` returns 1 and stderr contains `cannot reuse psmux session existing-busy: not idle`.
  - **S3 — reused session not killed on failure:** same setup as S2, plus assert `kill_session` is NOT called (the wrapper did not own the reused session).
  - **S4 — keep-alive true, success path:** `--psmux-session new-name --keep-alive`; `list_sessions` returns `[]` (new session creation path); `_wait_for_idle_prompt` returns True after `new_session`; happy path completes; `_psmux_capture.extract_response` mocked to return `"ok"`. Assert `kill_session` is NOT called; assert the prompt file `unlink` IS called (separate cleanup). `main()` returns 0.
  - **S5 — keep-alive true, error mid-call when wrapper owns session:** `--psmux-session new-name --keep-alive`; `list_sessions` returns `[]`; `new_session` succeeds; `_wait_for_idle_prompt` returns False after the claude-launch `send_keys`. Assert `kill_session` IS called (error-path + `session_owned_by_us` true); `main()` returns 1.
  - **S6 — regression guard, no flags:** no `--psmux-session`, no `--keep-alive`; auto-generated session name `mill-<uuid8>`; happy path. Assert `new_session` runs and `kill_session` runs (today's tear-down behaviour preserved). `main()` returns 0.
  - **S7 — named-but-missing creates with chosen name:** `--psmux-session new-name`; `list_sessions` returns `[]`. Assert `_psmux.new_session(session_name="new-name", ...)` is called with that exact name (not an auto-generated one).
  - **S8 — list_sessions raises PsmuxError:** `--psmux-session any-name`; `_psmux.list_sessions` is patched to raise `_psmux.PsmuxError("psmux broken")`. Assert `new_session` is NOT called; `main()` returns 1; stderr contains `psmux broken`.
  - **S9 — reuse_idle_timeout_s is plumbed from config:** patch `_config.load_config` to return `{"llm": {"claude": {"psmux": {"reuse_idle_timeout_s": 42}}}}`; run the S1 happy path with a side-effect spy on `_wait_for_idle_prompt` that captures the timeout arg; assert the captured timeout equals `42.0`. Then drop the key from the mocked config and assert the captured timeout equals `REUSE_IDLE_TIMEOUT_S_DEFAULT` (10.0). This test does not validate the timing loop itself, only the value-plumbing.

  Follow the print/exit pattern used by `test-llm-claude.py`: increment a local `errors` counter on failures, print `PASS: ...` / `FAIL: ...` lines, return 1 if any error. Use `tempfile.TemporaryDirectory` for any scratch path needs; mock `_paths.resolve_git_root` to that temp dir so the wrapper's `.scratch/` dir resolves inside the temp tree, NOT in the repo's gitignored `.scratch/`. No real psmux invocations; no real claude.
- **Commit:** `unit-tests: add test-claude-sub.py covering reuse / keepalive / cleanup`

## Batch Tests

`verify:` runs `test-claude-sub.py` (newly created). The nine tests S1–S9 collectively cover every new branch added in this batch: flag plumbing (S6, S7), reuse short-circuit (S1, S2, S8, S9), cleanup ownership rules (S3, S4, S5, S6), and config plumbing (S9). `test-llm-claude.py` is not exercised in this batch's verify command because no `_llm_claude` code changes here — it is exercised again in batches 1 and 3 verify lines. If a reviewer wants belt-and-braces, running `python plugins/mill/unit_tests/run-all.py` is the project-wide convention but is not required by this batch's verify.
