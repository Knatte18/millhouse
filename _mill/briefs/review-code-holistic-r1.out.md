MILL_REVIEW_BEGIN
# Review: millpy-implement finalize/resume fixes and the red integration suites — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-26
```

## Findings

### [NIT:consistency] Stale layout description in `_setup_pair` docstring
**Location:** `plugins/mill/integration_tests/test-spawn.py:61-65`
**Issue:** The docstring still lists `<container>/hub` and `<container>/hub/.millhouse/wiki`, but the fixture builds the hub at `<container>/wts/hub` (lines 73-74).
The module docstring (lines 8-9) was updated as Card 10 requires, so the file now describes two layouts.
**Fix:** Update the `_setup_pair` layout list to the container layout.

### [NIT:consistency] Misplaced parenthetical in `_forward_output` docstring
**Location:** `plugins/mill/scripts/_implementer_common.py:1865`
**Issue:** "every value for this batch's own card_ids (per commit_none_card_ids exclusion is not applied here ...)" reads as garbled.
The sentence is unchanged by this task, but it now sits beside the new `commit_none_card_ids` semantics.
**Fix:** Reword it, or leave it as pre-existing.

## Verdict

APPROVE
All cards are realised: `Commit: none` recount, `_is_brief_path` finalize fix, and resume note. Tests and repairs are consistent, with only docstring nits.
MILL_REVIEW_END
