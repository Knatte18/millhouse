MILL_REVIEW_BEGIN
# Review: mill-plan: entry-gate, timeline, and script-portability bugs — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Sonnet 5 (claude-sonnet-5)
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [NIT:consistency] Card 3 locate-quotes drop `status_path,` argument
**Location:** batch 1, card 3, insertions 2 and 6 **Issue:** Both "locate the sentence" quotes for the Agent-mode tree-guard checkpoint text ("...call _status.append_recovery_log(result[\"timestamp\"], result[\"restored_paths\"])...") omit the `status_path,` first argument that is actually present in the source at `mill-plan/SKILL.md` lines 416 and 497 (`_status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"])`), so the quoted "sentence" is not a byte-exact substring of the file. **Fix:** Correct both quotes to include `status_path,` so an implementer doing a literal-string locate succeeds; the surrounding immediately-preceded/immediately-followed anchors still make the insertion point findable in the meantime.

### [NIT:consistency] "Immediately precedes" mischaracterizes subprocess blockquote adjacency
**Location:** batch 1, card 3, insertions 3 and 7 **Issue:** Both describe the "Before invoking `millpy-bg`" blockquote as immediately preceding the `--slug plan-review-r<N>`/`--slug plan-review-retry-r<N>` bash invocation, but in the actual file (lines 463-473 and 511-521) two more blockquotes (round-cap override reminders) sit between that blockquote and the bash block. **Fix:** Reword to "the blockquote immediately preceding the round-cap-override reminder blockquotes, ahead of the `--slug ...` invocation" — the actual instruction ("insert immediately before this blockquote") is unambiguous regardless, so this is cosmetic.

## Verdict

APPROVE
Plan is accurate against source, decisions are faithfully implemented, and DAG/verify/context fields are sound; only minor quote-precision NITs found.
MILL_REVIEW_END
