MILL_REVIEW_BEGIN
# Review: _plan_validate.py: further context-completeness, fence/indent-drift, and tag-exclusion gaps

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-21
```

## Findings

### [BLOCKING:design] move-target-collision fix-table edit has no specified content
**Section:** Scope: In / Technical context (mill-plan/SKILL.md fix-table)
**Issue:** Scope commits to updating the `move-target-collision` fix-table row (line 386) "to describe the new/changed check behavior," but unlike the `requirements-quote-indent-drift` row (which gets an explicit new message-shape clause per Decision `paired-fence-indent-check`) and the `verify-excludes-edited-tagged-test` row (fully rewritten per Decision `verify-tags-package-scoping`), no Decision or Technical-context text says what the `move-target-collision` row should actually say. Decision `intra-plan-move-chain` adds only a suppression condition — it emits no new message text — so it's unclear whether any row-content change is needed at all, or what it would be if so.
**Fix:** Either state explicitly that no fix-table content change is needed for `move-target-collision` (mirroring the `context-completeness` row's "likely no edit needed" caveat already given in Technical context), or specify the exact clause to add (e.g., a note that condition-1 no longer fires when the target is an in-plan chained-move source).

## Verdict

REQUEST_CHANGES
One fix-table content gap (move-target-collision) needs explicit resolution before plan writing.
MILL_REVIEW_END
