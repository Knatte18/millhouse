MILL_REVIEW_BEGIN
# Review: _plan_validate.py: further context-completeness, fence/indent-drift, and tag-exclusion gaps

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-21
```

## Findings

### [BLOCKING:consistency] paired-fence-indent-check: "immediately follows" definition contradicts its own Testing case
**Section:** Decision `paired-fence-indent-check` vs. Testing bullet (c). **Issue:** The Decision's mechanism walks `fence_bodies` (the flat regex-extracted list of fences) and compares an unmatched fence only against the immediately-preceding list entry, which is blind to prose between two fences in the raw text; but Testing (c) explicitly expects "a matched fence separated from an unmatched one by intervening prose text but still within the same Requirements: field" to produce NO finding — the opposite of what the described list-order mechanism would do, since the two fences are still list-adjacent. **Fix:** State explicitly in the Decision whether "immediately follows" means fence_bodies list-adjacency (current wording) or raw-text line-adjacency with no intervening prose, and reconcile Testing (c) to match whichever is chosen.

### [BLOCKING:design] paired-fence-indent-check: no tracked state for the anchor's matched Edits: token
**Section:** Decision `paired-fence-indent-check`. **Issue:** The new finding's message requires `path` = "the anchor fence's own matched Edits: token", but the Decision only specifies tracking `last_matched_indent`; verified against `_plan_validate.py:3110-3114`, the existing clean-match branch uses `any(... for t in ordered_resolved_tokens)` and never captures which token matched, so no token is available to carry forward even if state-tracking is added. **Fix:** Have the Decision also specify tracking the anchor's matched token (e.g. `last_matched_token`), including refactoring the clean-match branch's `any()` to a token-capturing loop like the strip/add passes already use.

## Verdict

REQUEST_CHANGES
Two BLOCKING design/consistency gaps in the paired-fence-indent-check decision must be resolved first.
MILL_REVIEW_END
