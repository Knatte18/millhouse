MILL_REVIEW_BEGIN
# Review: Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-15
```

## Findings

### [BLOCKING] Card 11 cat-file path needs posix normalization
**Location:** Batch 5 / Card 11 (`base_tracks_task_dir`)
**Issue:** `git cat-file -e <base>:<task_dir-relative>/status.md` requires a repo-root-relative path with forward slashes; computing it via `task_dir.relative_to(worktree)` yields backslashes on Windows, which git rejects, making the helper always return False.
**Fix:** Specify that the worktree-relative path is rendered with `.as_posix()` before building the `<rev>:<path>` pathspec.

### [NIT] Card 8 rename ` -> ` parsing is dead code for the actual data source
**Location:** Batch 4 / Card 8 (`compute_terminal_dirt` pure helper)
**Issue:** The card mandates handling `R  old -> new` by splitting on ` -> `, but `_pygit2_util.status_porcelain` documents (its own docstring) that index renames return only the new path with no ` -> ` separator, so the rename branch never fires here.
**Fix:** Either drop the ` -> ` handling as unreachable given this data source, or note it is defensive-only; `line[3:]` already yields the correct new path.

### [NIT] Card 9 names `_parent_branch.resolve` but `_parent_branch.py` is not in Context
**Location:** Batch 4 / Card 9
**Issue:** Requirements calls `_parent_branch.resolve(status_path, interactive=False)` from a file absent from `Context:`/`Edits:`; strictly this is a context-completeness gap.
**Fix:** Add `plugins/mill/scripts/_parent_branch.py` to Card 9 `Context:` (the inline signature mitigates but the file should be listed).

### [NIT] #470 fix not applied to the second load_config in _review_common.py
**Location:** Batch 2 / Card 2 (scope)
**Issue:** Card 2 fixes only `_config.load_config`'s single-path repo-layer resolution; `_review_common.load_config` (used by mill-go) has the same hub-root-only limitation and still drops container-layout repo overrides.
**Fix:** Confirm scope intentionally excludes `_review_common.load_config`, or extend the fix; otherwise the #470 symptom persists for mill-go-driven reviewer selection.

## Verdict

REQUEST_CHANGES
One Windows path-sep BLOCKER in Card 11; remaining items are minor.
MILL_REVIEW_END