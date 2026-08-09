MILL_REVIEW_BEGIN
# Review: mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-09
```

## Findings

### [GAP] `--revise` row vs. existing unconditional `approved: true` halt row
**Section:** Decision `mill-plan-revise-reentry` (#786), mill-plan/SKILL.md Entry step 4 table
**Issue:** Confirmed (mill-plan/SKILL.md line 46) the existing table already has an unconditional row — `approved: true` in overview frontmatter → halt "plan already approved, run /mill-go" — that fires regardless of `phase:`. The decision's own text ("`approved:` is confirmed to stay `true` for the entire duration of mill-go's run") means the intended `--revise` window (`phase: planned`, `approved: true`) *also* satisfies this pre-existing row's condition. The decision never states that the new row must be checked before, or takes precedence over, this existing row, nor that the existing row must be amended to exclude `revise_requested`. As written, a plan writer could place the new row after the existing one (or leave the existing row's condition unmodified), causing every `--revise` invocation to hit the pre-existing halt before ever reaching the new logic — silently defeating the entire feature.
**Fix:** State explicitly either (a) the new `revise_requested` row is evaluated before the table's other rows (i.e. checked as a distinct pre-check, not merely "added to the table"), or (b) the existing `approved: true → halt` row's condition is amended to `approved: true AND NOT revise_requested`.

## Verdict

GAPS_FOUND
One GAP: unresolved precedence between the new `--revise` table row and the existing unconditional `approved: true` halt.
MILL_REVIEW_END
