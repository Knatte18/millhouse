# Review: 29 (A) — mill-merge-in: delegate konflikter og verify-feil til sub-agent — 03-unit-tests

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 03-unit-tests
date: 2026-05-07
```

## Findings

### [NIT] test_9 argparse exit captured as rc

**Step:** Card 6 — `test_9_missing_mode`
**Issue:** Requirements say "Assert rc == 2 (argparse error)" but argparse calls `sys.exit(2)`, raising `SystemExit`. Using `_run_main([])` won't return 2 — it'll propagate the exception.
**Fix:** Either use `assertRaises(SystemExit)` directly for this test instead of `_run_main`, or note in Requirements that this test deviates from the helper pattern.

## Verdict

APPROVE
One NIT on capturing the argparse SystemExit; all other paths, mocking strategy, and fixture structure are sound.