MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: misses bare symbol/identifier references entirely, only matches path tokens

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] "One allowed dot" signal contradicts the shape gate's own stated rationale
**Section:** Decisions § Symbol-candidate shape
**Issue:** The "looks like code" signal is satisfied by an uppercase-after-position-0 letter, an underscore, OR "the one allowed dot" — the dot alone, independent of case. This means any plain all-lowercase two-segment dotted phrase (`config.example`, `user.name`, `response.body`) is a symbol candidate, even though the rationale explicitly frames the signal requirement as excluding "plain all-lowercase... words... more likely to be ordinary prose." Every worked example in the rationale (`zone.SourceCellsWithCoverage`, `reedengine.New`, `cell.CenterVerticalDepth`) already contains an uppercase letter after position 0 in one segment, so the dot-alone branch is not needed to cover any cited issue and exists only to admit lowercase dotted prose the rest of the decision says it wants to exclude.
**Fix:** Either drop "the one allowed dot" as an independent qualifying signal (require CamelCase/underscore in at least one segment even for dotted tokens), or explicitly state and justify the intentional broader case — e.g. catching lowercase, unexported Go-style qualified calls (`pkg.remap`) — as an accepted trade-off, and add a Testing case exercising an all-lowercase dotted token to confirm the intended behavior.

## Verdict

REQUEST_CHANGES
Dot-alone "looks like code" signal undermines the shape gate's stated lowercase-prose exclusion; needs explicit resolution.
MILL_REVIEW_END
