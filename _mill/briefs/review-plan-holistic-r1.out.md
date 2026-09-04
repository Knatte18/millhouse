MILL_REVIEW_BEGIN
# Review: mill-plan: review-round cap and skip-check threading bugs — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:scope] Full-validate gate added to 4b/4d but not to 4c
**Location:** Batch 01, Cards 3 & 4 (step 4b/4d full-validate re-run). **Issue:** 4c also applies NIT fixes and can break loop straight to Handoff on convergence (same risk category #981 targets in 4b/4d), yet Card 3 says "Do not change 4a, 4c, or 4d" and Card 4 says "Do not change 4a, 4b, or 4c" — 4c never gets the gate. **Fix:** Add a card (or extend Card 3/4's scope) applying the identical full-validate gate to 4c's fix-and-converge path, or add a Shared Decision explaining why 4c is deliberately excluded.

### [BLOCKING:consistency] --approve escape hatch not surfaced in the row operators actually see
**Location:** Batch 01, Card 2 (`phase: blocked` table row edit). **Issue:** Card 2 only edits the row's trailing citation sentence ("This row is reached only when…"); the row's actionable guidance text — "tell the operator to re-run `/mill-plan --revise` to resume plan review (or resolve manually)" — is left untouched, so an operator hitting this exact row (no flag passed) is never told `--approve` exists, even though this is precisely the state `--approve` was built to resolve. **Fix:** Extend Card 2's Requirements to also update the row's action text to mention `--approve` as an alternative when `blocked_reason` starts with "max-rounds exhausted".

### [NIT:consistency] Two independently-toggleable features bundled into one card/commit
**Location:** Batch 01, Card 5. **Issue:** The card's own prose states the round-cap-raise and step-6-waiver instructions are independent ("an operator may raise the cap without waiving step 6 … or do both"), yet both are authored as one card with one commit message, so reverting one later means reverting both. **Fix:** Split into two cards (round-cap-raise; step-6-waiver + the one-sentence append to "Resumed-loop round-cap substitution").

### [NIT:consistency] Step-6-waiver commit instruction omits explicit git pathspec
**Location:** Batch 01, Card 5 (waiver paragraph's commit step). **Issue:** Unlike every other commit instruction in this file (e.g. Card 2's "`git -C <worktree> add <plan_dir> && …`"), the waiver's "commit on the task branch with message X" omits the `git add` pathspec even though it mutates `plan/00-overview.md`. **Fix:** Name the pathspec explicitly (at minimum `<plan_dir>`), matching sibling commit instructions.

## Verdict

REQUEST_CHANGES
4c lacks the #981 full-validate gate given to 4b/4d, and Card 2 leaves the operator-facing --revise-only guidance stale.
MILL_REVIEW_END
