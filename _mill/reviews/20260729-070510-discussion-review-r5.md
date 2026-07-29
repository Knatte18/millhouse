MILL_REVIEW_BEGIN
# Review: mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Bracketing-check wiring site collides with the shared dispatch section
**Section:** Decisions -- "Closing the Agent-mode bracketing gap"
**Issue:** The decision places the new `check_and_restore` call "immediately before each Agent-mode `--stage prepare` dispatch and immediately after ... `--stage finalize`" for "every review loop," but the actual prepare/finalize steps (steps 2 and 6) live in mill-go/SKILL.md's single shared `## Agent-mode dispatch` section (`plugins/mill/skills/mill-go/SKILL.md:105-199`), which is also the dispatch mechanism for non-review Implement, Fix, and merge-in calls (confirmed: step 2/6 branch on CLI name, not role) -- explicitly out of scope per Scope (Out) "Only the three review loops ... are in scope." The discussion never states whether the bracketing edit goes into that shared section (over-applying to Implement/Fix/merge-in) or is duplicated at each of the four review-loop-specific call sites (mill-start step 2, mill-plan step 2, mill-go Code Review loop step 2, mill-go Holistic Review loop step 3) -- and the codebase's own existing convention explicitly discourages the latter ("that section is the single source of truth; do not re-assert ... behavior here," mill-start/SKILL.md:172).
**Fix:** State explicitly which of the two wiring approaches is required (e.g., "add the checkpoint at each review loop's own dispatch call site, never inside the shared `## Agent-mode dispatch` section, to avoid covering Implement/Fix/merge-in"), so a plan writer doesn't reasonably default to editing the shared section and inadvertently expand scope.

## Verdict
GAPS_FOUND
One GAP: the Agent-mode bracketing checkpoint's SKILL.md wiring location is unresolved and could scope-creep into non-review dispatches.
MILL_REVIEW_END
