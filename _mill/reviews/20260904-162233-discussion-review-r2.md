MILL_REVIEW_BEGIN
# Review: Review prompt/output file listings resolve plan-relative paths to absolute before display, instead of keeping them relative

```yaml
duration_s: 161.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (best-effort self-assessment)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [NIT:consistency] Testing §7 misattributes run-holistic site to wrong function
**Demoted-from:** BLOCKING
**Section:** Testing, item 7 (flow-level tests). **Issue:** claims the four canonical sites live in "two different functions (`_review_one_batch` at line 134; `prepare()` at 382-661)", but the run-holistic manifest (line 1045, `batch_list`/`read_list` at 1048-1049) is inline inside `run()` (defined at line 750, step 5 "Holistic"), not inside `prepare()` — verified `_review_plan.py` has `def _review_one_batch` (134), `def prepare` (382), `def finalize` (662), `def run` (750), and line 1045 falls after 750 with no intervening `def`. **Fix:** correct the parenthetical to name three functions (`_review_one_batch`, `prepare()`, `run()`) so the flow-test author targets `run()`'s own dispatch path for site 4 instead of assuming it is reachable through `prepare()`.

## Verdict

APPROVE
Testing §7's function attribution for the run-holistic flow-test site is factually wrong and undermines its own missed-call-site safeguard.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
