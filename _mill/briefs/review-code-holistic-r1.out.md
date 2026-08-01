MILL_REVIEW_BEGIN
# Review: Add mill-quick: skip-review pipeline for simple tasks — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-01
```

## Findings

### [NIT] "No file may be edited before step 6" overstates the builder-lock write
**Location:** `plugins/mill/skills/mill-quick/SKILL.md:19-21` vs `:94-107`
**Issue:** The Entry preamble states no worktree file is edited before step 6, but step 5 (`millpy-builder-lock.py acquire`) writes `.millhouse/builder.lock` under the worktree on a successful acquire, which happens before step 6.
**Fix:** Narrow the preamble wording to "no tracked `_mill/` file" or explicitly except the gitignored builder-lock file, matching `_builder_lock.py`'s own write timing.

## Verdict

APPROVE
Single batch is a faithful, verified rendering of the plan; helper signatures, push discipline, and cross-references to mill-start/mill-go all check out against source.
MILL_REVIEW_END
