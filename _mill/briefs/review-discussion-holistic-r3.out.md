MILL_REVIEW_BEGIN
# Review: mill-plan/SKILL.md doc gaps: missing mill:conversation load, Phase: Plan commit step omits push

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Max-rounds prompt format conflicts with mill:conversation's rule
**Section:** Problem (Gap A quote of mill-plan lines 246-254) / Scope > In
**Issue:** `conversation/SKILL.md` mandates numbered `1) Label — description` lists with `(Recommended)` suffixed to option 1's label. mill-plan's literal max-rounds-escape prompt (verified: `plugins/mill/skills/mill-plan/SKILL.md` lines 248-252) instead uses lettered `A) B) C)` options with a separate trailing `Recommended: {A/B/C}` line that can point at any letter — structurally non-compliant. Loading the skill (Gap A's fix) does not, by itself, bring this already-hardcoded prompt text into conformance; the discussion's characterization of it as "the same shape `mill:conversation` documents" (Problem, line 17) overstates the match.
**Fix:** State explicitly whether reformatting this prompt to numbered/recommended-first form is in scope for this task, or record a deliberate deferral with rationale — `conversation/SKILL.md`'s own "applies retroactively... when you touch an existing skill" clause makes this a live question given this task edits the same file.

### [GAP] Two push-fix commit lines already omit `-C <worktree>` on `git commit`
**Section:** Gap B (Problem quotes) / Decisions > push-wording-scope (mill-plan lines 116, 242)
**Issue:** Verified in `plugins/mill/skills/mill-plan/SKILL.md`: both lines targeted for the "Push." addition — line 116 (`git -C <worktree> add <plan_dir> <status_path> && git commit -m "..."`) and line 242 (`git -C <worktree> add ... && git commit -m "..."`) — prefix `-C <worktree>` only on `add`, not on `commit`. Every other commit-producing step already fixed or cited as already-fine (4a/167/176) consistently prefixes `-C <worktree>` on both. The discussion quotes these two lines verbatim without noting the discrepancy.
**Fix:** Since the plan is already touching these exact two lines to append "Push.", decide whether to also normalize them to `git -C <worktree> commit` for consistency, or explicitly note the inconsistency is out of scope (same "obvious remaining inconsistency on next read" logic the push-wording-scope Decision already applied to pull in 4d).

### [NOTE] mill-go Step 0 load placement wording is slightly inconsistent
**Section:** Decisions > mill-conversation-load-placement (mill-go)
**Issue:** Scope > In says the load goes "at/immediately after the current Step 0"; the Decision says "extend/adjoin the existing Step 0 ... keeping it the first substantive action" — leaves ambiguous whether the load merges into Step 0's own text (one combined step) or becomes a new step following it.
**Fix:** State literally which — e.g. "Step 0 becomes one paragraph covering both checks" vs "insert a new Step 0.5 immediately after."

## Verdict

GAPS_FOUND
Two GAPs: prompt-format mismatch with mill:conversation, and pre-existing -C <worktree> omission on the two lines being edited.
MILL_REVIEW_END
