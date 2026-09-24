# Batch: setup-docs

```yaml
task: "Auto-name task sessions <slug>:<phase>"
batch: "setup-docs"
number: 5
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-skill-helper-drift.py
depends-on: [1, 2, 3]
```

## Batch Scope

Updates the two skill documents that describe the behaviour delivered in batches 1-4: `mill-setup` (Phase 7 skip rule, new Phase 7b for `tasks.json` and keybindings, Phase 8 verification and report, idempotency, helper list) and `mill-spawn` (mentions the seeded `tasks.json`).
Docs-only batch: the runnable check is the skill helper-reference drift guard, which fails if any `_module.function(` reference in a SKILL.md does not resolve to a shipped function.

## Cards

### Card 12: mill-setup Phase 7 skip rule, Phase 7b, Phase 8, idempotency

- **Context:**
  - `plugins/mill/scripts/_vscode_tasks.py`
  - `plugins/mill/scripts/_vscode_keybindings.py`
  - `plugins/mill/scripts/millpy-session-tasks.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/templates/vscode-settings.json`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Edit `plugins/mill/skills/mill-setup/SKILL.md` in these places, keeping its existing prose conventions (one sentence per line, ASCII-only commands):
  - The helper list near the top ("Helpers used by this skill: ..."): add `_vscode_tasks` (Phase 7b) and `_vscode_keybindings` (Phase 7b), and extend the `_render` note to include `_vscode_tasks`.
  - Phase 7 table: change the "Present and green" row so it skips only when `titleBar.activeBackground` is `#2d7d46` **and** `terminal.integrated.commandsToSkipShell` already contains `workbench.action.tasks.runTask`; a green file that lacks that entry is backed up to `.vscode/settings.json.bak` and overwritten like the "different colour" rows.
  - Add `### Phase 7b - VS Code session tasks and shortcuts` after Phase 7 with two steps.
  Step 1 (tasks.json): run `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "<VENV_PYTHON>" -c "from pathlib import Path; import yaml; import _vscode_tasks; from _paths import resolve_short_name; cfg = yaml.safe_load(Path(r'<cwd>/mill-config.yaml').read_text(encoding='utf-8')); print(_vscode_tasks.write_tasks(Path('.vscode/tasks.json'), resolve_short_name(cfg, '<repo-name>'), (cfg.get('spawn') or {}).get('sessions')))"`, but with `cfg` loaded as `_config.load_config(hub_root=_paths.resolve_hub_path(), worktree_root=_paths.resolve_git_root())` instead of a bare `yaml.safe_load` of the hub file, so the layered config (template defaults, hub `mill-config.yaml`, `.millhouse/config.local.yaml`) is the same one `millpy-session-tasks` uses and a re-run of mill-setup never discards local `spawn.sessions` overrides; explain that the printed status is `created`, `unchanged`, `updated`, or `replaced` (an existing file without the `// managed by mill` first line is backed up to `.vscode/tasks.json.bak` first), that the hub's session names use the short name because no task slug exists there, and that model/effort come from `spawn.sessions` and are refreshed by re-running mill-setup or `millpy-session-tasks`.
  Step 2 (keybindings): run `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "<VENV_PYTHON>" -c "import _vscode_keybindings as k; s, w = k.write_bindings(); print(s); [print('WARNING: ' + x) for x in w]"`; explain that it merges six bindings `alt+shift+1` to `alt+shift+6` (start, start-auto, start-orch, plan, go, quick) into the user-level stable-VS-Code `keybindings.json` inside a `// mill:begin` / `// mill:end` block, that a key already bound outside the block is skipped with a warning and never overwritten, that an unparsable file or a missing VS Code user directory skips all six bindings with a warning while mill-setup continues, and that mill-spawn never touches this file.
  Add the two manual verification steps the plan calls for: open a worktree and press `Alt+Shift+4` with editor focus and with terminal focus; if the shortcut does not fire with terminal focus, keep the settings entry, tell the user shortcuts work with editor focus or via Run Task, and add no further workaround.
  - Phase 8 invariants list: add that `.vscode/tasks.json` exists and its first line is `// managed by mill`, and that `.vscode/settings.json` `terminal.integrated.commandsToSkipShell` contains `workbench.action.tasks.runTask`.
  Add two lines to the summary block: `VS Code tasks:  .vscode/tasks.json (<status>)` and `Keybindings:   <status> (<N> warnings)`, and print any warnings after the block.
  - `## Idempotency` list: add that `.vscode/tasks.json` is rewritten only when content differs and an unmarked file is backed up first (Phase 7b), that the keybindings block is replaced in place and an unchanged file is not rewritten (Phase 7b), and change the `.vscode/settings.json already green -> skipped` line to reflect the new skip condition.
- **Commit:** `docs(mill-setup): add Phase 7b tasks.json and keybindings, extend Phase 7 skip rule`

### Card 13: mill-spawn skill mentions tasks.json

- **Context:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Edits:**
  - `plugins/mill/skills/mill-spawn/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/skills/mill-spawn/SKILL.md`, extend the sentence that lists what mill-spawn does (the one ending "assigns a VS Code title-bar color, and writes the initial `_mill/status.md`") so it also says it seeds `.vscode/tasks.json` with the six session launch tasks (`mill: start`, `start-auto`, `start-orch`, `plan`, `go`, `quick`; session names `<slug>:<phase>`, model and effort from `spawn.sessions`), and add one short paragraph below it: the keyboard shortcuts for those tasks are user-level and are seeded by `/mill-setup`, not by mill-spawn; run `millpy-session-tasks` in a worktree after changing `spawn.sessions` to refresh its `tasks.json`.
  Do not add any `_module.function(` style helper reference.
- **Commit:** `docs(mill-spawn): document seeded session tasks`

## Batch Tests

`verify:` runs `test-skill-helper-drift.py`, the guard that every `_module.function(` reference in a SKILL.md resolves to a shipped function; the new Phase 7b commands reference `_vscode_tasks.write_tasks` and `_vscode_keybindings.write_bindings`, both created in earlier batches.
The rest of this batch is prose with no runnable surface.

Manual verification checklist (run once after merge, not automated):

1. Press `Alt+Shift+4` in a worktree with editor focus and with a terminal focused; the `mill: plan` task should open a terminal running `claude -n "<slug>:plan" ...`.
2. Confirm the initial prompt `/mill-plan` executes as a slash command in the interactive session; if it arrives as plain text, switch `_prompt` in `_vscode_tasks.py` to the `Invoke the mill:mill-<phase> skill with args "<flag>"` form and re-render.
3. Confirm no default VS Code binding exists on `alt+shift+<digit>` (Keyboard Shortcuts editor, search `alt+shift+1`).
