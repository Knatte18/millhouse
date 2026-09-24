MILL_REVIEW_BEGIN
# Review: Prefix session names with repo short name; add MH:orch session

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

Cross-checked every Technical Context claim against source: `_vscode_tasks.py` (`TASK_SPECS`, `DEFAULT_SESSIONS`, `build_command`, `_validate_name`'s forbidden-char set, `render_tasks`/`write_tasks` signatures), `_paths.py` (`resolve_short_name`'s fallback arithmetic, `resolve_main_worktree_root`), `millpy-spawn.py`, `millpy-session-tasks.py`, `millpy-terminal.py`, `_render.py` (KeyError-on-unresolved-token), `vscode-tasks.json` and `mill-config.yaml` templates, `_setup.py`, and `mill-setup/SKILL.md` Phases 3.1/7/7b. All quoted current-state descriptions match what is on disk verbatim, including the exact `short_name: ""    # e.g. "MH" for millhouse` template line the new line-level helper must preserve, and the existing `test-vscode-tasks.py` assertion that the template's `spawn.sessions` equals `DEFAULT_SESSIONS` (correctly flagged as needing an `orch` entry).

Decisions are complete: each carries rationale and rejected alternatives, and no undecided item remains — the one explicitly deferred detail (`_NO_PROMPT_PHASES` vs. `None`-prompt mechanism) is scoped as an implementation choice, not a design gap. Scope in/out boundaries are unambiguous (migration, keybinding, window-title format, `parent-thread` field all explicitly excluded with reasons). Constraint coverage (`_validate_name` char set, ASCII-only logging, config template/hub sync, no `sed`) is addressed. Testing section names concrete unit-test files and behaviors per changed module, including the fallback-derivation edge case (`mi:` from `millhouse`, not `se:` from the worktree slug).

## Verdict

APPROVE
No blocking or nit findings; discussion is internally consistent and verified against source.
MILL_REVIEW_END
