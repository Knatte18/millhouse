# Batch: llm-rate-limit

```yaml
task: 'review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure'
batch: llm-rate-limit
cards: 3
verify: uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"
depends-on: []
```

## Batch Scope

Adds rate-limit detection to the `_llm_claude` provider wrapper. Closes #93. New `LLMRateLimitError(LLMError)` subclass; new `_scan_rate_limit(stdout) -> bool` helper; restructure of `_invoke` so it parses the captured stdout defensively before deciding which exception to raise on non-zero exit. The new exception takes precedence over `LLMSessionError`. Independent of every other batch — only `_llm_claude.py` and its unit test change. After this batch, callers (`_review_plan.run`, `_review_code.run`) catch `LLMError` (parent class) unchanged; `_invoke`'s typed-exception split is what enables future orchestrators to distinguish throttle from crash.

## Cards

### Card 10: Add `LLMRateLimitError` exception class

- **Reads:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Modifies:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `class LLMRateLimitError(LLMError)` to `_llm_claude.py` directly below `LLMSessionError`. Docstring: `"""Raised when the claude CLI exits non-zero AND stream-json indicates a rate-limit/throttle event. Backends record verdict: ERROR with error: 'rate_limit: ...' and the orchestrator's ERROR-only retry handles it. Inherits from LLMError so existing catch sites continue to handle it as a generic provider failure unless they specifically want the typed split."""`. Update the module-docstring's public-API list to include `LLMRateLimitError`. In `test-llm-claude.py`: import `LLMRateLimitError`; add an assertion block proving the class exists, subclasses `LLMError`, and that `raise LLMRateLimitError("throttled"); except LLMError as e: ...` works (parallel to the existing LLMSessionError test).
- **Commit:** `feat(llm-claude): add LLMRateLimitError exception class`

### Card 11: Add `_scan_rate_limit(stdout)` helper

- **Reads:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Modifies:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** TDD-first. Add `_scan_rate_limit(stdout: str) -> bool` to `_llm_claude.py` near `_parse_stream_json`. Iterate `stdout.splitlines()`, JSON-parse each line defensively (skip un-parseable lines without raising). Return `True` when ANY of: (a) any event has `type == "rate_limit_event"` (top-level type field); (b) any event has `type == "result"` AND `is_error == True` AND a rate-limit signal — defined as `subtype` containing `"rate"` (case-insensitive) OR the lowercased JSON-stringified event body containing the substring `"rate_limit"`. Return `False` for empty stdout, all-good results, or generic non-rate-limit errors. The helper does not raise. Tests-first in `test-llm-claude.py`: rate_limit_event line → `True`; `result` event with `is_error: true` and `subtype: "rate_limited"` → `True`; `result` event with `is_error: true` and a generic subtype like `"error_during_execution"` and no rate-limit string → `False`; empty stdout → `False`; one un-parseable line followed by a rate_limit_event line → `True` (defensive parse skips the bad line and finds the good one); one un-parseable line followed by a generic result error → `False`.
- **Commit:** `feat(llm-claude): add _scan_rate_limit helper`

### Card 12: Restructure `_invoke` to raise `LLMRateLimitError`

- **Reads:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Modifies:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_invoke`, after `result = _subprocess_util.run(...)` returns and the duration is logged, BEFORE the existing `if result.returncode != 0:` branch: compute `rate_limited = _scan_rate_limit(result.stdout or "")`. Then in the non-zero branch: if `rate_limited` is `True`, raise `LLMRateLimitError(f"claude rate-limited (exit {result.returncode}): {stderr_snippet}")` — taking precedence over `LLMSessionError` even when `resume=True`. If `rate_limited` is `False` and `resume=True`, raise `LLMSessionError` exactly as today. If `rate_limited` is `False` and `resume=False`, raise `LLMError` exactly as today. Zero-exit path is unchanged (parse stream-json, return `(text, sid)`). Tests-first in `test-llm-claude.py`: monkeypatch (or wrap) `_subprocess_util.run` to return a fake `CompletedProcess` with non-zero exit and a rate-limited stream-json fixture in stdout → assert `LLMRateLimitError` is raised when `_invoke` is called with `resume=False` AND when called with `resume=True`. Non-zero exit + no rate-limit signal + `resume=True` → assert `LLMSessionError`. Non-zero exit + no rate-limit signal + `resume=False` → assert `LLMError` (and that it is NOT `LLMSessionError`). Zero exit → `(text, sid)` tuple unchanged. The fixtures are inline strings; no fake child-process subprocess needs to be spawned. To exercise `_invoke`, call `run_bulk(prompt_text="x", model="m", session_id="abc", resume=...)` after monkeypatching `_subprocess_util.run`.
- **Commit:** `fix(llm-claude): raise LLMRateLimitError on throttle (#93)`

## Batch Tests

Run-all unit tests must pass. `test-llm-claude.py` covers all three cards: class existence, `_scan_rate_limit` cases, `_invoke` integration via `_subprocess_util.run` monkeypatch. The integration test against the real `claude` CLI lives in `integration_tests/` and is not exercised by this batch's `verify:`.
