MILL_REVIEW_BEGIN
# Review: mill-finalize/mill-merge corrupt or mishandle _mill/status.md and task_dir on stacked branches

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-16
```

## Findings

### [NOTE] Contradictory inline note in Direct-squash Step 5
**Section:** Decisions/step5-relative-pathspec; Technical context (mill-merge Step 5)
**Issue:** The current mill-merge SKILL.md:163 asserts `git reset`/`checkout` "accept both [absolute and relative] forms within the repo root" — directly contradicting #648's premise that the child-anchored absolute path is outside the parent repo; the discussion's fix changes the commands but never flags this note for correction.
**Fix:** State that this misleading note must be removed/corrected alongside the pathspec change so the skill is not self-contradictory.

### [NOTE] Residual live-worktree corruption window for general readers
**Section:** Scope/Out (4th bullet); Problem (para 1)
**Issue:** Step 3 leaves the child worktree's live `_mill/status.md` holding parent content by design; the slug-check protects only merge-routing reads, so after a partial/halted finalize, general readers (mill-go, mill-inspect) reading `_status.read_status`/`read_full` still see corrupted phase/parent fields — the scoping rationale doesn't address this failure window.
**Fix:** Note explicitly why a partial-finalize state read by mill-go is safe (or acknowledge it as accepted residual risk).

## Verdict

APPROVE
Thorough discussion; decisions well-justified, claims verified against source; only non-blocking notes.
MILL_REVIEW_END
