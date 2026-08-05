# Batch: self-hosting-detection-helper

```yaml
task: mill-go's one-shot pre-batch-1 baseline can't cover a task's own later per-batch-baseline capability
batch: self-hosting-detection-helper
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-paths.py
depends-on: []
```

## Batch Scope

Adds the one pure-Python building block batch 2 depends on: a helper that
detects whether the current task worktree is millhouse developing itself
(self-hosting), plus its unit test. No orchestration (SKILL.md) changes
happen in this batch — it is deliberately isolated so batch 2 can consume
a tested, working helper rather than developing it inline.

## Cards

### Card 1: Add `_paths.is_self_hosting_task` helper

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new function `is_self_hosting_task(git_root: Path) -> bool` to `plugins/mill/scripts/_paths.py`, placed after `sanitize_filename_component` (the last function in the file, currently ending around line 648). Body: `return (git_root / "plugins" / "mill" / "scripts" / "millpy-implement.py").exists()`. Give it a Google-style docstring matching this file's existing convention (see `sanitize_filename_component`'s docstring immediately above it as the template): one-line summary stating it detects whether `git_root` is a millhouse-developing-millhouse (self-hosting) task worktree, an `Args:` section documenting `git_root`, and a `Returns:` section stating it returns `True` when `git_root/plugins/mill/scripts/millpy-implement.py` exists on disk and `False` otherwise (including when `git_root` does not exist or is a file, not a directory — `Path.exists()` on a nested path under a non-directory returns `False` rather than raising).
- **Commit:** `feat(paths): add is_self_hosting_task helper`

### Card 2: Add `test_is_self_hosting_task` unit test

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new top-level function `test_is_self_hosting_task() -> None` to `plugins/mill/unit_tests/test-paths.py`, following the existing style of `test_resolve_task_path` (line 56) and `test_status_path` (line 137): each case gets its own `with tempfile.TemporaryDirectory() as tmp:` block and ends with a `print("PASS: ...")` line. Cover exactly these three cases:
  1. A tempdir laid out with `plugins/mill/scripts/millpy-implement.py` present (create the parent directories, then write an empty file at that relative path) -> `_paths.is_self_hosting_task(root)` returns `True`.
  2. A tempdir with no such path -> returns `False`.
  3. `git_root` pointing at a plain file (not a directory) -> returns `False`, does not raise.

  Then wire the new test into `main()`'s call sequence: immediately after the existing `test_status_path()` call (currently at line 1103), add a new line `test_is_self_hosting_task()`.
- **Commit:** `test(paths): cover is_self_hosting_task`

## Batch Tests

`test-paths.py` (run directly, its own `main()` drives every `test_*` function including the two new cases added by Card 2) is the sole verify target — it is the file both cards touch, and this batch introduces no other runnable surface.
