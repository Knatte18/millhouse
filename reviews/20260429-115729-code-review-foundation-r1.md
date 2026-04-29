# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — foundation

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: foundation
date: 2026-04-29
```

## Findings

### [NIT] `resolve_active_worktree` leaks `ActiveError` on missing marker

**Location:** `_paths.py` (`resolve_active_worktree` function body, `_active.read_slug` call)
**Issue:** When `container_path/wts/<slug>` exists but `.millhouse/active.slug.md` is absent or malformed, `_active.ActiveError` escapes instead of either declared exception; callers expecting only `ActiveWorktreeNotFound`/`ActiveWorktreeSlugMismatch` would need to catch a third type. The plan's contract and the test suite omit this case entirely.
**Fix:** Wrap the `_active.read_slug` call in a `try/except _active.ActiveError` and re-raise as `ActiveWorktreeNotFound` (directory exists but cannot be confirmed as a valid worktree).

### [NIT] Container-path logic duplicated inside `resolve_worktrees_dir`

**Location:** `_paths.py:resolve_worktrees_dir` template branch (inline `container = ...`)
**Issue:** The `main_root.parent.parent if main_root.parent.name == "wts" else main_root.parent` expression duplicates `resolve_container_path` verbatim; a future change to container detection would need two edits in the same file.
**Fix:** Replace the inline with a call to `resolve_container_path(git_root)` — the function is already defined above and in scope.

## Verdict

APPROVE — two NITs, no BLOCKINGs; all five cards are correctly implemented and tested.