# Batch: llm-claude-keepalive-integration

```yaml
task: Keep psmux TUI alive across calls for session continuity
batch: llm-claude-keepalive-integration
number: 3
cards: 4
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-llm-claude.py
depends-on: [1, 2]
```

## Batch Scope

Wires `_llm_claude` to drive the keepalive primitives the wrapper now exposes. `_build_psmux_argv` gains two parameters and emits `--psmux-session mill-<id12>` and `--keep-alive` when called for them. `_invoke()`'s psmux branch (a) drops the early `if resume: raise LLMError(...)` guard, (b) distinguishes a caller-provided `session_id` from the auto-generated one, (c) derives the psmux name and passes the new flags accordingly, and (d) maps a non-zero wrapper exit to `LLMSessionError` iff `resume=True` else plain `LLMError`. A new public helper `cleanup_session(session_id)` is added for mill-go (batch 4) to call after each logical session ends. Updates `test-llm-claude.py` per K1–K5 (rewrites the existing Test 6).

External interface for batch 4: `cleanup_session(session_id: str | None) -> None` is a no-op when `session_id` is None or empty, otherwise derives `mill-{session_id[:12]}`, queries `_psmux.list_sessions()`, and calls `_psmux.kill_session()` if the derived name is present. Never raises — swallows `PsmuxError` from either psmux call so callers do not need their own try-wrap. Returns None.

## Cards

### Card 8: extend `_build_psmux_argv` with keep_alive / psmux_session_name

- **Context:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/_llm_claude.py`, change the signature of `_build_psmux_argv` from `(model, effort, allowed_tools, session_id)` to `(model: str, effort: str | None, allowed_tools: str, session_id: str, *, psmux_session_name: str | None = None, keep_alive: bool = False) -> list[str]`. In the body, after the existing `--session-id <session_id>` append, add: `if psmux_session_name is not None: argv += ["--psmux-session", psmux_session_name]` and `if keep_alive: argv += ["--keep-alive"]`. Update the docstring to mention the two new keyword-only args. Do not change the existing positional args, the `mode` derivation, or the unsupported-mode `LLMError`.
- **Commit:** `_llm_claude: thread psmux_session_name and keep_alive through _build_psmux_argv`

### Card 9: rewire `_invoke()` psmux branch (drop resume guard, derive name iff caller-provided, map error)

- **Context:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
  - `plugins/mill/scripts/_psmux.py`
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_llm_claude._invoke()`, locate the `if _get_via_psmux_flag():` block. Make the following structural changes inside that block, in order: (a) delete the existing `if resume: raise LLMError("psmux path does not support session resume; turn off via_psmux for resume flows")` lines. (b) Capture the original argument before auto-generation: replace the line `if session_id is None: session_id = str(uuid.uuid4())` with `caller_provided_session_id = session_id is not None` followed by `if session_id is None: session_id = str(uuid.uuid4())` (the auto-gen path still runs; we just remember whether the caller chose the id). (c) Immediately above the `argv = _build_psmux_argv(...)` call, derive `psmux_name = f"mill-{session_id[:12]}" if caller_provided_session_id else None`. Both new wrapper flags gate on the same `caller_provided_session_id` boolean: the auto-generated path passes `psmux_session_name=None` so the wrapper falls back to its existing `mill-<uuid8>` auto-name, and `--keep-alive` is also omitted — net behaviour for the auto-gen path is bit-for-bit identical to today's one-shot tear-down. This refines the "psmux-session-name derivation" Shared Decision in 00-overview.md: the deterministic `mill-{session_id[:12]}` name applies only when the caller chose the session_id (the only branch where `psmux ls` debuggability matters, because the session survives across calls). (d) Update the call to `argv = _build_psmux_argv(model, effort, allowed_tools, session_id, psmux_session_name=psmux_name, keep_alive=caller_provided_session_id)`. (e) Replace the existing `if result.returncode != 0: raise LLMError(...)` block (the lines `error_detail = (result.stderr or result.stdout or "")[:500]; raise LLMError(f"psmux-claude exited {result.returncode}: {error_detail}")`) with the two-branch form: build `error_detail` the same way, then `if resume: raise LLMSessionError(f"psmux-claude (session {session_id[:8]}...) exited {result.returncode}: {error_detail}")` else `raise LLMError(f"psmux-claude (session {session_id[:8]}...) exited {result.returncode}: {error_detail}")`. The wrapper has no `--resume` flag — psmux-path resume works via session-name reuse — so the error message must not imply otherwise; the `(session <id8>...)` prefix gives operators the same debug pointer without misrepresenting the wrapper interface. ASCII-only: literal `...` (three dots), not the unicode ellipsis. Leave everything else in the block (psmux check, timeout handling, log lines, success-path stdout rstrip + sid_log + return) unchanged.
- **Commit:** `_llm_claude: support resume on psmux path; derive psmux name; map LLMSessionError`

### Card 10: add public `cleanup_session(session_id)` helper

- **Context:**
  - `plugins/mill/scripts/_psmux.py`
  - `plugins/mill/scripts/_llm_common.py`
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/_llm_claude.py`, add a new public module-level function inside the `# Public API` section, placed immediately after `run_implementer` (alongside the other three public entry points `run_bulk` / `run_tool_use` / `run_implementer`). Signature: `def cleanup_session(session_id: str | None) -> None:`. Body: `if not session_id: return None`; import `_psmux` locally (mirrors the lazy-import style used by `_get_via_psmux_flag`); `psmux_name = f"mill-{session_id[:12]}"`; wrap the next steps in `try: ... except _psmux.PsmuxError: pass`: call `existing = _psmux.list_sessions()`; `if psmux_name in existing: _psmux.kill_session(psmux_name)`. Add an ASCII-only stderr log line `print(f"[_llm_claude] cleanup_session: killed psmux session {psmux_name}", file=sys.stderr)` immediately after a successful `kill_session` call (inside the `if` and inside the try). Docstring: explain the contract — derives the psmux name from `session_id` using the same `mill-{id[:12]}` rule used by `_invoke`; idempotent; swallows `PsmuxError` so callers do not need their own try-wrap; no-op on falsy `session_id`. Add the function name `"cleanup_session"` to the module-level `__all__` if such a list exists (check first; if not, do not add one). Update the module docstring `Public API:` section to list `cleanup_session()` alongside the existing entries.
- **Commit:** `_llm_claude: add cleanup_session helper for caller-driven psmux reaping`

### Card 11: extend `test-llm-claude.py` with K1–K5 (rewrite Test 6)

- **Context:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_psmux.py`
  - `plugins/mill/scripts/_llm_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/unit_tests/test-llm-claude.py`, extend the `# --- psmux branch tests ---` section. Use the existing `_fake_psmux_run`, `_psmux_captured_argv` helpers and the `_FakePsmuxResult` class already in the file. Rewrite the existing Test 6 — currently asserts that `via_psmux + resume=True` raises `LLMError` before any subprocess call — as new Test K3 (see below). Tests to add (after Test 11, retaining the existing numbering for unchanged tests):
  - **K1 — keepalive argv when caller passes session_id:** `_get_via_psmux_flag=True`, `shutil.which` returns truthy, `_fake_psmux_run` captures argv; call `run_bulk("prompt", model="m", session_id="abc-123-de-fghij-rest")`. Assert `--psmux-session` appears in argv, followed by `mill-abc-123-de-f` (literal first 12 chars `abc-123-de-f`). Assert `--keep-alive` is present. Assert `--session-id abc-123-de-fghij-rest` is preserved.
  - **K2 — no keepalive when session_id=None:** same fixture; call `run_bulk("prompt", model="m")` (no session_id). Assert `--psmux-session` is NOT in argv; assert `--keep-alive` is NOT in argv; assert `--session-id <some-uuid>` IS present (today's behaviour, regression guard).
  - **K3 — resume=True now exercises subprocess and maps LLMSessionError on failure** (replaces existing Test 6): patch `_get_via_psmux_flag=True`, `shutil.which` truthy, `_subprocess_util.run` returns `_FakePsmuxResult(returncode=1, stdout="", stderr="boom")`; call `run_bulk("prompt", model="m", session_id="resume-sid", resume=True)`; assert the call raises `LLMSessionError` (NOT plain `LLMError`); assert subprocess WAS called exactly once (the early-raise guard is gone). Mark this test's comment as "rewritten from former Test 6; psmux path now supports resume per discussion.md decision".
  - **K4 — non-resume failure maps plain LLMError:** same fixture as K3 but `resume=False`, `session_id="abc-explicit"`; assert raises `LLMError` AND `not isinstance(exc, LLMSessionError)`.
  - **K5 — `cleanup_session` behaviour:** import `cleanup_session` from `_llm_claude`. Three sub-cases: (i) patch `_psmux.list_sessions` to return `["mill-abc-123-de-f", "mill-other"]` and `_psmux.kill_session` to a Mock; call `cleanup_session("abc-123-de-fghij-rest")`; assert `kill_session` was called once with `"mill-abc-123-de-f"`. (ii) patch `list_sessions` to return `[]`; call `cleanup_session("not-present-id")`; assert `kill_session` was NOT called and the call returned without raising. (iii) patch `kill_session` to raise `_psmux.PsmuxError("boom")`; call `cleanup_session("id-xx-rest-yy")` so the derived name is `mill-id-xx-rest-y` (the first 12 chars of `id-xx-rest-yy` are `id-xx-rest-y`); patch `list_sessions` to return `["mill-id-xx-rest-y"]` (exact match); assert the call swallows the `PsmuxError` and returns None. Also assert `cleanup_session(None)` and `cleanup_session("")` both return None without touching `_psmux` (patch `list_sessions` to a Mock and assert it was not called).

  Follow the PASS/FAIL print pattern used by the existing psmux-branch tests. Increment the outer `errors` counter on assertion failure. The rewritten Test K3 replaces Test 6; the legacy "psmux path does not support session resume" assertion is removed entirely (that error message no longer exists in `_llm_claude.py` after card 9). Existing Tests 1, 2, 3, 4, 5, 7, 8, 9, 10, 11 must continue to pass without modification — verify locally by reading each one against the new wrapper-argv expectations: Tests 2/3/4/5 do not assert presence-or-absence of the new flags so they remain green; Test 7 and Test 8 still pre-empt subprocess by mocking `shutil.which=None` / `_psmux_fail`; Test 9 still expects no retry; Tests 10/11 are about parsing / SystemExit handling and are untouched by the new code path.
- **Commit:** `unit-tests: cover keepalive argv, error mapping, and cleanup_session`

## Batch Tests

`verify:` re-runs `test-llm-claude.py` end-to-end. The file now contains the original Tests 1–5, 7–11 plus the rewritten K3 (replacing Test 6), K1, K2, K4, K5 (15 tests in total in the psmux-branch section). Beyond `test-llm-claude.py`, this batch does not modify the wrapper or any other source/test file, so `test-claude-sub.py` from batch 2 should keep passing (the wrapper is unchanged); run it as a sanity check during code review but it is not part of this batch's `verify:`.
