MILL_REVIEW_BEGIN
# Review: mill-go2: fork-based fixer (NIT-fix) dispatch — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; brief specifies "sonnethigh" as the dictated reviewer_model)
reviewed_file: plan/
date: 2026-08-11
```

## Findings

### [BLOCKING:design] Fork-fallback log doesn't reconstruct fork_attempted for the common crash-resume case
**Location:** batch 2, card 4 (`### fixer` override block) / batch 1, card 2 (`append_fork_fallback_log`)
**Issue:** The row is written only "on the first terminal failure classification under the base's step 4" (i.e., only once a fork attempt has already failed and fallen back). If the Builder session crashes while a fork is still in flight — before any failure is ever classified — `read_fork_fallback_log` returns `[]` on resume, `fork_attempted` computes `False`, and mill-go-base's `## Resume` `fixing` branch (which unconditionally re-runs prepare → Agent → finalize, consulting Override point A again) will fork a *second* fixer for the same scope/round against the real worktree. This is exactly the "double-fork-on-resume bug" Shared Decision `fork-fallback-log-is-control-flow-state` says the reader prevents, but the log's write condition doesn't cover this timing.
**Fix:** Either narrow the Decision's claim to "prevents re-forking after an already-recorded fallback" (not general crash-resume double-fork), or have the override additionally log/commit a lightweight "fork dispatched" marker before the Agent call (not just on fallback), so resume can distinguish "never forked" from "forked, outcome unknown."

### [BLOCKING:design] `_check_fork_override`'s assertions don't distinguish scenario 2 of the 5 it claims to catch
**Location:** batch 2, card 3 (`_check_fork_override`)
**Issue:** The card lists 5 scenarios the check must make "distinguishable from the output alone," including "the placeholder `(none)` left in place alongside the override." But the specified mill-go2 assertions only check: body is not `None`, body is not *exactly* `"(none)"`, body contains `fixer`, body contains `subagent_type: "fork"`. If an implementer appends the fixer block below a leftover `(none)` line, the body is no longer exactly `"(none)"` and still contains both literals — every specified assertion passes, so no `FAIL:` is emitted despite the leftover placeholder. The check's coverage claim is false for this one scenario.
**Fix:** Add an explicit assertion that the extracted mill-go2 body does not contain `(none)` as a standalone line/substring once the override is present, and emit a distinct `FAIL:` for it.

## Verdict

REQUEST_CHANGES
Two design gaps: the fork-fallback log doesn't cover the crash-mid-fork case it claims to fix, and the contract check misses one of its five stated scenarios.
MILL_REVIEW_END
