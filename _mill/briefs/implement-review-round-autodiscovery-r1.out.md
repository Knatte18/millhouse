Excellent! The batch is complete. All cards have been implemented and the verify command passed successfully. Here's a summary of the work done:

## Implementation Summary

I successfully implemented all three cards in the review-round-autodiscovery batch:

### Card 5: Auto-discover round in millpy-review-plan.py finalize
- Added `discover_round` to the imports from `_review_common`
- Replaced the hard-error check `"--round is required for finalize stage"` with conditional auto-discovery using `discover_round()`
- Updated the `--round` argparse help text to indicate auto-discovery in finalize stage
- Replaced all `args.round` references with `round_n` variable in the finalize branch

### Card 6: Auto-discover round in millpy-review-discussion.py finalize
- Added `discover_round` to the imports from `_review_common`
- Replaced the hard-error check with conditional auto-discovery using `discover_round()`
- Updated the `--round` argparse help text to indicate auto-discovery in finalize stage
- Replaced `args.round` with `round_n` variable in the finalize branch

### Card 7: CLI-level tests for --round auto-discovery
- Created `test-review-plan-finalize-round.py` with four test cases:
  1. Plan review finalize with empty reviews_dir → expects round=1
  2. Plan review finalize with existing r1 file → expects round=2
  3. Discussion review finalize with empty reviews_dir → expects round=1
  4. Discussion review finalize with existing r1 file → expects round=2
- Tests verify that `discover_round` is called and the correct `round_n` is passed to the finalize functions

### Verification
All 4 test cases passed successfully.

{"status":"success","commit_sha":"e1a43a0f440b34936b67166058b0a9921c73056d","session_id":"f6e09660-2cc9-418f-bcb8-46471b4b21c5"}