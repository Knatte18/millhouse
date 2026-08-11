MILL_REVIEW_BEGIN
# Review: Surface reviewer time/tool-call cost + a review-summary command

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; distinct from the dictated reviewer_model)
reviewed_file: _mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:design] Duration-summing fix breaks the fast-fail retry gate
**Section:** Decision "Duration for multi-call rounds: sum across every retry, at every layer" (layer 2, intra-`_invoke()`).
**Issue:** The fix says to compute `dt = time.monotonic() - start` only once, "at the very end of `_invoke()`, after any retry has completed." But the retry-decision condition itself (`result.returncode != 0 and dt < 2.0 and ...`, `_llm_claude.py` line 371, plus the debug print at line 377) runs *before* any retry and needs the *first attempt's own* elapsed time to decide whether to retry at all — deleting the pre-retry `dt` computation as literally described removes the value that gate depends on, since `dt` would not yet exist when line 371 evaluates.
**Fix:** Clarify that a first-attempt timing value is still computed right after the first subprocess call (feeding the retry gate + its print, as today, under whatever name), and a *second*, separate `time.monotonic() - start` call is added after the retry block for the returned cumulative duration — not a single relocated computation as currently phrased.

## Verdict

REQUEST_CHANGES
Layer-2 duration-summing fix as described eliminates the timing value the fast-fail retry gate itself depends on.
MILL_REVIEW_END
