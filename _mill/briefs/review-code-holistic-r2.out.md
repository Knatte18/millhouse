MILL_REVIEW_BEGIN
# Review: Fix nested-hub path resolution and SKILL.md vs shipped-API mismatches — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-18
```

## Findings

### [NIT] `_collect_shipped_helpers` last-writer-wins on stem collision
**Location:** `plugins/mill/unit_tests/test-skill-helper-drift.py:83`
**Issue:** `helpers[module_stem] = top_level_functions` overwrites an earlier entry when two scripts share the same stripped stem. `scripts/_render.py` and `scripts/wiki/_render.py` both strip to `render`; `rglob` order is not stable, so one module's function set silently replaces the other's.
**Fix:** Change the assignment to `helpers[module_stem] = helpers.get(module_stem, set()) | top_level_functions` so both modules' functions are unioned under the shared key. (In practice the current test still passes because both files define `render`, but the logic is fragile.)

### [NIT] SKILL.md Step 5 uses absolute `task_dir` for `git reset/checkout` pathspec
**Location:** `plugins/mill/skills/mill-merge/SKILL.md:111-112`
**Issue:** `task_dir` is an absolute path (`status_path.parent`), while `git reset HEAD -- <path>` canonically expects a repo-relative path. The integration test (line 537) correctly uses the relative string `"src/hub/_mill"`, creating an implicit inconsistency between the prose and the test.
**Fix:** Add a note in the prose that `<task_dir>` must be passed as a relative path from the repo root (e.g., derive `task_dir_rel = task_dir.relative_to(git_root)`) or explicitly mention that git accepts absolute paths within the repo.

## Verdict

APPROVE
All three batches are correctly implemented; two low-severity nits only.
MILL_REVIEW_END
