MILL_REVIEW_BEGIN
# Review: Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: /home/knatte/Code/millhouse/wts/mill-merge-conflict-robustness-gaps/_mill/discussion.md
date: 2026-07-28
```

## Findings

### [GAP] Marker gate can't tell "clean" from "check command itself failed"
**Section:** Decisions/merge-in-marker-verification (#713)
**Issue:** Check 2 flags a problem only via the substring "conflict marker" in output; check 1 only via a filename appearing in `--name-only` output. Verified against `_subprocess_util.run` (default `check=False`, never raises, just returns whatever `returncode`/`stdout` git produced): a git-level failure unrelated to markers (lock contention, transient error, wrong cwd) yields neither signal, so it is indistinguishable from "no problems found." The Decision's own rationale ("rather than treating any nonzero exit as a failure," to dodge `--check`'s whitespace-warning false positives) only reasons about over-triggering, never about this under-triggering direction.
**Fix:** Specify that a nonzero exit from either check not explained by the expected marker/unmerged signal must itself surface as `stuck_type: logic` (or equivalent) rather than silently passing the gate.

### [NOTE] Existing conflicts-mode success tests not addressed by the gate's test plan
**Section:** Testing (merge-in-marker-verification)
**Issue:** `test-millpy-merge-in-subagent.py`'s pre-existing success-path tests (test_1, test_15, test_16, test_17, test_19) run against a non-git `tmp_path` with `_subprocess_util.run` mocked to one constant `return_value`. Once the new gate is wired into both call sites, these tests exercise it too, but Testing only specifies new tests for the gate helper itself, not whether the pre-existing tests need updated mocks/assertions.
**Fix:** State whether these existing tests must be updated to prove the gate actually ran, rather than passing by coincidence because the constant mocked output happens not to trip either check.

## Verdict

GAPS_FOUND
One gap in the #713 marker-gate's handling of check-command failures unrelated to markers.
MILL_REVIEW_END
