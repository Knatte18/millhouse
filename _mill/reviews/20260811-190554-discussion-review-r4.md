MILL_REVIEW_BEGIN
# Review: Surface reviewer time/tool-call cost + a review-summary command

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; unverified)
reviewed_file: _mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:design] 4(c) probe-confirmed-dead outcome is a re-dispatch, contradicting the Decision
**Section:** Decisions > "Agent-mode duration across a transient re-dispatch"
**Issue:** The Decision claims 4(c) "is NOT a re-dispatch — there is only ever one `Agent()` call for that attempt." But `mill-go-base/SKILL.md` step 4(c) has two outcomes: probe-says-still-running (single timer, matches the Decision) AND probe-says-no-longer-running-or-errors, which explicitly "proceed[s] to the existing one-retry transient classification from (a) and re-dispatch exactly as today" — a second `Agent()` call, functionally identical to 4(a)'s re-dispatch. The reviewer-only `test -f output_path` shortcut in 4(c) also funnels into this same re-dispatch branch.
**Fix:** Split 4(c) into its two outcomes explicitly: "still running" keeps the single continuous timer (no summation); "confirmed dead / probe error" must sum durations exactly like 4(a), since it triggers the identical re-dispatch code path.

### [BLOCKING:design] Duration lost on the parse_verdict-failure ERROR path, unaddressed by the exception-path Decision
**Section:** Decisions > "Duration on the exception/error path"
**Issue:** This Decision only covers `_invoke()` raising `LLMError`/`LLMSessionError`/`LLMRateLimitError` (a failed call). But each backend (confirmed in `_review_code.py`, `_review_plan.py`, `_review_discussion.py`) has a second `except ReviewError as exc:` branch (e.g. `_review_code.py` lines 697-718, 761-782) reached after a *successful* reviewer call whose `parse_verdict()` then fails — this also builds a synthetic `verdict: "ERROR"` `reviews[...]` entry, but duration is fully known here (the call succeeded) and nothing in the discussion says to carry it through. As written, this path silently drops duration exactly like the case the Decision was written to fix.
**Fix:** Add `except ReviewError` alongside `except LLMError` in the Decision's scope: read the already-available `ReviewerCallResult.duration_s` (not `getattr(exc, ...)`) into this branch's `reviews[...]` entry too.

## Verdict

REQUEST_CHANGES
Two design gaps in the duration-accounting Decisions would silently undercount/drop cost data on real code paths.
MILL_REVIEW_END
