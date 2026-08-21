MILL_REVIEW_BEGIN
# Review: millpy-review-plan: finalize envelope verdict silently diverges from the review file's own written verdict

```yaml
duration_s: 228.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; harness system prompt states "Sonnet 5" / claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Findings

### [BLOCKING:design] Fourth bug's premise is false — the catch site is unreachable
**Section:** Problem (4th bug) / Decision "error_kind misclassification..." / Scope item 2
**Issue:** All three finalize() wrappers already swallow the only ReviewError finalize_scope() can raise (parse_verdict failure) and return `error_kind: "reviewer"` directly, never re-raising — confirmed at `_review_plan.py:712-733`, `_review_discussion.py:206-228`, `_review_code.py:580-608`, each explicitly labeled "reviewer-kind-finalize-wrappers Shared Decision" in existing tests. The CLI-level `except ReviewError` the discussion targets (millpy-review-plan.py:307, -discussion.py:246, -code.py:266) can never be reached by that path in real production code.
**Fix:** Re-verify reachability of the CLI-level catch before scoping this change; drop the item (treat like #864/#867 — already correct) unless a genuine second raise path is found and documented.

### [NIT:consistency] Proposed change contradicts an existing passing test
**Demoted-from:** BLOCKING
**Section:** Technical context / Testing — "error_kind classification"
**Issue:** `test-review-plan-finalize-round.py` cases (e)/(f)/(g) — `review-{plan,discussion,code}-finalize-outer-catch-error-kind-usage` — mock `finalize()` to raise `ReviewError` directly and assert the CLI's outer catch yields `error_kind == "usage"` for all three CLIs; this test is not cited anywhere in the discussion and pins "usage" as the intended value for that exact catch site.
**Fix:** Cite this test in Technical context and reconcile: either explain why it's wrong and must change, or drop the error_kind scope item.

### [NIT:consistency] Wrong file cited as "existing regression home for error_kind"
**Demoted-from:** BLOCKING
**Section:** Technical context — "Existing regression home for error_kind"
**Issue:** `test-review-cli-error-envelope.py` (checked in full) contains zero `error_kind` references — it only covers the exit-code contract (#338: 0/1/0). Actual `error_kind` coverage lives in `test-review-cli.py` (print_error_envelope defaults/overrides) and the finalize()-wrapper-level assertions in `test-review-plan-flow.py`/`test-review-discussion-flow.py`/`test-review-code-flow.py`.
**Fix:** Correct the citation so a plan writer extends the right file(s) instead of adding dead assertions to an unrelated test file.

## Verdict

REQUEST_CHANGES
Fourth-bug scope item rests on a false reachability premise and contradicts an existing passing test.
_Note: 2 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 1._
MILL_REVIEW_END
