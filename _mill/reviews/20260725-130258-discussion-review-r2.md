MILL_REVIEW_BEGIN
# Review: mill-plan review severity counting and validation schema gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

## Findings

### [GAP] Fail-loud helper's headings-vs-YAML mode selection is ambiguous
**Section:** Technical context — Severity-counting call graph (YAML-fallback paragraph)
**Issue:** "when heading_count (for either known severity) is 0, fall back to scanning fenced yaml `findings:`" does not specify AND vs OR: `parse_blocking_count` decides headings-vs-YAML independently per single severity call, but the new helper is one pass checking "neither" label and must pick one global mode. Under an AND reading (fallback only when both BLOCKING and NIT heading counts are 0), a review with real NIT headings present but zero BLOCKING headings plus an unrecognized severity expressed only in a YAML `findings:` entry would never trigger the YAML scan — silently reproducing Bug 1 through the exact mixed-format edge case this task exists to close.
**Fix:** State explicitly whether the fallback triggers on "both known-severity heading counts are 0" (matching the pure-YAML #552 shape) or "either is 0," and confirm the chosen rule can't leave a YAML-only unrecognized-severity entry uncounted when one known severity happens to use headings.

### [NOTE] Schema-doc scope bullet omits the YAML-fallback fail-loud behavior
**Section:** Scope — `review-output.schema.md` bullet
**Issue:** The Scope bullet says to document "any non-conforming severity heading is treated as blocking, not dropped," but the Technical Context requires the fail-loud helper to also cover the YAML-fenced `findings:` fallback path (case-insensitive) — the schema-doc bullet's wording only mentions headings, so a plan writer following Scope literally could under-document the YAML case.
**Fix:** Reword the `review-output.schema.md` Scope bullet to explicitly cover both the heading and YAML-`findings:` fail-loud paths, mirroring the Technical Context paragraph already written for the code fix.

## Verdict

GAPS_FOUND
One GAP: fail-loud helper's headings-vs-YAML fallback trigger condition is ambiguous (AND vs OR).
MILL_REVIEW_END
