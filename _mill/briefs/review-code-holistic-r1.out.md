MILL_REVIEW_BEGIN
# Review: Skill doc/table accuracy gaps across mill-groom, mill-start/mill-plan, and implementer-brief — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-25
```

## Findings

### [NIT] Auto-mode NOTE delegation still restates 4b's commit mechanics inline
**Location:** `plugins/mill/skills/mill-start/SKILL.md:37`
**Issue:** Card 3 edit 2 asked the `--auto` subsection to delegate to interactive step 4b's status-append/commit sequence instead of independently re-listing it (to avoid future drift between the two spots); the implementation does say "follow interactive step 4b's status-append calls and commit verbatim" but then still spells out both `_status.append_phase` calls, the four commit pathspecs, and the commit message inline in a parenthetical.
**Fix:** Trim the parenthetical to a bare cross-reference (e.g. "— see step 4b for the exact calls and commit") so a future edit to 4b's mechanics can't silently diverge from this restatement.

## Verdict

APPROVE
All four cards match plan requirements verbatim; no out-of-plan files, no cross-file inconsistencies found.
MILL_REVIEW_END
