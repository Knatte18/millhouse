MILL_REVIEW_BEGIN
# Review: _plan_validate: context-completeness fires on forbidding/explanatory file mentions

```yaml
duration_s: 229.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-estimate; harness-reported model ID is claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:design] New negation/verb word sets drop "forbid", breaking existing marker
**Section:** Decisions > Prohibition-detection redesign
**Issue:** The enumerated negation words (`do not`, `never`, `must not`, `cannot`, `shall not`, `won't`, bare `not`) and verb words (`touch, change, modify, edit, add, link, read, use, reference, include, update, remove, delete, alter, rename, move, create, write, mention, cite`) contain neither `forbid` nor any negation synonym for it. Verified against `_plan_validate.py:1366-1376`: `forbid` is one of the 9 current `_PROHIBITION_MARKERS`, and `test_check_context_completeness_clean_prohibition_marker` (test-plan-validate.py:1951) asserts `"must forbid touching \`mill-config.yaml\`"` produces zero errors — that sentence has a verb (`touch`) but no word from the new negation set, so under the described redesign it would newly fail. The Testing section explicitly commits to "keep the existing forbid test passing," which the word-set design as specified cannot satisfy.
**Fix:** Add `forbid`/`forbids`/`forbidden` to the negation set (or otherwise special-case it) and state this explicitly in the Decision's word-list enumeration.

### [NIT:scope] Existing-test-coverage count in Testing section is wrong
**Demoted-from:** BLOCKING
**Section:** Testing > Existing coverage baseline / Scope > In
**Issue:** Discussion states "only 1 of 9 — forbid — currently has a test." Verified: `test_check_context_completeness_clean_prohibition_marker_change_modify` (test-plan-validate.py:2411) already exercises `"do not change"` and `"must not modify"` phrasing (covering markers `not change`/`not modify`), so 3 of 9 markers already have coverage. This test is also absent from the "existing coverage baseline (do not regress)" enumeration entirely.
**Fix:** Correct the count and add the omitted test to the baseline list so the refactor doesn't accidentally drop it.

### [NIT:consistency] run() wiring line numbers are swapped
**Section:** Technical context / Scope > Out (#823)
**Issue:** Discussion states "`_check_context_completeness` at line 2726, `_check_verify_full_suite` at line 2739." Verified via grep: it's reversed — `_check_verify_full_suite` call is at 2726, `_check_context_completeness` call is at 2739.
**Fix:** Swap the two line numbers.

### [NIT:design] Line-wide, non-adjacent negation+verb matching raises false-negative risk, undiscussed as a rejected alternative
**Section:** Decisions > Prohibition-detection redesign
**Issue:** The old phrase-tuples required negation+verb as one contiguous substring (implicit adjacency); the new design explicitly drops that ("anywhere on the line ... not positionally adjacent") while also broadening the verb set to very common words (`add`, `use`, `read`, `include`, `write`, `create`). A multi-clause Requirements line naming a genuine dependency alongside an unrelated prohibition clause could now be silently exempted — a worse failure mode (silent Context gap) than the false positives being fixed. One regression test is planned but the tradeoff/rejected-alternative (e.g. adjacency-scoped matching) isn't discussed in the Decision's rationale.
**Fix:** Add a sentence to the Decision's rationale/rejected-alternatives acknowledging this tradeoff and why line-wide (vs. adjacency-scoped) matching was still chosen.

## Verdict

REQUEST_CHANGES
Word-set design breaks the existing "forbid" case and the Testing baseline undercounts existing coverage.
MILL_REVIEW_END
