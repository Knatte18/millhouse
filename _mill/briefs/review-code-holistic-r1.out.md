MILL_REVIEW_BEGIN
# Review: Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-29
```

## Findings

### [NIT] test-worktree.py's move() collision test uses a file, not a directory
**Location:** `plugins/mill/unit_tests/test-worktree.py:476-494`
**Issue:** Card 7 (`02-mill-resume-repair.md`) specifies a failure case where the move target "already exists as a directory"; the implemented test instead pre-creates a regular file at the target and documents (in a comment) that `git worktree move` nests into an existing directory rather than failing, so the directory-collision scenario as literally worded would not raise.
**Fix:** None required to act on now — the rationale is sound and matches `scenario_d`'s later regression guard in `test-resume-relocate.py` (nested-directory collision); the plan wording is simply imprecise, not the code.

### [NIT] test-resume-relocate.py imports helper modules inside `__main__` guard
**Location:** `plugins/mill/integration_tests/test-resume-relocate.py:373-379`
**Issue:** `_paths`, `_resume_repair`, `_status`, `_worktree` are imported inside `if __name__ == "__main__":` rather than at module top, unlike the two sibling integration tests it was modeled on (`test-hub-relative-path.py`, `test-worktree-sibling-resolution.py`), which import at module level right after `sys.path.insert`.
**Fix:** None required — the file is always invoked as a script per its own docstring, so this works correctly; noted only for stylistic consistency with the established convention.

## Verdict

APPROVE
Implementation matches all four batch plans precisely across every card, contract, and shared decision; only cosmetic deviations found.
MILL_REVIEW_END
