# Plan: Auto-name task sessions <slug>:<phase>

```yaml
task: "Auto-name task sessions <slug>:<phase>"
slug: "session-naming"
approved: false
started: "20260924-061400"
parent: "main"
root: ""
verify: null
skip_checks: ["wiki-config-mutation"]
discussion_sha: "aae08aea338592f1dad9424eafea2253fdd85a06"
```

## Batch Index

```yaml
batches:
  - number: 1
    name: tasks-render
    file: 01-tasks-render.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-vscode-tasks.py test-vscode.py test-config.py
  - number: 2
    name: keybindings
    file: 02-keybindings.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-vscode-keybindings.py
  - number: 3
    name: session-tasks-cli
    file: 03-session-tasks-cli.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-session-tasks.py test-shortcut-wrapper.py test-skill-writer.py
  - number: 4
    name: spawn-wiring
    file: 04-spawn-wiring.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-spawn.py
  - number: 5
    name: setup-docs
    file: 05-setup-docs.md
    depends-on: [1, 2, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-skill-helper-drift.py
```

## Shared Decisions

### Decision: config-mutation-is-bootstrap-safe

- **Decision:** Card 1 edits the hub `mill-config.yaml` and the plugin template (adding `spawn.sessions`), so `wiki-config-mutation` is skipped for this plan (`skip_checks` in the frontmatter).
  Card 1 is the bootstrap card: the only consumer is the new `_vscode_tasks.resolve_sessions`, which falls back per key to built-in defaults, so a config without the keys behaves identically.
- **Rationale:** key addition with consuming code in the same plan cannot use the "provably unused" exemption; the bootstrap-card exemption applies instead.
- **Applies to:** tasks-render

### Decision: prompt-form-single-fallback-point

- **Decision:** The task's initial prompt is built in one private helper, `_vscode_tasks._prompt`.
  The slash form (`/mill-<phase> [flag]`) is implemented; that an interactive `claude` session executes a positional `/...` prompt as a command could not be tested non-interactively during planning and is on the manual checklist in batch 5.
  The documented fallback (`Invoke the mill:mill-<phase> skill with args "<flag>"`) is a one-function change.
- **Rationale:** verification needs an interactive TTY; isolating the form keeps the fallback cheap.
- **Applies to:** tasks-render

### Decision: commandsToSkipShell-kept

- **Decision:** `terminal.integrated.commandsToSkipShell: ["workbench.action.tasks.runTask"]` stays in the settings template.
  The VS Code terminal docs state that commands on this list have their keybindings handled by VS Code instead of the shell when a terminal has focus, and do not list `runTask` among documented defaults.
  Whether the shortcut fires with terminal focus in practice is on the manual checklist; the discussion's fallback (document editor-focus / Run Task usage, no further workaround) applies if it does not.
- **Rationale:** verification requested by the discussion; docs confirm the mechanism.
- **Applies to:** tasks-render, setup-docs

### Decision: claude-ready-terminal-not-found

- **Decision:** A repo-wide `git grep -i "claude ready"` at planning time matched only the discussion file; nothing in this repo creates the "claude ready" default terminal, so no batch removes anything.
  The final report must say this and that the source is probably the Claude Code VS Code extension or the user's global VS Code config.
- **Rationale:** the discussion required a final grep and a report when nothing is found.
- **Applies to:** all batches

### Decision: keybindings-write-is-conservative

- **Decision:** `_vscode_keybindings.write_bindings` never creates the VS Code user directory (missing directory: skipped with a warning), never overwrites a conflicting user binding, and leaves an unparsable file untouched.
  Tests inject explicit paths; the real user file is never touched by tests.
- **Rationale:** writing outside the worktree is limited to the mill marker block inside an existing VS Code user directory (discussion constraint).
- **Applies to:** keybindings, setup-docs

### Decision: done-gate-left-null

- **Decision:** `pipeline.done_gate` is not set by this plan.
  The candidate lint command `uvx ruff check .` run against the worktree tip exits 1 with 2008 pre-existing findings, so making every task depend on it would tie unrelated debt to this work; no repo-wide test command is added because the full suite takes minutes.
- **Rationale:** planning rule: leave `done_gate: null` and record the finding when lint has pre-existing repo-wide debt.
- **Applies to:** all batches

### Decision: verify-scoping

- **Decision:** Every batch `verify:` runs only the named test files via `run-all.py --only`; none uses the unbounded suite.
  The module-wide overview `verify:` is `null`.
- **Rationale:** each batch touches only the files its tests cover (`_shortcuts.py` is covered by `test-shortcut-wrapper.py` and `test-skill-writer.py` in batch 3).
- **Applies to:** all batches

### Decision: phase-4.7-prose-unchanged

- **Decision:** mill-setup Phase 4.7 does not enumerate the wrapped scripts (it says "every user-callable mill script" and reads `_shortcuts.SHORTCUT_SCRIPTS`), so adding `millpy-session-tasks` needs no Phase 4.7 prose change; Phase 8's wrapper check already iterates `SHORTCUT_SCRIPTS`.
- **Rationale:** the discussion asked the plan to check that prose; checked, nothing to edit.
- **Applies to:** setup-docs

## All Files Touched

- `SKILLS.md`
- `mill-config.yaml`
- `plugins/mill/scripts/_shortcuts.py`
- `plugins/mill/scripts/_vscode_keybindings.py`
- `plugins/mill/scripts/_vscode_tasks.py`
- `plugins/mill/scripts/millpy-session-tasks.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/skills/mill-session-tasks/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/skills/mill-spawn/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/templates/vscode-settings.json`
- `plugins/mill/templates/vscode-tasks.json`
- `plugins/mill/unit_tests/test-millpy-session-tasks.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-skill-writer.py`
- `plugins/mill/unit_tests/test-vscode-keybindings.py`
- `plugins/mill/unit_tests/test-vscode-tasks.py`
- `plugins/mill/unit_tests/test-vscode.py`
