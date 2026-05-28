# Review: Background worker + shell-metadata edge cases

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-28
```

## Findings

### [NOTE] BaseException test needs to catch propagated exception
**Section:** Testing — `millpy-bg.py` (#365)
**Issue:** The `finally` design lets `KeyboardInterrupt` propagate out of `_worker_main` after writing the sentinel; the described test (call `_worker_main`, then assert log content) will itself be interrupted before the assertion runs unless the test body catches the `BaseException`.
**Fix:** Clarify that the new BaseException test must wrap the `_worker_main` call in `try/except KeyboardInterrupt` (or equivalent `BaseException`) before checking the log — the hand-rolled test style in `test-millpy-bg.py` has no framework-level catch.

## Verdict

APPROVE
All technical claims verified; one test-writing nuance to note but no blocking gaps.