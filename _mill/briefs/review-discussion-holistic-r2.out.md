MILL_REVIEW_BEGIN
# Review: Surface reviewer time/tool-call cost + a review-summary command

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:design] run_implementer() shares _invoke(), contradicting "NOT touched"
**Section:** Decisions § "Reviewer-call return contract becomes a small dataclass"
**Issue:** Decision states `_invoke()` itself stops returning a bare `(text, session_id)` tuple and instead returns `ReviewerCallResult`, while separately stating `run_implementer()` is "explicitly NOT touched." Verified in `_llm_claude.py`: `run_bulk()`, `run_tool_use()`, and `run_implementer()` all do `return _invoke(...)` directly (lines 428-437, 462-471, 504-514) — there is no unpacking today. If `_invoke()`'s return type changes, `run_implementer()`'s return value changes automatically unless its body is specifically edited to unwrap the dataclass back into the old 2-tuple, which the Decision never says to do.
**Fix:** State explicitly that `run_implementer()`'s body must unpack `ReviewerCallResult` and return `result.text, result.session_id` (its external contract stays a 2-tuple, but its internal code is NOT actually untouched given the shared `_invoke()` dependency).

## Verdict

REQUEST_CHANGES
One BLOCKING: the dataclass-conversion Decision's "run_implementer NOT touched" claim is inconsistent with `_invoke()`'s shared return-type change.
MILL_REVIEW_END
