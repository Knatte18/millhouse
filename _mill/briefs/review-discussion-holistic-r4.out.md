Verification complete. All factual claims in the discussion (file paths, line numbers, function signatures, gate behavior, exception hierarchies, SKILL.md dispatch wording, and citations to mill-plan/mill-go) check out against the actual source. Producing the review.

MILL_REVIEW_BEGIN
# Review: Fix discussion review round-cap, daemon cold-start, and nits-only no-op in finalize

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-30
```

## Findings

### [NOTE] `_marker.task_data()`'s second wiki call bypasses the new retry chokepoint
**Section:** Decisions -- "WikiStartupError retry lives in `_marker.slug_from_branch()`"
**Issue:** `task_data()` calls `slug_from_branch()` (gets retry protection) then makes its own separate, unwrapped `wiki.list_tasks_brief(wiki_path)` call at `_marker.py:95`; `_review_common.load_task_title()` (used by `_review_discussion.py`, `_review_plan.py`, `_review_code.py`) only catches `_marker.MarkerError`, not `WikiStartupError`, so this second call is a residual unprotected wiki touch point not covered by the "fixes every caller transparently" rationale.
**Fix:** Either note this as an accepted, narrow exception (the window is effectively zero since the call follows immediately after a just-confirmed-warm daemon) or explicitly extend Scope to also guard `task_data()`'s own `list_tasks_brief` call.

## Verdict

GAPS_FOUND
One residual NOTE-level gap; no GAPs -- all other technical claims verified accurate against source.
MILL_REVIEW_END
