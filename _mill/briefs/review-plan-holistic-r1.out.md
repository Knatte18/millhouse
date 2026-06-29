I have read the overview, both batches, all source files, the test files, and verified the referenced test files exist. Here is my review.

MILL_REVIEW_BEGIN
# Review: Fix prepare-retry atomicity, partial-batch finalize routing, and envelope field parity -- holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-29
```

## Findings

### [NIT] Card 5 threads `_gate_session_id` before it is defined
**Location:** Batch 1 / Card 5 (parsed-success site)
**Issue:** At the parsed-success verify-gate site (`_implementer_common.py` lines 748-757), Card 5 says to thread `_gate_session_id` into `_reclassify_verify_failure`, but `_gate_session_id` is only assigned at line 798 -- a literal implementation NameErrors and crashes finalize.
**Fix:** Instruct the card to hoist the `_gate_session_id = session_id or parsed.get("session_id")` assignment above the `_run_verify_gates(...)` call (or inline that expression at the reclassify call).

### [NIT] Card 7 leaves the primary #570 path (parsed-success) untested
**Location:** Batch 1 / Card 7 (a)-(c)
**Issue:** All partial/zero/complete reclassification cases use non-JSON "inferred-success" output, exercising only the three inference sites. The parsed-success+verify-fail site -- the canonical case where the implementer self-reports `status:success` on a partial batch -- has no coverage, so the forward-reference defect above (and that site's logic/commit_sha branch) would ship unverified.
**Fix:** Add one Card 7 case feeding JSON `status:success` with a failing `verify_cmd` and `0<content<card_count`, asserting `stuck_type:transient`, `commits_made==content`.

### [NIT] Card 2 names `_is_only_start_batch_commit` without listing its file in Context
**Location:** Batch 1 / Card 2
**Issue:** The requirement references `_is_only_start_batch_commit` (in `_implementer_common.py`) but Context lists only `_subprocess_util.py`; the mention is rationale-only (keep the commit message literal), so no real cold-start exploration is needed.
**Fix:** Either drop the function name from the rationale or add `_implementer_common.py` to Card 2 Context for completeness.

## Verdict

APPROVE
Plan is sound, sequenced, and DAG-consistent; only minor ordering/coverage NITs remain.
MILL_REVIEW_END