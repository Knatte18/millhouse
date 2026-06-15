Excellent! All three cards have been successfully implemented and tested. Here's a summary of what was accomplished:

## Summary

I have successfully implemented all three cards of the ref-path-resolution batch:

### Card 1: resolve_ref_paths — git_root/root/raw as primary
- Modified `resolve_ref_paths()` in `_review_common.py` to reorder resolution candidates
- `git_root/root/raw` is now tried BEFORE `project_root/root/raw` when `git_root` is available and `root` is set
- Falls back to `project_root/root/raw`, then `git_root/raw`, maintaining proper precedence
- Fixes #471 path-doubling issue when cwd is the root subfolder
- Commit: `161c79ec`

### Card 2: resolve_existing_paths — add git_root/root/raw candidate
- Modified `resolve_existing_paths()` in `_review_common.py` to add the missing `git_root/root/raw` candidate
- Previously only tried `git_root/raw` as fallback, now tries `git_root/root/raw` first
- Mirrors the structure from `resolve_ref_paths` for consistency
- Fixes #471 doubling regression (silently drops single-prefixed path instead of doubled path)
- Commit: `dbc48637`

### Card 3: Unit tests for both resolvers
- Added comprehensive test coverage in `test-review-common.py`:
  - Test for `resolve_ref_paths` with cwd==git_root layout (primary candidate verification)
  - Test for `resolve_existing_paths` with cwd==git_root/root layout (#471 doubling regression)
  - Test for git_root=None fallback for both functions
  - Test for wiki/ prefix routing unchanged when git_root is threaded
  - All tests use tempfile fixtures following existing test style
  - Commit: `a6e1cc35`

All commits follow the project style and the verify command passes successfully.

{"status":"success","commit_sha":"a6e1cc354fd2251073482948cfa553bad11b010f","session_id":"c5f9a08a-43a9-4562-a8e6-2f1fd3b5624c"}
