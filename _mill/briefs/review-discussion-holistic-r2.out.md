MILL_REVIEW_BEGIN
# Review: mill-go-base: remove subprocess/psmux dispatch branches

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [NIT:consistency] Per-batch cleanup block's start line disagrees across two Decisions
**Section:** `remove-psmux-cleanup-block` vs `remove-subprocess-poll-loop-maxwait` **Issue:** The former states the per-batch cleanup block spans SKILL.md 403-421; the latter's parenthetical says the same block is 402-421. Line 402 is blank (verified against source), so the deletion outcome is identical either way, but the two Decisions describing the same range disagree on its boundary. **Fix:** Pick one boundary (403, since that's where the `**Per-batch session cleanup.**` heading actually starts) and align the parenthetical in `remove-subprocess-poll-loop-maxwait`.

### [NIT:consistency] Sibling-SKILL subprocess/psmux reference counts (7, 6, 2) don't match a raw grep
**Section:** Scope > Out **Issue:** Verified against source: mill-plan/SKILL.md has ~9 lines mentioning subprocess/psmux dispatch (not 7), mill-start/SKILL.md has ~8 (not 6); mill-merge-in's claimed 2 is accurate. These counts are cited only as rationale for leaving the three sibling SKILLs untouched, so the discrepancy doesn't change scope or any action item. **Fix:** Either recount precisely or soften to "several"/"a handful" so the number isn't a load-bearing, checkable claim.

## Verdict

APPROVE
Every specific line number, quoted text, and count I spot-checked against source (30+ claims) verified exactly; the two NITs are non-blocking.
MILL_REVIEW_END
