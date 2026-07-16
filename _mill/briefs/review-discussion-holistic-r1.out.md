MILL_REVIEW_BEGIN
# Review: Batch verify/baseline/completeness gates produce false positives or time out

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-16
```

## Findings

### [GAP] #642 detection signal absent at plan-write time
**Section:** Decisions → go-build-tag-retiering-check
**Issue:** The decision and Testing both key detection off "a diff showing a newly-added `//go:build` line," but mill-plan authors the verify command before implementation exists, so no batch diff is available at plan-write time — only card prose.
**Fix:** State what mill-plan actually inspects (card intent vs. deferring the check to a post-implementation/finalize phase where a diff exists), and reconcile that with the diff-based Testing scenario.

### [GAP] #660 gate needs declared card IDs, not just card_count
**Section:** Decisions → completeness-recount-cards-done
**Issue:** The gate must compare `cards_done` "against the batch's declared card IDs," but `_batch_completeness_stuck` today receives only `card_count` (an int; confirmed line 175), and the decision only threads `cards_done` "alongside card_count" — the source/format of the declared card-ID list is never established.
**Fix:** Specify where the declared card-ID set comes from (batch-file parsing) and thread it into the gate, or define set-coverage semantics against something stronger than a bare count.

### [GAP] #650 preflight output/persistence unspecified
**Section:** Decisions → done-gate-baseline-preflight
**Issue:** The module-wide pattern it mirrors (`compute_baseline`) runs in a torn-down transient worktree and caches only a verdict string; a self-capturing done_gate's value is the snapshot *files* it writes, which vanish if run transiently and need a defined persistence location to reach the Handoff run.
**Fix:** State whether the preflight runs in the real worktree vs. transient, where captured snapshots live (committed / gitignored / .scratch), and how the Handoff-time done_gate consumes them.

### [NOTE] #638 code-vs-skill implementation locus ambiguous
**Section:** Technical context / Testing → batch-verify-list-validation
**Issue:** Technical Context calls `mill-review-plan` (an LLM skill) "the natural place" to validate, but Testing prescribes a "unit test" asserting drop behaviour — implying a named Python function that is never identified.
**Fix:** Name the module/function that performs the `git diff main` check so it is unit-testable, or state the validation is skill-prose and adjust the test strategy accordingly.

## Verdict

GAPS_FOUND
Three decisions leave their core detection/comparison/persistence mechanism unspecified for a plan writer.
MILL_REVIEW_END