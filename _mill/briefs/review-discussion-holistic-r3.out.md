MILL_REVIEW_BEGIN
# Review: _plan_validate context-completeness: further false-positive/false-negative gaps, round 3

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-23
```

## Findings

### [BLOCKING:design] line-join-refactor's offset coordinate mismatch for `_is_literal_enumeration_exempt`
**Section:** Decision `line-join-refactor`
**Issue:** Token extraction now runs on the joined text, so `match.start(1)`/`match.end(1)` are joined-text-global offsets. The decision says `_is_literal_enumeration_exempt` "keep[s] running against ONLY the token's own originating physical line ... exactly as today," but that function's own logic (`_BACKTICK_RE.finditer(line)` then `m.start(1) == token_start and m.end(1) == token_end` to skip the tested occurrence) requires `token_start`/`token_end` local to `line`, not global to the joined text. Verified against the current implementation (`plugins/mill/scripts/_plan_validate.py`, `_is_literal_enumeration_exempt`) — passing global offsets with a re-scan of only the local physical line means the self-skip span match almost never succeeds past the first physical line, so the tested token gets counted as its own "sibling" and the majority tally (this task's own `literal-enumeration-majority` fix) is corrupted for every line after the first.
`_is_cross_card_ownership_exempt`/`_is_illustrative_output_exempt` are unaffected (no offset params), so this is specific to the one helper that takes positions.
**Fix:** State explicitly that the global `token_start`/`token_end` must be translated to offsets relative to the looked-up originating physical line (subtract that line's start offset from the offset table) before calling `_is_literal_enumeration_exempt`.

## Verdict

REQUEST_CHANGES
One BLOCKING: line-join-refactor omits required offset translation for `_is_literal_enumeration_exempt`.
MILL_REVIEW_END
