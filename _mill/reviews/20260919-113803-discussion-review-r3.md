MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness: path-token exemption list gaps

```yaml
duration_s: 230.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-19
```

## Findings

### [NIT:scope] Ownership regex's possessive-'s branch has no test
**Section:** Decisions § Ownership-phrase exemption / Testing § Ownership exemption
**Issue:** The regex `\b(?:batch|card)\s+\d+\s+(?:'s\s+)?(?:<verb-form>)\b` includes an optional `'s` group, but none of the six listed ownership tests exercise it (all verbatim/synonym/past-tense cases omit the possessive).
**Fix:** Add a `..._ownership_possessive` clean case (e.g. "batch 8's fix touches `x.cs`.") or drop the untested group if not actually needed for any reported shape.

### [NIT:consistency] Illustrative-output exemption mislabeled as a "pairing" mechanism
**Section:** Decisions § Illustrative-example/output-framing exemption
**Issue:** Decision calls `_is_illustrative_output_exempt` a "marker-verb pairing" mechanism "mirroring `_is_prohibition_exempt`'s ... negation word + verb form pairing," but the operational spec that follows checks only a single `_OUTPUT_VERB_FORMS` presence line-wide — structurally a single-marker gate like `_CITATION_MARKERS`, not a two-set AND-pairing. The concrete behavior stated is unambiguous, so this is a labeling inconsistency, not a missing decision.
**Fix:** Reword to "single-marker line-wide exemption" (or similar) rather than "pairing," to avoid a plan writer over-building a second condition that doesn't exist in any reported shape.

## Verdict

APPROVE
Decisions, scope, and testing are resolved and source-consistent; only two non-blocking wording/coverage nits remain.
MILL_REVIEW_END
