# Batch: worktree-locked-error

```yaml
task: '20 (A) — mill UX-fixes: teardown + spawn-integration'
batch: worktree-locked-error
cards: 3
verify: python plugins/mill/unit_tests/test-worktree.py
depends-on: []
```

## Batch Scope

Adds `WorktreeLockedError(WorktreeError)` to `_worktree.py` and updates `remove_safe` to raise it instead of the base `WorktreeError` when the removal fails due to an NTFS CWD lock or `PermissionError`. Updates `mill-merge/SKILL.md` Step 8 so that `WorktreeLockedError` triggers a "print + skip + continue" path instead of halting. Adds unit tests for all new error paths.

No external interface change — `WorktreeLockedError` is a subclass of `WorktreeError`, so existing callers that catch the base class are unaffected.

## Cards

### Card 1: Add WorktreeLockedError and update remove_safe

- **Reads:**
  - `plugins/mill/scripts/_worktree.py`
- **Modifies:**
  - `plugins/mill/scripts/_worktree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Add `WorktreeLockedError(WorktreeError)` class immediately after `WorktreeError`. Docstring: `"Raised when a worktree directory cannot be removed because it is in use (NTFS CWD lock or PermissionError)."`.
  2. Update the module-level docstring Public API list to include `WorktreeLockedError`.
  3. In `remove_safe`, after computing `long_path_marker` (current line ~248), add a lock-pattern check BEFORE the `if not long_path_marker` guard. Detection strings: `"Permission denied"`, `"is in use"`, `"Access is denied"`. If any match: `raise WorktreeLockedError(f"worktree is locked (path={path}): {stderr!r}")`. Note: do NOT add `"cannot remove"` — that is git's own worktree-lock message (different scenario).
  4. In the long-path fallback block, wrap the `shutil.rmtree(str(path), ignore_errors=False)` call in `try/except PermissionError as exc: raise WorktreeLockedError(f"worktree is locked via rmtree fallback (path={path}): {exc}") from exc`.
  5. The junction-strip (`_junction.strip_all_in_worktree`) runs before either error path — do not move it.
- **Commit:** `fix(_worktree): add WorktreeLockedError for in-use/permission-denied removal failures`

### Card 2: Update mill-merge SKILL.md Step 8 error handling

- **Reads:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Modifies:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Replace the entire block starting with `**On \`remove_safe\` raising \`WorktreeError\`:**` through the end of its Markdown table (currently two rows). The replacement is:

  ```
  **On `remove_safe` raising:**

  | Exception | Handling |
  |---|---|
  | `WorktreeLockedError` | Print to stderr: `"[worktree] cannot remove <path>: directory is in use — close this CC session and run:\n    git worktree remove --force <path>\n    git branch -D $CHILD_BRANCH"`. Skip the `git branch -D "$CHILD_BRANCH"` line that follows `remove_safe`. Continue to Step 9. |
  | `WorktreeError` (other) | Halt with the captured error message — do NOT manually run `rmdir` or `rmtree` as a workaround. |
  ```

  `$CHILD_BRANCH` in the printed message refers to the child branch name captured earlier in the mill-merge session (the branch that was being removed). Both commands must appear so the operator can clean up the stale worktree and branch after closing the session.
- **Commit:** `fix(mill-merge): WorktreeLockedError → skip + print manual commands, not halt`

### Card 3: Add WorktreeLockedError unit tests

- **Reads:**
  - `plugins/mill/unit_tests/test-worktree.py`
  - `plugins/mill/scripts/_worktree.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Add `from unittest.mock import patch, MagicMock` to the imports at the top of the test file.
  2. Add `WorktreeLockedError, remove_safe` to the `from _worktree import ...` line.
  3. Add the following test cases inside `main()`, after the existing tests:

     **Test: WorktreeLockedError is a WorktreeError subclass.**
     `assert issubclass(WorktreeLockedError, WorktreeError)`. Print `"PASS: WorktreeLockedError is WorktreeError subclass"`.

     **Test: remove_safe raises WorktreeLockedError on "Permission denied" in git stderr.**
     Use `tempfile.TemporaryDirectory`. Create real dirs for `path` and `cwd`. Build a `MagicMock` result with `returncode=1`, `stderr="fatal: Permission denied"`. Patch `_worktree._subprocess_util.run` to return it (use `patch('_worktree._subprocess_util.run', return_value=mock_result)`). Call `remove_safe(path, cwd=cwd, junctions_cfg={})`. Assert `WorktreeLockedError` is raised. Print `"PASS: remove_safe raises WorktreeLockedError on Permission denied"`.

     **Test: remove_safe raises WorktreeLockedError on "is in use" in git stderr.**
     Same structure, `stderr="fatal: is in use"`. Assert `WorktreeLockedError` raised. Print `"PASS: remove_safe raises WorktreeLockedError on is in use"`.

     **Test: remove_safe raises base WorktreeError (not subclass) for unrecognized git errors.**
     `stderr="fatal: some unknown error"` (no lock-pattern match). Assert `WorktreeError` is raised AND `not isinstance(exc, WorktreeLockedError)`. Print `"PASS: remove_safe raises WorktreeError (not locked) for unrecognized error"`.

     **Test: remove_safe raises WorktreeLockedError when shutil.rmtree raises PermissionError (long-path fallback).**
     Patch `_worktree._subprocess_util.run` to return `returncode=1`, `stderr="Filename too long"` (triggers the long-path branch). Patch `_worktree.shutil.rmtree` with `side_effect=PermissionError("locked")`. Assert `WorktreeLockedError` is raised. Print `"PASS: remove_safe raises WorktreeLockedError when rmtree fallback raises PermissionError"`.

  All five tests must be inside the outer `try/except AssertionError` block in `main()` so a failure is caught and surfaced like the existing tests.
- **Commit:** `test(_worktree): add WorktreeLockedError and remove_safe unit tests`

## Batch Tests

`verify: python plugins/mill/unit_tests/test-worktree.py` runs all tests in that file. After this batch, the five new tests (subclass check, two locked-git-stderr cases, unrecognized-error regression, rmtree-PermissionError) plus the four existing tests (copy_millhouse, list_worktrees x3, remove) must all pass.
