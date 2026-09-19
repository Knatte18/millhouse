MILL_REVIEW_BEGIN
# Review: Audit mill-start/mill-plan/mill-go for turn reduction — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-19
```

## Findings

### [BLOCKING:consistency] Overlapping line-range double-classifies mill-plan Plan Review lines
**Location:** `doc/turn-reduction-audit.md` (`## mill-plan` → Phase: Plan Review), citing `mill-plan/SKILL.md:308-337` vs. `mill-plan/SKILL.md:316-329`
**Issue:** The "Path Setup / read persisted `skip_checks`/`discussion_sha`" bullet is cited as lines 308-337 and classified wholesale **Mechanical/collapsible** ("Deterministic frontmatter reads"). The very next bullet re-classifies a subset of that same range (316-329, which includes the Live operator round-cap override at `mill-plan/SKILL.md:326` and the Live operator waiver of step 6 at line 328) as **Excluded** for the live-operator parts. Verified against the current `mill-plan/SKILL.md`: lines 316-329 genuinely fall inside 308-337, so the same source lines carry two contradictory verdicts (Mechanical/collapsible AND Excluded) in the same document. This is exactly the "no step... double-counted" failure the doc's own `## Coverage check` claims did not occur, and a follow-up implementer could read either verdict for those lines.
**Fix:** Narrow the first bullet's line range to just the Path Setup / skip_checks / discussion_sha reads it actually describes (roughly `mill-plan/SKILL.md:308-314`, ending before "When `revise_from_blocked` is set" at line 316) so it no longer overlaps the next three bullets' ranges.

## Verdict

REQUEST_CHANGES
Overlapping line ranges classify the same mill-plan source lines as both Mechanical/collapsible and Excluded.
MILL_REVIEW_END
