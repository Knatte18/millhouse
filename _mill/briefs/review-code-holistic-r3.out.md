MILL_REVIEW_BEGIN
# Review: mill-merge-in/mill-finalize/codeguide-update: cleanup-ordering and path-resolution bugs — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-04
```

## Findings

### [BLOCKING:scope] #930 citation-scan duplicated into mill-merge/SKILL.md, unauthorized by any card
**Location:** `plugins/mill/skills/mill-merge/SKILL.md:283-294`
**Issue:** Batch 2's Batch Scope and Card 5 explicitly scope #930's fix to `mill-finalize`'s pre-merge cleanup only ("Two cards, both required... a non-blocking scan-and-warn in mill-finalize Step 3... and a doc note in CLAUDE.md"); Card 5's `Edits:` list is `plugins/mill/skills/mill-finalize/SKILL.md` alone. No card in batch 1 or batch 2 authorizes touching `mill-merge/SKILL.md` Step 4. Yet `mill-merge/SKILL.md` Step 4 ("Cleanup commit") now carries a near-verbatim duplicate of Card 5's citation-scan block, explicitly labeled `(non-blocking, #930)`, with its own two grep commands and warning-text branching. This is the "surprise file" scenario the review criteria call out by name — the batch file was never updated to authorize this addition before it was implemented, and the overview's `## All Files Touched` / Shared Decisions never mention #930 applying to `mill-merge`.
**Fix:** Either revert the addition to `mill-merge/SKILL.md` Step 4 (keep #930's fix confined to `mill-finalize` as planned), or add a card to batch 1 (or a new batch) that explicitly authorizes and documents extending #930's scan to `mill-merge`'s own cleanup path, updating `00-overview.md`'s Batch Scope / All Files Touched accordingly — the underlying observation (mill-merge's Step 4 also deletes `_mill/` and can equally break citations) may be correct, but it needs to go through the plan first, not land as an uncarded diff.

## Verdict

REQUEST_CHANGES
mill-merge/SKILL.md Step 4 carries an unauthorized #930 citation-scan duplicate outside any card's scope.
MILL_REVIEW_END
