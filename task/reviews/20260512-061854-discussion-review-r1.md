Now I have enough to write the review. The critical finding is that `_cleanliness.is_clean` does not exist — `_cleanliness.py` contains only `capture_snapshot` and `compute_new_dirt`, and a codebase-wide grep confirms zero occurrences of `is_clean`.

# Review: 50 (A) — Bug-fix batch 5 (post-44 triage)

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-12
```

## Findings

### [GAP] `_cleanliness.is_clean` does not exist
**Section:** Technical Context → Shared helpers already in place; Scope → #243; D5
**Issue:** The discussion states "`_cleanliness.is_clean(project_root) -> bool` is the public API (verified via grep)" and builds the #243 fallback around calling it. In reality `_cleanliness.py` contains only `capture_snapshot` and `compute_new_dirt`; a repo-wide grep confirms zero occurrences of `is_clean`. The plan writer inheriting this as fact will write a call to a non-existent function.
**Fix:** Either (a) declare `is_clean` as a new function to be added to `_cleanliness.py` as part of #243 (specify its implementation — likely `git status --porcelain` with no untracked-file exclusions, unlike `compute_new_dirt`), or (b) specify that the fallback calls `compute_new_dirt` against an empty pre-snapshot (or `git status --porcelain` directly) and remove the `is_clean` reference.

## Verdict

GAPS_FOUND
`_cleanliness.is_clean` is cited as existing but is absent from the codebase; the #243 fallback implementation depends on it.