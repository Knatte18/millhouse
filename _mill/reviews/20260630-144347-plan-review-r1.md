I have everything I need. Let me compose the review.

Key verification results:
- `run-all.py --only` accepts multiple space-separated basenames (`nargs="+"`), so batch 2's verify is valid.
- The shared-module import pattern (`import _subprocess_util`) means `patch("mill_cleanup._subprocess_util.run")` also intercepts `_pr_state`'s calls, so the three existing test mocks work after the refactor.
- A fourth PR-reap mock exists (`_mock_run_18d`, ~line 1056, gh returncode=1) that the plan does NOT list — but it returns empty stdout and returncode=1, which the new `none` path handles unchanged, so it correctly needs no edit.
- The `cached_task`/`cached_task_description` caching in mill-merge Entry only runs when `phase: done` (SKILL.md lines 56-60); in `pr-pending` re-entry status.md is typically absent.

MILL_REVIEW_BEGIN
# Review: Handle pre-closed and pre-merged PRs gracefully in mill-merge — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-30
```

## Findings

### [BLOCKING] closed route from pr-pending lacks commit-message source
**Location:** Batch 3 / Card 3 — `closed` route
**Issue:** The `closed` route says "proceed with the normal local squash ... continue to Step 1," reaching Step 5's `git commit -m "<cached_task>"`; but `cached_task`/`cached_task_description` are cached only in the Entry phase-gate `phase: done` branch (SKILL.md L56-60), and in a `pr-pending` re-entry status.md is typically absent (finalize already `git rm -r`'d task_dir), so the squash commit message is undefined for the pr-pending+closed path.
**Fix:** Have the `closed` route specify a commit-message fallback (e.g. derive title via `_client.get_task(wiki_path, slug)`) when status.md/`cached_task` is unavailable.

### [NIT] `_paths.resolve_git_root` used in gate snippet, `_paths` not in Context
**Location:** Batch 3 / Card 3 — Context
**Issue:** The gate snippet calls `_paths.resolve_git_root()`, but `_paths.py` is not in `Context:`. Mitigated only because the Edits target (mill-merge/SKILL.md) already uses this identifier.
**Fix:** Note the reliance on the existing in-file `_paths` usage, or add `_paths.py` to Context for explicitness.

## Verdict

REQUEST_CHANGES
Plan is well-grounded; the closed/pr-pending squash needs a defined commit-message source.
MILL_REVIEW_END