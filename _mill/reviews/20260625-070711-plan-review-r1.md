MILL_REVIEW_BEGIN
# Review: Fix pre-existing unit-test failures, CRLF cleanliness false-positive, and review false-BLOCKING on Go — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-25
```

## Findings

### [NIT] Plan/code prepare tests must bypass the plan validator
**Location:** Batch 1 / Card 2
**Issue:** `millpy-review-plan.py --stage prepare` runs `_plan_validate.run` (lines 127-146) BEFORE calling `prepare`; mirroring the discussion test (which mocks only `_review_*.prepare`) will trip the real validator and the new plan test may exit 1 before the brief is written.
**Fix:** Have the new plan test pass `--skip-validate` or mock `_plan_validate.run`; the code-review prepare path has no validator and needs no change.

### [NIT] Card 10 mock mechanism is under-specified for multi-call rev-parse
**Location:** Batch 3 / Card 10
**Issue:** `_subprocess_util.run` is invoked many times across prepare+finalize (rev-parse, add, commit, status, compute_terminal_dirt); a flat `side_effect` SHA list is order-fragile and may desync the prepare-time `start_sha` from the finalize-time HEAD.
**Fix:** Prefer a callable `side_effect` that inspects the git argv and returns `abc1234` for rev-parse during prepare and a distinct SHA during finalize, rather than a positional list.

## Verdict

APPROVE
Diagnoses verified against source; both NITs are test-wiring details, not plan defects.
MILL_REVIEW_END
