MILL_REVIEW_BEGIN
# Review: mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-09
```

## Findings

### [GAP] --revise has no vehicle for communicating what should change
**Section:** Decisions / `mill-plan-revise-reentry` (#786) **Issue:** The flow only flips `approved: false`/`phase: planning` and re-enters the Plan Review loop "reusing review-execution logic unmodified" (own rationale wording) — there is no mechanism for the operator to state a revision reason, or for that reason to reach the reviewer/planner brief; the loop relies entirely on the reviewer independently re-noticing drift against current source. This under-serves the Problem statement's own motivating case ("plan revision after upstream merges") for any change that isn't something the reviewer would organically re-flag (e.g. operator-directed scope additions). **Fix:** State explicitly whether `--revise` is scoped strictly to "re-review to catch drift" (and document that limitation), or add an optional free-text/reason token threaded into the re-dispatched review brief.

### [GAP] Revision round-namespace has no defined behavior for a second `--revise`
**Section:** Decisions / `mill-plan-revise-reentry` (#786) **Issue:** The namespace is specified only as "`<reviews_dir>/revise-1/` (or similar)" with no rule for what happens on a subsequent `--revise` of the same task after the first revision is re-approved — a fixed literal name collides with (overwrites) the first revision's round files, directly contradicting the decision's own rationale ("keeps the original pass's audit trail completely undisturbed"). **Fix:** Define the subdirectory-naming rule for repeat revisions (e.g. increment `revise-N` via a directory-listing scan analogous to `discover_round`) or explicitly declare only one revision pass is supported per task.

### [NOTE] Technical-context line citation for `git.base_branch` fallback is off
**Section:** Technical context, `mill-merge-status-absent-fallback` (#782) bullet **Issue:** Cites "`mill-merge/SKILL.md` Entry Step 1 (lines 43-48)" for the `cfg.git.base_branch` "main" fallback; the actual "Config keys to read" / `git.base_branch` fallback text is at lines 49-54 (verified by direct read) — lines 43-48 cover the in-place/main-worktree bypass logic instead. **Fix:** Correct the cited line range to 49-54 so a plan writer locating this by line number doesn't land on unrelated text.

## Verdict

GAPS_FOUND
Two GAPs on the `--revise` design (#786): revision-intent channel and repeat-revision namespace collision are unaddressed.
MILL_REVIEW_END
