# Review: 38 (A) — Drop active.slug.md marker

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-09
```

## Findings

### [GAP] Test update list omits 5 affected files
**Section:** ## Testing
**Issue:** The list "Update existing unit tests that wrote markers" covers 13 files but misses: `test-active.py` (directly imports `_active` symbols — fails on import when `_active.py` is deleted), `test-inplace.py` (calls `is_inplace(active_data, git_root, cfg)` with the old dict-based signature; all 4 tests break with the new `is_inplace(slug, git_root, cfg)`), and `test-millpy-color.py`/`test-millpy-implement.py`/`test-millpy-implement-holistic.py` (patch `mill_color._active`, `millpy_implement._active`, `millpy_implement_holistic._active` respectively — after those production imports are removed, the patches target non-existent attributes and raise `AttributeError`).
**Fix:** Add these 5 files to the Testing section: delete `test-active.py` (coverage subsumed by new `test-marker.py`), update `test-inplace.py` to pass `slug` instead of `active_data`, and update the three patch targets in the color/implement/implement-holistic tests.

### [NOTE] Cleanup call order requires reordering, not just threading
**Section:** ## Technical Context (millpy-vscode/terminal row + millpy-cleanup row)
**Issue:** The discussion says "mill-cleanup already has `home_tasks` parsed at line 484; thread it through," implying only a signature change is needed. But the actual call `discover_active_worktrees(container_path / "wts")` is at line 480 — *before* `home_tasks = _tasks_md.parse(home_text)` at line 484. The call must be moved to after line 484, not just updated in-place.
**Fix:** Add a note that the `discover_active_worktrees` call site in `millpy-cleanup.py` must be moved to after the `home_tasks` parse — or note that `home_tasks` loading must be hoisted above line 480.

## Verdict

GAPS_FOUND
Five test files omitted from the update list will cause suite failures; one needs explicit call-reorder guidance.