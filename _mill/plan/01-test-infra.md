# Batch: test-infra

```yaml
task: 52 (A) -- Fix unit_tests/run-all destroying wiki during batch verify
batch: test-infra
number: 1
cards: 2
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

This batch delivers the two infrastructure changes required before test migration can happen. Card 1 adds `safe_temp_dir()` to `_test_helpers.py` — the junction-aware temp dir helper that batch 2 imports. Card 2 adds `cwd=HERE` to `run-all.py` so test subprocesses start from the `unit_tests/` directory, which has no NTFS junctions, eliminating the cwd-level junction risk. Together these two changes form a complete fence: even if a test still uses bare `TemporaryDirectory`, its subprocess starts in a junction-free directory. Batch 2 (test-migration) then removes the remaining `TemporaryDirectory` usages in junction-creating tests.

## Cards

### Card 1: Add `safe_temp_dir()` to `_test_helpers.py`

- **Context:**
  - `plugins/mill/scripts/_safe_rmtree.py`
- **Edits:**
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add `import contextlib` to the stdlib imports block (the block starting with `import subprocess` at the top of the file).
  - Add `import tempfile` to the same stdlib imports block.
  - After the existing `import _tasks_md  # noqa: E402` import (which is already after the sys.path setup), add `import _safe_rmtree  # noqa: E402`.
  - After the existing `seed_wiki_config` function, add the following function:

    ```python
    @contextlib.contextmanager
    def safe_temp_dir():
        tmp = Path(tempfile.mkdtemp())
        try:
            yield tmp
        finally:
            _safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)
    ```

  - `safe_temp_dir()` must yield `Path` (not `str`). The `allowed_root=tmp` argument allows `safe_rmtree` to delete the entire temp dir while passing its containment check.
  - No docstring is needed (per project convention: no docstrings unless the why is non-obvious).
  - Update the module docstring's `Public API:` section to list `safe_temp_dir()`: add `    safe_temp_dir() -> ContextManager[Path]` after the `_make_task_worktree` entry.
- **Commit:** `fix(unit-tests): add safe_temp_dir helper to _test_helpers`

### Card 2: Add `cwd=HERE` to `run-all.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/run-all.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `run-all.py`, locate the `subprocess.run(...)` call (currently: `subprocess.run([sys.executable, str(test)], capture_output=False, text=True, env=child_env,)`).
  - Add `cwd=HERE` as a keyword argument. `HERE` is already defined at module level as `Path(__file__).resolve().parent` (the `unit_tests/` directory).
  - The updated call must be: `subprocess.run([sys.executable, str(test)], capture_output=False, text=True, env=child_env, cwd=HERE)`.
  - No other changes to `run-all.py`.
- **Commit:** `fix(unit-tests): set cwd=HERE in run-all.py to isolate test subprocesses from worktree junctions`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` runs the full unit test suite. After this batch, all existing tests must pass. The verify command is run from the worktree root; `run-all.py` itself resolves `HERE` via `__file__`, so cwd at invoke time does not matter.
