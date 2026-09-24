MILL_REVIEW_BEGIN
# Review: Prefix session names with repo short name; add MH:orch session

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

Verified against source: `_vscode_tasks.py` (TASK_SPECS, DEFAULT_SESSIONS, build_command, render_tasks,
write_tasks, `_validate_name`), `_paths.py` (`resolve_short_name`, `resolve_main_worktree_root`),
`_render.py`, `vscode-tasks.json` template, `mill-config.yaml` template and hub file, `_setup.py`,
`millpy-spawn.py`, `millpy-session-tasks.py`, `millpy-terminal.py`, `millpy-claim.py`,
`millpy-color.py`, `_vscode.py`, `_vscode_keybindings.py`, `mill-setup/SKILL.md`,
`mill-spawn/SKILL.md`, `mill-session-tasks/SKILL.md`. Every current-state claim (existing docstrings,
signatures, template shape, `resolve_short_name(cfg, git_root.name)` call sites, six-task template,
Phase 3.1/7/7b numbering) matches what's on disk. The two callers correctly left out of scope
(`millpy-color.py`, `millpy-claim.py`) do genuinely keep `git_root.name` with no session-naming
involvement — `millpy-claim.py` never calls `_vscode_tasks.write_tasks`, only the window title.

Each `### Decision:` carries rationale and a Rejected list. The composition/lower-casing design
(single `session_prefix` helper) and the `<HUB_TASKS>` template-token mechanism resolve prior-round
gaps (lower-casing site, terminal session) without introducing new contradictions — the empty-string
worktree case and the leading-comma hub fragment both produce valid JSON as described.
`spawn.sessions.orch` addition is consistent with `resolve_sessions` iterating `DEFAULT_SESSIONS`
(confirmed in `_vscode_tasks.py`), and is a no-op for worktree rendering since `TASK_SPECS` never
references the `orch` phase.

No undecided items, scope ambiguity, or tooling/validator contradictions found. Testing section names
unit-test targets per callsite with concrete expected strings, all against existing test files.

## Verdict

APPROVE
No blocking or nit findings; all technical-context claims verified against source.
MILL_REVIEW_END
