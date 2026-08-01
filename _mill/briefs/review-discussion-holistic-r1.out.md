MILL_REVIEW_BEGIN
# Review: Non-interactive pipeline: only mill-start's interview may prompt the operator

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point-release unverifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-01
```

## Findings

### [GAP] mill-start/SKILL.md:41 references the deleted config key, uncovered by scope
**Section:** Technical context / "`pipeline.autonomous_mode` config key — every site to remove"
**Issue:** Grep confirms 8 files reference `autonomous_mode`; the Technical Context site list covers 6 (template, mill-plan, mill-go, mill-autofix x3, both unit-test fixtures) but omits `mill-start/SKILL.md:41`, which states "`--auto` is independent from `pipeline.autonomous_mode`... `pipeline.autonomous_mode` is a config key controlling mill-go's stuck-handling" — this sentence becomes factually wrong (referencing a deleted key) once this task lands, but the "Out" section frames mill-start lines 13-41 as entirely untouched/correct.
**Fix:** Add mill-start/SKILL.md:41 to the removal-sites list (the cross-reference sentence needs rewording or deletion), or explicitly note in "Out" that this one line is a documentation-only touch despite the rest of Auto mode being untouched.

## Verdict

GAPS_FOUND
One incomplete site in the autonomous_mode-removal enumeration (mill-start/SKILL.md:41).
MILL_REVIEW_END
