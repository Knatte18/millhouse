# Batch: foundation-extract

```yaml
task: '14 (D) — Holistic-fix agent for cross-batch funn (conflicts with 15)'
batch: foundation-extract
number: 1
cards: 3
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Extract `_forward_output()` from `millpy-implement.py` into a new `_implementer_common.py` shared helper, update the import in `millpy-implement.py`, and update `TestForwardOutput` in the test suite to call `_implementer_common._forward_output` directly. This batch produces the shared helper that batch 2 (`holistic-implement`) depends on. No external interface changes — all callers of `_forward_output` via `millpy-implement.main()` are unaffected.

## Cards

### Card 1: Create `_implementer_common.py`

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/scripts/_implementer_common.py`. Add a module-level docstring stating it holds shared helpers for `millpy-implement.py` and `millpy-implement-holistic.py`. Copy `_forward_output(output: str) -> int` verbatim from `millpy-implement.py` (lines 42–58, including its docstring). Imports needed: `import json`, `import re`. No other imports. No `if __name__ == "__main__":` block.
- **Commit:** `refactor(mill): create _implementer_common with _forward_output`

### Card 2: Remove `_forward_output` from `millpy-implement.py`

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/millpy-implement.py`: (1) delete the `_forward_output` function definition (lines 42–58, the function and its docstring); (2) add `from _implementer_common import _forward_output` to the imports block, after the `import _timestamp` line. Both existing call sites (`return _forward_output(output)` at the end of the initial-dispatch branch and the fix-cycle-resume branch) remain unchanged — `_forward_output` is still bound in the module namespace via the `from ... import`.
- **Commit:** `refactor(mill): import _forward_output from _implementer_common in millpy-implement`

### Card 3: Update `TestForwardOutput` to use `_implementer_common` directly

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/unit_tests/test-millpy-implement.py`: (1) add `import _implementer_common` to the imports block (the `scripts/` dir is already on `sys.path` via the `HUB / "plugins" / "mill" / "scripts"` insert); (2) in `TestForwardOutput._call`, change `millpy_implement._forward_output(output)` to `_implementer_common._forward_output(output)`. This makes the test explicitly cover `_implementer_common`, not the re-exported name in `millpy_implement`.
- **Commit:** `test(mill): update TestForwardOutput to call _implementer_common directly`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` — runs the full test suite including `TestForwardOutput` (now explicitly testing `_implementer_common._forward_output`) and `TestMillpyImplement` (regression coverage for the refactored import path in `millpy-implement.py`).
