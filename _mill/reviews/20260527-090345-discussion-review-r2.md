# Review: Sub-project repo (hub_relative_path) support

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md (round 2)
date: 2026-05-27
```

## Findings

### [NOTE] Stale callsite list in `resolve_ref_paths` Decision
**Section:** `### resolve_ref_paths gains a git_root fallback`
**Issue:** Decision prose says "Update callers in `_review_code.py` (lines 254, 305 area, 375) and `_review_plan.py` / `_review_discussion.py`" — line 305 is `project_root=project_root` inside `_build_artefact_section(...)`, not a callsite; 375 is off-by-one for `resolve_existing_paths` line 374; `_review_discussion.py` has zero callsites of either function (grep-verified).
**Fix:** Remove "305 area" and `_review_discussion.py` from this sentence; the correct list is already accurate in the Technical Context verified-callsite tables.

## Verdict

APPROVE
Discussion is complete and technically sound; one stale callsite reference in Decision prose is low risk given the accurate Technical Context tables.