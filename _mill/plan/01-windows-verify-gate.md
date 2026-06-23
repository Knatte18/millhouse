# Batch: windows-verify-gate

```yaml
task: "Fix nit-enforcement gate, Windows verify false-positive, reviewer oscillation, and scope-violation handling"
batch: windows-verify-gate
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-fix.py
depends-on: []
```

## Batch Scope

Fixes #517 — the Windows `go test` temp-cleanup race (`go: unlinkat …\\X.test.exe: Access is denied`) misclassified as `stuck_type: verify`. Introduces a single shared helper `_is_benign_windows_cleanup(output: str) -> bool` in `_implementer_common.py`, applies it inside `_run_verify_gate` (win32-only, guarded by "no test-failure marker"), and refactors `millpy-fix.py`'s `_is_windows_lock_error(e)` to delegate its textual match to the shared helper (the Exception-typed wrapper stays, since it also inspects `__cause__.winerror`). This batch is the root of the `millpy-fix.py` / `test-millpy-fix.py` write-chain (batches 2 and 3 follow). External interface consumed downstream: the `_is_benign_windows_cleanup` helper name and signature.

## Cards

### Card 1: benign-Windows-cleanup helper + apply in verify gate

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `_is_benign_windows_cleanup(output: str) -> bool` to `_implementer_common.py`. It returns `True` only when the combined output contains a Windows cleanup-race signature (case-insensitive any of: `unlinkat`, `access is denied`, `winerror 5`, `winerror 32`) AND contains NO test-failure marker (case-insensitive none of: `fail`, `--- fail`, `panic:`, `build failed`). Modify `_run_verify_gate(project_root, verify_cmd)`: when `result.returncode != 0`, before returning the `stuck/verify` dict, if `sys.platform == "win32"` and `_is_benign_windows_cleanup(result.stdout + result.stderr)` is `True`, treat the verify as success — return `None` (the gate's success sentinel) instead of the stuck dict. Non-win32 behaviour unchanged. Keep all strings ASCII. Reference `_is_windows_lock_error` in `millpy-fix.py` for the existing signature vocabulary to stay consistent.
- **Commit:** `fix(verify): treat win32 cleanup-race exit as success when no test failed`

### Card 2: delegate millpy-fix lock-error match to the shared helper

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Refactor `_is_windows_lock_error(e: Exception) -> bool` in `millpy-fix.py` so its string-signature branch delegates to `_implementer_common._is_benign_windows_cleanup(str(e))` instead of its own inline `["winerror 32", "process cannot access", "being used by another process"]` list. Preserve the structured `__cause__` OSError `winerror == 32` check (it has no string equivalent). Net behaviour: returns `True` for WinError-32 sharing-violation exceptions exactly as before, now via the shared textual matcher. Import the helper at the top of `millpy-fix.py` (it already imports from `_implementer_common`).
- **Commit:** `refactor(fix): delegate windows lock-error text match to shared helper`

### Card 3: tests for the verify-gate win32 path and the delegated helper

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-implementer-common.py`, extend the verify-gate cases (around the existing cases 19-22) to cover: (a) win32 + non-zero exit + cleanup signature (`unlinkat ... Access is denied`) + no FAIL marker → gate returns success (no `stuck/verify`); (b) win32 + cleanup signature BUT a `--- FAIL` line present → stays `stuck/verify` (must not mask a real failure); (c) win32 + ordinary non-zero (no signature) → `stuck/verify`; (d) non-win32 + identical cleanup-signature output → `stuck/verify` (platform gate). Monkeypatch `sys.platform` to drive (a)-(c) vs (d). In `test-millpy-fix.py`, update `test_is_windows_lock_error_helper` so it still passes after the delegation refactor (WinError-32 phrases → True, non-lock message → False, `__cause__` winerror 32 → True, winerror 5 → False).
- **Commit:** `test(verify): cover win32 cleanup-race gate and delegated lock-error helper`

## Batch Tests

`verify:` runs `test-implementer-common.py` and `test-millpy-fix.py` — the two suites whose subjects this batch edits (`_run_verify_gate` + the new helper live in `_implementer_common.py`; `_is_windows_lock_error` lives in `millpy-fix.py`). Scope is the two affected files only, not the full suite. Key scenarios: the four-way win32/non-win32 × signature/FAIL matrix in card 3, and the unchanged lock-error helper contract.
