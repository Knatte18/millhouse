MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: plan/
date: 2026-08-12
```

## Findings

### [BLOCKING:design] Card 9's divergence-halt fixture cannot actually diverge — `--ff-only` will succeed, not fail
**Location:** 04-integration-tests.md, Card 9, "Divergence-halt sub-scenario"
**Issue:** The fixture only advances `parent_ff_halt`'s local `main` by one unpushed commit; `origin_ff_halt/main` is never independently advanced. `git merge --ff-only origin/main` fails only when neither ref is an ancestor of the other (a genuine two-sided divergence). Here `origin/main` is a strict ancestor of local `main`, so git reports "Already up to date." and exits **0** — the opposite of the asserted non-zero exit. As written the test's own assertion (step 4, "Assert this second command exits non-zero") will fail once implemented.
**Fix:** Also push an independent commit to `origin_ff_halt/main` (e.g. via a throwaway `advancer_ff_halt` clone, mirroring the Success sub-scenario's step 2) *before* the local unpushed commit, so both sides genuinely diverge and `--ff-only` has no fast-forward path in either direction.

### [NIT:consistency] Batch 2 Card 3's "Why" narrative overstates the `--ff-only` failure trigger
**Location:** 02-mill-merge-skill-fixes.md, Card 3
**Issue:** "If `merge --ff-only` fails (the parent worktree has local commits not present in `origin/<parent_branch>`...)" is incomplete — a parent with local-only commits and an unmoved `origin` does not fail `--ff-only` (it's a no-op success), only a parent with local-only commits *and* an independently-advanced `origin` does. The actual halt behavior is safe either way (same root cause as the Card 9 finding above), but the prose could mislead an implementer verifying the halt condition.
**Fix:** Clarify the halt only fires when `origin/<parent_branch>` has also advanced independently, not merely because the parent has unpushed local commits.

## Verdict

REQUEST_CHANGES
Card 9's divergence-halt fixture doesn't reproduce true git divergence, so its own assertion will fail as written.
MILL_REVIEW_END
