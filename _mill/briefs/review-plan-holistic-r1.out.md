MILL_REVIEW_BEGIN
# Review: Monitor tool: persistent:true still referenced in mill-go-base and mill-plan despite no such param — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-23
```

## Findings

### [BLOCKING:consistency] Card 3 writes a `_mill/discussion.md` citation into a permanent doc
**Location:** batch `fix-monitor-persistent-refs`, Card 3, Requirement 1.
**Issue:** The dictated replacement paragraph for `plugins/mill/docs/harness-tool-contracts.md` (a permanent module doc, not under `_mill/`) reads "...the same verification `_mill/discussion.md`'s Problem section records, for the task that corrected this section..." — this cites `_mill/discussion.md` from a permanent doc, which CLAUDE.md's "Never cite `_mill/discussion.md`... from a permanent doc" rule forbids: `_mill/` is deleted/restored at merge time, so the link dangles on the parent branch after this task merges.
**Note:** the pre-existing text (verified in `plugins/mill/docs/harness-tool-contracts.md` line 26) already carries this same citation, but the plan has the opportunity to fix it here and instead re-writes the identical defect into the new paragraph.
**Fix:** Drop the `_mill/discussion.md` cross-reference from the replacement paragraph; state the 2026-09-23 re-verification as a bare fact (e.g. "reconfirmed via a live tool-schema read on 2026-09-23") without pointing at a task-branch-only path.

### [NIT:consistency] Batch Scope claims no card ordering dependency; Card 3 assumes one
**Location:** batch `fix-monitor-persistent-refs`, Batch Scope vs. Card 3.
**Issue:** Batch Scope states the three cards have "no ordering requirement between them... not because any one depends on another," but Card 3's Requirements open with "Read cards 1 and 2's now-updated `mill-go-base/SKILL.md` and `mill-plan/SKILL.md`... so this card's wording stays consistent with the design those two cards just landed" — this presumes cards 1 and 2 already executed.
**Impact:** Low — Card 3's find/replace text is fully literal and quoted, so the actual edit is identical regardless of execution order; only the narrative claim is self-contradictory.
**Fix:** Either drop the "now-updated" framing from Card 3 (since the replacement text doesn't actually depend on it), or state plainly in Batch Scope that Card 3 is sequenced after Cards 1–2 for wording-review purposes only.

## Verdict

REQUEST_CHANGES
Card 3's dictated text embeds a `_mill/discussion.md` citation into a permanent doc, violating CLAUDE.md's citation rule.
MILL_REVIEW_END
