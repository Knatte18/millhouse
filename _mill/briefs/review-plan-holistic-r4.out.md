MILL_REVIEW_BEGIN
# Review: _plan_validate context-completeness: further false-positive/false-negative gaps, round 3 — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-23
```

## Findings

### [BLOCKING:design] Card 6's run-boundary rule still lets a dangling backtick bridge into a fence delimiter
**Location:** batch 01, Card 6, Step 1 + Step 3.
**Issue:** Step 1 says a line is quoted only when `in_fence` is `True` on entry OR it starts with `>`, with the fence toggle "evaluated on the line's CURRENT state, exactly as today" — meaning the *opening* ` ``` ` delimiter line itself is non-quoted and gets appended to the preceding run (verified against `_plan_validate.py`'s current per-line loop, lines 2825-2829, which the docstring explicitly says this mirrors). Step 3 then runs `backtick_re.finditer(joined_text)` once over that whole run, including the delimiter line's own literal ``` ``` ``` text. A dangling, never-closed backtick on the line immediately before the fence can therefore still pair with the *first* backtick character of the fence delimiter itself (three backticks in `` ```yaml `` provide a valid closing partner for `` `([^`]+)` ``), producing a real match that spans from the dangling backtick through to the fence line — silently swallowing any trailing dependency text on the dangling-backtick's own line into the match's captured group. This is exactly the corruption class the refactor exists to close, just relocated to a fence boundary instead of an ordinary line wrap, and it contradicts the card's own stated invariant ("a quoted region always starts a new run, so a backtick match can never span across one") — the delimiter line is not actually quoted at the point it's added to the run.
**Why the new test won't catch it:** the specified regression test `test_check_context_completeness_clean_line_join_dangling_backtick_before_fence_not_bridged` places nothing but the dangling backtick at the very end of its line, so the accidental cross-line match's captured group is just a bare `"\n"`, which fails `_symbol_candidate_shape`'s shape gate and is silently dropped — the test will pass while the underlying bridging still occurs. A dangling backtick followed by trailing prose (or a real path-looking token) before the newline, immediately preceding a fence, is not covered by any specified card-6 test and would demonstrate a real false negative (or corrupted token) under the given algorithm.
**Fix:** Treat any line whose lstripped form starts with the triple-backtick marker as quoted for run-membership purposes on both the opening and closing side (i.e., never append a fence-delimiter line itself to `current_run`), so its own backtick characters can never enter a run's `joined_text`. Add a test where the dangling-backtick line carries trailing text (or a genuine dependency token) between the backtick and the fence to prove the fix, rather than only the degenerate empty-capture case.

## Verdict

REQUEST_CHANGES
Card 6's fence-boundary run construction has a latent backtick-bridging gap its own new test can't detect.
MILL_REVIEW_END
