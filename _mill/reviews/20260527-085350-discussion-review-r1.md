# Review: Sub-project repo (hub_relative_path) support

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-27
```

## Findings

### [GAP] resolve_ref_paths callsite inventory is wrong
**Section:** Scope (In) and Technical Context → resolve_ref_paths signature change
**Issue:** Discussion claims 5 `resolve_ref_paths` callsites (3 in `_review_code.py`, 1 in `_review_plan.py`, 1 in `_review_discussion.py`). Grep shows the actual count is 3: `_review_code.py` has 1 (line 254 only — lines 276 and 375 call `resolve_existing_paths`, not `resolve_ref_paths`); `_review_plan.py` has 2 (lines 134 and 470); `_review_discussion.py` has 0. A plan built from this inventory will create phantom tasks for two non-existent `_review_code.py` callsites and may miss the second `_review_plan.py` site.
**Fix:** Correct the callsite count to 3; replace the `_review_code.py` line list (254, 276, 375) with just line 254; replace the single `_review_plan.py` entry with lines 134 and 470; remove `_review_discussion.py` from the list. Also clarify whether `resolve_existing_paths` (which has a similar project-root dependency at lines 276 and 375) needs a matching `git_root` fallback or is intentionally out of scope.

## Verdict

GAPS_FOUND
One callsite inventory error in Scope and Technical Context; all other claims verified against source.