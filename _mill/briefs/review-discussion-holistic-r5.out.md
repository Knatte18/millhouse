MILL_REVIEW_BEGIN
# Review: Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] "any mill skill" trigger claim unverified against mill-resume/SKILL.md
**Section:** Scope > In (mill-resume/SKILL.md new-phase bullet)
**Issue:** Text says the repair triggers "when mill-resume — or, per its own doc, 'any mill skill' — is invoked from inside such a worktree," but grepping `plugins/mill/skills/` for "any mill skill" returns zero matches — no doc says this, and the entire repair (Phase 1 halt change + new phase) is written only inside `mill-resume/SKILL.md`. There is no mechanism described for another skill (e.g. `mill-go`) invoked directly from the broken worktree to reach this logic.
**Fix:** Either drop the "any mill skill" clause as inaccurate, or add an explicit decision on how non-mill-resume invocations from the same broken worktree are handled (redirect to mill-resume, or explicitly out of scope with rationale).

### [NOTE] `git worktree move` failure itself has no stated halt behavior
**Section:** Decisions > mill-resume-relocate-then-scaffold / Testing > mill-resume relocate+scaffold
**Issue:** The pre-checks (uncommitted changes, canonical-path collision) each have explicit halt messages, and Phase 6's existing `git worktree add` failure has "report the error and stop," but no equivalent statement covers `git worktree move` itself failing (e.g. locked worktree, cross-filesystem move, permission error) after both pre-checks pass.
**Fix:** State that a `git worktree move` failure reports stderr and halts without further mutation, mirroring Phase 6's existing pattern.

### [NOTE] Non-committal testing language for mill-go halt-message verification
**Section:** Testing > mill-go health_check error surfacing
**Issue:** "unit test (or targeted review of the rendered halt output)" leaves the verification method undecided; unlike every other testing bullet in this section, no single strategy is committed to.
**Fix:** Commit to one approach (e.g. a unit test asserting the reason-string is logged plus a lightweight text-match check on the SKILL.md halt block), or state explicitly that manual review is accepted here and why.

## Verdict

GAPS_FOUND
One GAP: unverified "any mill skill" scope claim contradicts current mill-resume/SKILL.md source.
MILL_REVIEW_END
