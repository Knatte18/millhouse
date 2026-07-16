MILL_REVIEW_BEGIN
# Review: Batch verify/baseline/completeness gates produce false positives or time out

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-16
```

Verified against source: `_implementer_common.py` line refs (`_reclassify_verify_failure`:102, `_batch_completeness_stuck`:172, short-circuit:215, `content==0` logic branch:140), `millpy-implement.py` card regex:368, `_plan_validate.py` `_check_verify_*` family (1218/1305/1375/1440), `_verify_baseline.compute_baseline`:70, and SKILL.md sites (timeout note:157, Pre-done gate:771-798, Wiki:199 / Baseline pre-flight:219). All claims accurate. The `content==0` + full-`cards_done` interaction I probed is already guarded upstream by the independent no-content-commit gate (`_implementer_common.py`:1036-1071), so `cards_done` cannot pass a zero-commit success — a real concern, but already covered.

## Findings

### [NOTE] cards_done int-vs-string JSON coercion unspecified
**Section:** Decisions -> completeness-recount-cards-done (#660)
**Issue:** The gate computes `card_ids(set[int]) - set(cards_done)`; a model that emits `cards_done` as JSON strings (`["7","8"]`) yields a non-empty difference and a false `incomplete`, defeating the fix and the `already_complete` backstop derived from the same field.
**Fix:** State that `cards_done` entries are coerced/validated to `int` before the set comparison (or the comparison normalizes both sides).

### [NOTE] "affected package(s)" resolution not stated for the retiering gate
**Section:** Decisions -> go-build-tag-retiering-check (#642)
**Issue:** The compile check runs "over the affected package(s)" but the mapping from a changed `.go` file to its `go build ./<pkg>/...` target is left implicit.
**Fix:** One line naming the mechanism (e.g. the package directory of each transitioned file) so the plan writer and test fixtures agree.

## Verdict

APPROVE
Plan-ready: every decision has rationale, rejected alternatives, locus, and named tests; NOTEs are non-blocking.
MILL_REVIEW_END
