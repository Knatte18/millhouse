MILL_REVIEW_BEGIN
# Review: mill-plan Entry step 2: _config.load_config called with hub_root/worktree_root swapped vs its own signature

```yaml
duration_s: 115.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-20
```

## Verdict

All source claims (`_config.py`, `_paths.py`, `_review_common.py`, `mill-plan/SKILL.md`, `mill-go-base/SKILL.md`, `mill-start/SKILL.md`) verified accurate; no findings.

Verified against source, all matching the discussion exactly: `_config.load_config` signature and docstring at `_config.py:221`; `resolve_repo_config_path`'s three-candidate use of `worktree_root` at `_config.py:178-218` (the r1-corrected "not only" phrasing now matches the code precisely); `resolve_main_worktree_root(git_root: Path)` at `_paths.py:234`; `resolve_task_path(worktree_root: Path, ...)` at `_paths.py:583`; mill-plan Entry step 1/2 bindings and call site at `mill-plan/SKILL.md:32-42` (line numbers cited as "~line 39"/"~line 42" both exact); `_plan_validate.run`'s second positional param confirmed named `project_root` at `_plan_validate.py:2708-2710`, matching the "no name-collision" claim for that call site; mill-go-base's Path Setup at lines 73-86 confirmed binding the hub-scoped `_paths.resolve_active_hub` value to a variable named `worktree_root` and feeding it into `resolve_task_path` — the cited structural analog superseding the r1-flagged wrong lines-512-514 citation; its distinct `_review_common.load_config(hub_root, mill_dir)` call confirmed at line 54 with matching signature at `_review_common.py:2726`; mill-start's identical `worktree_root = _paths.resolve_hub_path()` binding confirmed at `mill-start/SKILL.md:82`, with no literal inline `_config.load_config(...)` call anywhere in that file (only prose + signature quote at line 75), matching the "follow-up, not folded in" scope call exactly.

Decisions section has stated rationale and rejected alternatives for both the root-cause classification and the fix-approach; the mill-start deferral is explicitly justified against the task's canonical brief. Testing section is appropriately scoped to a prose-only Markdown edit (grep + read-through, no unit-test claim, no PYTHONPATH= verify-command applicability since there is no Python `verify:` step here). No undecided items, no scope ambiguity, no unaddressed failure modes for a call-argument-only documentation fix.
MILL_REVIEW_END
