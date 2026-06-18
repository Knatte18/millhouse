This confirms my concern. `test-review-plan-flow.py` exercises `plan_run()` and `finalize()` directly (the backend functions), not the CLI `main()` finalize path where the new auto-discovery lives. There are some CLI `main()` tests but they target the `prepare` stage (lines 1240, 1312), not finalize round auto-discovery. The discussion's testing rationale ("tested adequately by the full `run()` path") does not cover the actual code being changed.

I have enough to produce the review. All three fixes are technically sound, well-scoped, with rationale and rejected alternatives for each decision. The one real gap is the testing claim for Fix 3.

MILL_REVIEW_BEGIN
# Review: Fix nested-junction teardown, Windows verify gate in merge-in, and review-plan --round threading

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-18
```

## Findings

### [GAP] Fix 3 test rationale doesn't cover the changed code
**Section:** § Testing — "No new test file needed for `--round` auto-discovery"
**Issue:** The auto-discovery is added at the CLI `main()` finalize branch (millpy-review-plan.py line ~171, millpy-review-discussion.py line ~116), but `test-review-plan-flow.py` exercises the backend `finalize()`/`run()` functions directly — never the CLI arg-defaulting path. The new branch (round_n = discover_round when args.round is None) would be untested.
**Fix:** Either add a CLI-level test invoking `main(["--stage","finalize", ...])` without `--round`, or correct the rationale to acknowledge the gap and justify why CLI-level defaulting needs no coverage.

### [NOTE] Recursive walk PermissionError handling underspecified
**Section:** § Technical context — Fix 1 pseudocode
**Issue:** The brief says to wrap inner `os.scandir` in try/except for `PermissionError`, but does not state whether a denied subdir is skipped silently or logged. A silently-skipped dir containing a live junction would reproduce the original wiki-destruction failure mode.
**Fix:** Specify that PermissionError skips only that subtree and is logged (warn), so an undescendable dir with a junction is at least surfaced rather than swallowed.

### [NOTE] junctions_cfg retained-but-unused on recursive signature
**Section:** § Decisions — recursive walk; § Technical context line 99
**Issue:** Keeping `junctions_cfg` as a dead parameter is reasonable for caller compatibility, but the only caller is `_worktree.remove_safe` (stated as the sole caller). The compatibility argument is thin when there is exactly one in-repo caller.
**Fix:** Optional — note explicitly that the param is kept to avoid touching `remove_safe`'s call signature this round, or drop it; either is fine, just record the intent.

## Verdict

GAPS_FOUND
One testing-coverage gap on the Fix 3 CLI change; fixes are otherwise sound and well-scoped.
MILL_REVIEW_END