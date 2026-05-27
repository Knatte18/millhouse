# Batch: millpy-fix-windows-lock

```yaml
task: V3 wiki adoption follow-up bugs
batch: millpy-fix-windows-lock
number: 4
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Adds Windows file-locking detection inside `millpy-fix.py`'s `LLMError` handler so deterministic infrastructure failures (`WinError 32` "process cannot access the file") emit `stuck_type: verify` instead of `transient`. The existing test `test_llm_error_propagates_as_stuck_transient` stays green because its mock `LLMError("timeout")` does not match the new Windows-lock pattern. New test cases cover both the Windows-lock branch (verify) and ensure the existing generic-error branch (transient) still works. Independent of every other batch; touches only `millpy-fix.py` and `test-millpy-fix.py`.

External interface: none. The `--scope` / `--batch-name` / `--review-file` flags and JSON output shape are unchanged. Only the `stuck_type` value selection changes, and only for the new branch.

Batch-local decisions:

- Detection helper is module-level (`_is_windows_lock_error`) so it is testable as a unit. The existing test file uses `importlib.util` to load `millpy-fix.py` as the `millpy_fix` module; the helper is available as `millpy_fix._is_windows_lock_error` after that load.
- Pattern matching is case-insensitive (`msg.lower()`); the three substrings `"winerror 32"`, `"process cannot access"`, `"being used by another process"` cover the Windows error-message forms emitted by Python's OSError formatter and Win32 directly.
- Reason string passed to the JSON is unchanged from the existing `transient` path — only the `stuck_type` value differs.

## Cards

### Card 11: Add _is_windows_lock_error helper and route to verify in LLMError handler

- **Context:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_llm_common.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add a module-level helper `_is_windows_lock_error(e: Exception) -> bool` to `millpy-fix.py` (place it above `main`, after the imports block). Body: read `cause = getattr(e, "__cause__", None)`; if `isinstance(cause, OSError) and getattr(cause, "winerror", None) == 32`: return `True`. Otherwise: `msg = str(e).lower()`; return `True` if any of the three substrings `"winerror 32"`, `"process cannot access"`, `"being used by another process"` is in `msg`, else `False`.
  - In `main` (`millpy-fix.py:42`), modify the existing `except _llm_claude.LLMError as e` block (`millpy-fix.py:262-265`): before the `print(json.dumps({"status": "stuck", "stuck_type": "transient", ...}))` line, compute `stuck_type = "verify" if _is_windows_lock_error(e) else "transient"` and use `stuck_type` in the JSON dict. Reason string and the stderr print stay unchanged. The function still returns `1`.
- **Commit:** `fix(millpy-fix): route Windows file-locking errors to stuck_type verify (#376)`

### Card 12: Add unit tests for _is_windows_lock_error and LLMError dispatch

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_llm_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add three new `def test_*` methods to the existing `class TestMillpyFix(unittest.TestCase)` in `test-millpy-fix.py`, placed immediately after `test_llm_error_propagates_as_stuck_transient` (`test-millpy-fix.py:313`):
    1. `test_is_windows_lock_error_helper` — call `millpy_fix._is_windows_lock_error` directly with: an `LLMError` whose `str(e)` is `"failed: WinError 32: file in use"` → assert `True`; an `LLMError` whose `str(e)` is `"the process cannot access the file"` → assert `True`; an `LLMError` whose `str(e)` is `"being used by another process"` → assert `True`; an `LLMError` whose `str(e)` is `"timeout after 60s"` → assert `False`; an `LLMError` raised from `OSError` with `winerror=32` (set via `e.__cause__ = OSError(...); e.__cause__.winerror = 32`) → assert `True`; an `LLMError` raised from `OSError` with `winerror=5` (access denied, NOT 32) → assert `False`.
    2. `test_windows_lock_error_routes_to_verify` — patch `millpy_fix._implementer_claude.run` to raise `millpy_fix._llm_claude.LLMError("WinError 32: file in use")`. Call `self._run_main([...])` with the same batch args as the existing transient test. Assert `rc == 1`, `data["status"] == "stuck"`, `data["stuck_type"] == "verify"`, `data["reason"] == "WinError 32: file in use"`.
    3. `test_generic_llm_error_still_routes_to_transient` — sanity regression. Patch `run` to raise `LLMError("timeout")`. Assert `data["stuck_type"] == "transient"`. (Equivalent to the existing `test_llm_error_propagates_as_stuck_transient` but kept as an explicit anti-regression case alongside the new verify test.)
  - All new tests follow the existing class's `_run_main` and `setUp` machinery — copy the call pattern from `test_llm_error_propagates_as_stuck_transient` (`test-millpy-fix.py:313`). No new imports required (`unittest.mock` and `json` are already imported).
- **Commit:** `test(millpy-fix): cover Windows-lock detection and verify-vs-transient routing (#376)`

## Batch Tests

Batch-level `verify:` runs the full unit-test suite. The new tests are inside `class TestMillpyFix(unittest.TestCase)` and are auto-discovered by `unittest.TestLoader` when `run-all.py` invokes `test-millpy-fix.py` as a subprocess. The existing `test_llm_error_propagates_as_stuck_transient` continues to pass because its `LLMError("timeout")` does not contain any of the three Windows-lock substrings.
