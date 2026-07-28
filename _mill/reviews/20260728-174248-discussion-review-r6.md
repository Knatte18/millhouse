MILL_REVIEW_BEGIN
# Review: Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-28
```

## Findings

### [GAP] Dirty-parent preflight doesn't exclude untracked files
**Section:** Decisions/dirty-parent-worktree-preflight (#705)
**Issue:** The Decision specifies plain `git -C <parent-path> status --porcelain` (no `--untracked-files=no`), so routine untracked noise (build output, editor swap files, anything not yet gitignored) in the parent worktree also halts the skill, even though neither named scenario (independent edit, mid-Step-5 retry) involves untracked files; the codebase's established convention for equivalent "is this dirty enough to act on" checks (`implementer-brief.md:99`, `_cleanliness.py` lines 18/33/161) deliberately passes `--untracked-files=no`/`include_untracked=False`.
**Fix:** State explicitly whether the preflight scopes to tracked changes only (matching the codebase convention) or intentionally also catches untracked-file squash collisions, since this is exactly the kind of unattended-pipeline false-positive the Rationale paragraph warns against elsewhere.

### [GAP] "Kept both sides" discarded-flag trigger: unconditional or ambiguous-only?
**Section:** Decisions/merge-in-semantic-duplication (#718)
**Issue:** The Decision's own text says "a resolution which kept content from both sides of a hunk... is surfaced" (unconditional), but Scope/In says the field extension covers only "ambiguous 'kept both sides' resolutions" (qualified) — it's unclear whether every ordinary step-3 disjoint combine (e.g. column A + column B, the existing silent-success case) must now populate `discarded`, or only the #718-shape judgment calls where the sub-agent itself is unsure.
**Fix:** Pick one: either scope the new `discarded` population to cases where the sub-agent's own move-vs-duplicate search was inconclusive/risky, or explicitly accept that every disjoint combine now gets surfaced to the operator — the two readings produce materially different brief wording and operator-interruption frequency.

## Verdict

GAPS_FOUND
Two cross-section wording ambiguities (untracked-file scoping in #705; unconditional-vs-ambiguous trigger in #718) need resolution before plan writing.
MILL_REVIEW_END
