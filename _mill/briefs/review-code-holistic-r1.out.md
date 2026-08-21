MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: nested-layout config resolution, stale locks, and rollback-target bugs — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-21
```

## Findings

### [NIT:consistency] Card 7 iteration expression deviates from plan's literal text
**Location:** `plugins/mill/scripts/_config.py:304`
**Issue:** Plan specifies `sorted(k for k in stub_data.keys() if k != "hub_relative_path")`; the implemented code reads `sorted(k for k in stub_data if k != "hub_relative_path")` — a trivial, behaviorally-identical rewrite (iterating a dict iterates its keys).
**Fix:** No functional fix needed; if strict literal-text fidelity is desired for future plan-vs-code diffing, align the two forms.

## Verdict

APPROVE
All four batches match plan text/logic exactly across SKILL.md prose, `_parent_branch.py`, `_config.py`, `_review_common.py`, and both test files.
MILL_REVIEW_END
