MILL_REVIEW_BEGIN
# Review: mill-spawn, millpy-implement, _cleanliness, discussion-review: small bugs and inconsistencies

```yaml
duration_s: 227.0
verdict: APPROVE
reviewer_model: sonnet
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-13
```

## Findings

### [NIT:consistency] #812 Testing claim of "existing pattern" is unverified
**Section:** Testing — #812 (`test-review-discussion-flow.py`).
**Issue:** Claims the new template-content assertion is "consistent with this file's existing pattern of asserting on template/prompt structure" — grep of the actual file shows zero references to `render_prompt`, `templates/`, or any prompt-content assertion; `_review_discussion.prepare` is fully mocked in every test (`prompt_text` is a literal `"prompt"` stub), so no such pattern exists today.
**Fix:** Drop or correct the "consistent with existing pattern" framing; the instruction to read `review-discussion.md` and assert the new bullet's presence is still correct and actionable on its own.

## Verdict

APPROVE
All cited line numbers, function signatures, and call sites verified against source; one non-blocking testing-rationale inaccuracy noted.
MILL_REVIEW_END
