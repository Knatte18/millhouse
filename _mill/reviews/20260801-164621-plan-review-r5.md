MILL_REVIEW_BEGIN
# Review: Non-interactive pipeline: only mill-start's interview may prompt the operator — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: plan/
date: 2026-08-01
```

## Findings

### [BLOCKING] Verify/logic self-resolve plan edits are never committed or logged
**Location:** Batch 2 Card 4 (`` `verify`/`logic` `` first-occurrence bullet); Batch 3 Card 6 (`` stuck_type: verify `` or `` logic `` bullet)
**Issue:** Both new self-resolve bullets instruct editing plan file(s) then re-firing/re-invoking immediately, with no `git add`/`commit` for the plan edit and no `_status.append_phase(..., "self-resolved-...")` call — violating Shared Decision `audit-trail-via-status-timeline` (which lists both batches under "Applies to") and departing from this codebase's established edit-plan-then-commit-then-retry pattern (e.g. mill-plan Step 1.5's validator-fix commit). Cards 9/10/12 in this same task correctly append_phase + commit their own self-resolve actions; these two do not.
**Fix:** Add an explicit `git -C <worktree> add <plan_dir> && git commit` plus `_status.append_phase(status_path, "self-resolved-<reason>", ...)` for the plan edit before the re-fire/re-invoke, mirroring Cards 9/10/12.

### [BLOCKING] Scope-violations self-resolve requires reading card bodies, contradicting Lean Builder
**Location:** Batch 4, Card 10 (Scope violations cleanup gate)
**Issue:** The new classification step tells the Builder to check `blocking_paths` "against the plan's `All Files Touched` list AND the batch cards' `Edits:`/`Creates:` fields" — the latter requires opening every batch file's card bodies, directly contradicting mill-go's own Principle: "You never read card bodies, diffs, or source files unless responding to a stuck-logic event on a specific batch." It is also redundant: `All Files Touched` is already defined by this plan's own convention as exactly the union of every card's `Edits:`/`Creates:`/Move-target paths.
**Fix:** Drop the "batch cards' Edits:/Creates: fields" cross-check; classify solely against the overview's `All Files Touched` list.

### [NIT] Card 5's rationale cites the wrong step number
**Location:** Batch 3, Card 5
**Issue:** The deletion rationale says "Card 7 in this batch makes step 5's round-exhaustion unconditional," but Card 7 actually edits step 7 ("Rounds exhausted"), not step 5.
**Fix:** Change "step 5's" to "step 7's" in Card 5's Requirements prose.

### [NIT] New self-resolve commits push without updating mill-go's push-policy note
**Location:** Batch 4, Cards 9 & 10
**Issue:** Both new self-resolve commits end with "and push," but mill-go's `## Board discipline` section explicitly states "The Builder's own state commits (Prepare, Approve, blocked, done)... do not push — mill-merge pushes the full task branch at task end," and this batch never updates that enumeration for the new `self-resolved-*` commit types.
**Fix:** Either drop "and push" from Cards 9/10 to match the documented policy, or add a card updating the Board-discipline paragraph.

### [NIT] mill-autofix phase numbering gains gaps after deletions
**Location:** Batch 6, Card 15
**Issue:** Deleting "## Phase 2" and "## Phase 4" without renumbering leaves Phase 0, 1, 1c, 3, 5 — a confusing gap for future readers.
**Fix:** Optional cosmetic renumbering of remaining phase headings.

## Verdict

REQUEST_CHANGES
Two BLOCKING gaps in new self-resolve logic (audit trail, Lean-Builder scope) need fixing before approval.
MILL_REVIEW_END
