MILL_REVIEW_BEGIN
# Review: Prefix session names with repo short name; add MH:orch session

```yaml
duration_s: 170.1
verdict: APPROVE
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

Verified against source: `_vscode_tasks.py`, `_paths.py`, `_render.py`, `_setup.py`, `millpy-spawn.py`, `millpy-session-tasks.py`, `millpy-terminal.py`, `vscode-tasks.json`, `mill-config.yaml` (template + hub), `mill-setup/SKILL.md`, `mill-spawn/SKILL.md`, `mill-session-tasks/SKILL.md`, `_vscode_keybindings.py`, and unit tests `test-vscode-tasks.py`, `test-millpy-spawn.py`, `test-millpy-terminal.py`.

All Technical Context claims (current signatures, docstrings, TASK_SPECS/DEFAULT_SESSIONS contents, the `resolve_short_name` fallback formula, the existing `parsed["spawn"]["sessions"] == DEFAULT_SESSIONS` test assertion, the `mill:conversation` numbered-list convention, `_render.render`'s KeyError-on-unresolved-token and no-recursive-substitution behavior, the `_setup.py`/Phase 4.9 precedent for line-level file edits) check out against the actual files. No CONSTRAINTS.md exists in this repo, so that criterion is inapplicable.

Every `### Decision:` carries rationale and rejected alternatives. The `resolve_sessions(phases=...)` scoping correctly isolates a bad `spawn.sessions.orch` value from worktree renders. The `<HUB_TASKS>` token / fragment-template mechanism produces valid JSON in both empty and hub-rendered cases and matches `_render.py`'s format-discipline rule. The main-worktree-name fallback (vs. current-worktree name) is applied consistently across all three callers and is covered by an explicit fallback test. No undecided items, no scope ambiguity, no failure-mode gaps found.

## Verdict

APPROVE
No blocking issues; all decisions grounded, technical-context claims verified against source.
MILL_REVIEW_END
