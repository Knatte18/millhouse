# Batch: unit-test

```yaml
task: 55 (A) -- Fix hardcoded _mill/ paths and mill-setup junction/config bugs
batch: unit-test
number: 1
cards: 1
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Create `test-resolve-task-path.py` in `plugins/mill/unit_tests/`, covering all five compat scenarios for `_paths.resolve_task_path`. Uses `tempfile.TemporaryDirectory` fixtures; no real git, no real LLM. The test is auto-discovered by `run-all.py` (which globs `test-*.py` in the unit_tests directory). This batch is standalone — no other batch depends on it, and it does not depend on any SKILL.md change.

## Cards

### Card 1: Create test-resolve-task-path.py

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-resolve-task-path.py`
- **Deletes:** none
- **Requirements:** Create a `unittest.TestCase` class `TestResolveTaskPath` with the following five test methods, using `tempfile.TemporaryDirectory` for all file fixtures:
  1. `test_mill_exists_returns_mill`: create `_mill/status.md` inside tmp root → `resolve_task_path(root, "_mill/status.md")` returns the `_mill/` path.
  2. `test_task_compat_fallback`: create `task/status.md` (NOT `_mill/status.md`) → `resolve_task_path(root, "_mill/status.md")` returns the `task/` path.
  3. `test_neither_exists_returns_mill`: no file created → `resolve_task_path(root, "_mill/status.md")` returns `root / "_mill" / "status.md"` (config-canonical default).
  4. `test_both_exist_primary_wins`: create both `_mill/status.md` and `task/status.md` → `resolve_task_path(root, "_mill/status.md")` returns `_mill/` path (primary wins).
  5. `test_non_mill_path_no_fallback`: call `resolve_task_path(root, "custom/status.md")` (no `_mill/` in path) → returns `root / "custom" / "status.md"` with no fallback attempted (i.e., same result regardless of whether `task/status.md` exists).
  Import `resolve_task_path` by inserting `plugins/mill/scripts` onto `sys.path` (pattern from other tests in the directory). Add `if __name__ == "__main__": unittest.main()`.
- **Commit:** `test: add unit test for resolve_task_path compat fallback`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` — discovers and runs all `test-*.py` files in `plugins/mill/unit_tests/`, including the new `test-resolve-task-path.py`. All five test methods must pass.
