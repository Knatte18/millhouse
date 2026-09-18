MILL_REVIEW_BEGIN
# Review: _plan_validate.py: subprocess trace noise, batch-oversized TDD cap, unrelated-test-file and fence-unaware parser bugs — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-09-18
```

## Findings

### [NIT:consistency] Card 4 points at a docstring bullet that does not exist
**Location:** batch 1 (plan-validate-fixes), card 4
**Issue:** Requirements instructs updating "the `batch-oversized` bullet under 'Checks performed'" in `_plan_validate.py`'s top-of-file module docstring; verified against `plugins/mill/scripts/_plan_validate.py` lines 15-67 — the "Checks performed (check keys):" list has no `batch-oversized` entry at all (it is only mentioned in `run()`'s own docstring at line 3706, a plain prose summary line, not a bulleted "check — description" entry).
**Fix:** Correct the instruction to either add a new `batch-oversized — ...` bullet to the top docstring's "Checks performed" list, or repoint the update at the `run()` docstring's summary line where `batch-oversized` is actually named.

## Verdict
APPROVE
Plan is thoroughly source-accurate across all nine cards; only a minor nonexistent-docstring-location nit in card 4.
MILL_REVIEW_END
