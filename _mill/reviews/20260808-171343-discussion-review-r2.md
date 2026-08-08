MILL_REVIEW_BEGIN
# Review: Unit test suite: hangs, unmocked-path errors, and stuck/success envelope bug found in piecewise sweep

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (best-effort self-assessment)
reviewed_file: _mill/discussion.md
date: 2026-08-08
```

## Findings

### [NOTE] Failing/passing test split in test-millpy-spawn.py not independently re-derivable statically
**Section:** Problem item 3 / Technical context **Issue:** The claimed 9-failing/7-passing split across `test-millpy-spawn.py` cannot be confirmed purely from stub-map naming — some of the ~11 call sites using the `"_wiki"` key (5 via the shared `_run_main_with_mocks` helper, 6 standalone) presumably pass only because they never reach a `wiki._client`-touching code path, which is plausible but unverified statically. **Fix:** No discussion change needed; plan/implementation step should re-run the file to confirm the exact fail/pass count rather than trusting the number as fixed.

## Verdict

APPROVE
All four breakages, three decisions, and cited line numbers verified against source; no gaps found.
MILL_REVIEW_END
