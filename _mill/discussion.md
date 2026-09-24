# Discussion: Auto-name task sessions <slug>:<phase>

```yaml
task: Auto-name task sessions <slug>:<phase>
slug: session-naming
status: discussing
parent: main
```

## Problem

Claude Code sessions can only be named at launch (`claude -n <name>`) or by the user typing `/rename`.
A skill, a hook, a setting or an env var cannot rename a running session (confirmed against the Claude Code docs during discussion).
Mill task work runs in three phase sessions per task (`mill-start`, `mill-plan`, `mill-go`), plus `mill-quick` as an alternative to `mill-start`;
none of them is named, so the session picker is a list of anonymous sessions.

The original issue (#1151) proposed passing `-n <slug>:<phase>` where mill launches claude, or printing the ready command.
Exploration showed mill launches no phase session itself (`millpy-terminal.py` is the only launcher and the user does not use it), and the user opens sessions with VS Code keyboard shortcuts.
The design therefore moves to VS Code tasks bound to user-level keyboard shortcuts:
one keypress opens a correctly named, correctly configured (model + effort) claude session that immediately runs the phase skill.

## Scope

**In:**

- A mill-owned `.vscode/tasks.json`, seeded by `mill-spawn` into each new worktree and by `mill-setup` into its own (hub) worktree.
  Six tasks, none auto-run: `mill: start`, `mill: start-auto`, `mill: start-orch`, `mill: plan`, `mill: go`, `mill: quick`.
- Per-phase `model` and `effort` in `mill-config.yaml` (and its plugin template) under `spawn.sessions`, overridable in `config.local.yaml`.
- A small re-render CLI, `millpy-session-tasks.py`, that rewrites the current worktree's `tasks.json` from the current merged config (see "Stale config after spawn").
- Keyboard-shortcut seeding: `mill-setup` merges six `alt+shift+1` … `alt+shift+6` bindings into the user's global VS Code `keybindings.json`.
- `terminal.integrated.commandsToSkipShell` in the seeded `.vscode/settings.json` template so the shortcuts also work while focus is inside a terminal.
- Unit tests for the new rendering and merge helpers.

**Out:**

- `millpy-terminal.py` and the `mill-terminal` skill: unchanged (user does not use them; they already pass `--name <slug>`).
- The `Run /mill-x next` hand-off lines in mill-start, mill-plan, mill-quick, mill-pause, mill-go: unchanged. The earlier idea of printing `claude -n …` commands there is dropped.
- `mill-finalize`: no session, no task. mill-go invokes it in its own session; run manually it happens in the existing `:go` session.
- Reviewer/implementer subprocess launches of `claude` (`_llm_claude.py`, `_agent_dispatch.py`): non-interactive, not task sessions.
- Auto-opening terminals on folder open (`runOn: folderOpen`). Explicitly rejected.
- VS Code variants other than stable `Code` (Insiders, VSCodium) for the keybindings path.
- Renaming an already-running session (impossible).
- The "claude ready" default terminal the user wants removed: nothing in this repo creates it (no match for "claude ready"; no `tasks.json` was ever seeded; `.vscode/` is gitignored).
  It most likely comes from the Claude Code VS Code extension or the user's global VS Code config.
  mill-plan must grep once more for any repo-side source; if none is found, leave it out and say so in the final report.

## Decisions

### Session-name and phase vocabulary

- Decision: session name is `<slug>:<phase>` with phase in `start`, `plan`, `go`, `quick`.
  `start-auto` and `start-orch` are launch variants of `start` and both produce the session name `<slug>:start`.
- Rationale: the phase names match the skill the user types.
  Auto/orch describe how the skill runs, not which phase the session is.
- Rejected: raw `status.md` phases (`discussing`, `discussed`): less readable, and a session is not one status phase.

### Slug source

- Decision: `mill-spawn` bakes the literal slug into the rendered `tasks.json` at spawn time.
  `mill-setup` (hub worktree, no task slug) bakes `resolve_short_name(cfg, <repo-name>)` instead.
- Rationale: `${workspaceFolderBasename}` is the folder VS Code opened, which is the hub subfolder when `hub_relative_path` is not `.`, so it would not equal the slug.
- Rejected: `${workspaceFolderBasename}`; wrong in sub-project layouts.

### Not auto-run; explicit tasks

- Decision: tasks have no `runOptions.runOn`.
  The user starts one with a keyboard shortcut (or Run Task).
  Each task's `command` is one string: `claude -n "<slug>:<phase>" --model <model> --effort <effort> "/mill-<skill>[ <flag>]"`.
- Rationale: three terminals on every folder open is unwanted noise.
  A single command string avoids per-shell argument-quoting differences between PowerShell (Windows default profile in the template) and bash (Linux).
- Rejected: `runOn: folderOpen` for all three phases; `sendSequence` keybindings (no naming, no model/effort); a keybinding-only approach with `newWithProfile` (profiles cannot pass a prompt or `-n`; the user's existing model shortcuts use profiles and stay unchanged).

### Flags as separate tasks

- Decision: `mill-start` gets three tasks: plain, `--auto`, `--orch`.
  `plan`, `go` and `quick` get one each.
- Rationale: `--auto`/`--orch` cannot be added after the session starts today.
  Choosing at launch avoids a prompt step.
  Only mill-start has these flags; mill-plan and mill-go are unconditionally autonomous.
- Rejected: a `pickString` task input (extra keystroke per launch); typing the flag inside the session.

### Config shape

- Decision: new keys in `mill-config.yaml` and the plugin template `plugins/mill/templates/mill-config.yaml` (the two must stay in sync):

  ```yaml
  spawn:
    sessions:
      start: { model: opus, effort: medium }
      plan:  { model: opus, effort: medium }
      go:    { model: sonnet, effort: high }
      quick: { model: sonnet, effort: high }
  ```

  Values are passed verbatim to `--model` / `--effort` (effort levels: low, medium, high, xhigh, max).
  Overridable per worktree in `.millhouse/config.local.yaml`.
  `mill-spawn` resolves these from its own merged config, so a spawned child gets the same values as its parent.
- Rationale: user requirement: defaults opus/medium, opus/medium, sonnet/high; easy to change; effort settable.
  `quick` was not specified by the user; it defaults to the same as `go` (sonnet/high).
- Rejected: hard-coded defaults in Python; a separate config file.

### Stale config after spawn

- Decision: model and effort are baked into `tasks.json` when it is rendered, so editing `mill-config.yaml` or `config.local.yaml` later does not change worktrees that already exist.
  A new script `plugins/mill/scripts/millpy-session-tasks.py` re-renders the current worktree's `tasks.json` from the current merged config (slug from `_marker.slug_from_branch`; hub worktree: short name), reusing `_vscode_tasks.write_tasks` and the same idempotent/backup rules.
  Re-running `mill-setup` also refreshes the hub's file.
  New spawns always pick up the current config.
  The script gets the usual shortcut wrapper entry in `_shortcuts.SHORTCUT_SCRIPTS`.
- Rationale: user requirement is that values are easy to change; a re-render command makes "change config, run one command" the whole workflow without VS Code reading mill config at runtime.
- Rejected: accepting staleness silently; resolving model/effort at task run time (would need a wrapper script between VS Code and claude on both platforms).

### Keyboard shortcuts

- Decision: `alt+shift+1` … `alt+shift+6` in this order: start, start-auto, start-orch, plan, go, quick.
  Binding: `{"key": "alt+shift+N", "command": "workbench.action.tasks.runTask", "args": "mill: <task>"}`.
- Rationale: verified against `~/SHORTCUTS.md` and the live `~/.config/xremap/config.yml`: `Ctrl+Shift+1–5` (desktop jump), `Ctrl+Shift+Alt+1–5` (move window), `Meta+Alt+1–4` (tiling) and `Ctrl+Alt+H/L` are taken on Linux; `Alt+Shift+<digit>` is not.
  `Ctrl+Alt+<digit>` is AltGr on Windows (norwegian `{ } [ ]`), `Meta+<digit>` belongs to the OS.
  Digits were preferred over mnemonic letters (user finds letters illogical).
  Windows key bindings of the user are unknown; mill-plan must not assume `Alt+Shift+<digit>` is free there beyond the skip-and-warn behaviour below.
- Rejected: `Shift+Ctrl+Alt+D/A/R/P/G/Q`; `Ctrl+Shift+<digit>`; `Ctrl+Alt+<digit>`; `Ctrl+K <digit>` chords.

### Keybindings are global, not per worktree

- Decision: VS Code has only user-level keybindings; there is no workspace keybindings file.
  Task labels are identical across worktrees, so one binding set works everywhere.
  `mill-setup` writes it (idempotent); `mill-spawn` does not touch it.
- Locations: Linux `~/.config/Code/User/keybindings.json`; Windows `%APPDATA%\Code\User\keybindings.json`; macOS `~/Library/Application Support/Code/User/keybindings.json`.
- The file is JSONC (comments allowed; the user's has `//` comments), so it must not be round-tripped through a strict JSON parse/dump.
  Insert/replace a marker-delimited block (`// mill:begin` … `// mill:end`) textually inside the top-level array; create the file with the block if it is missing.
- Conflict detection: strip `//` line comments and `/* */` block comments outside string literals with a small tokenizer, tolerate trailing commas, then `json.loads` the result and inspect entries outside the mill block (compare `key` case-insensitively, ignoring whitespace).
  If a target key (`alt+shift+N`) is already bound by such an entry, skip that binding and print a warning naming the key and command.
  Never overwrite.
- If the file cannot be parsed after stripping, skip all six bindings, leave the file untouched, and print a warning; `mill-setup` continues.
- Rejected: overwrite on conflict; writing keybindings from `mill-spawn` on every spawn.

### Terminal-focus behaviour

- Decision: add `"terminal.integrated.commandsToSkipShell": ["workbench.action.tasks.runTask"]` to `plugins/mill/templates/vscode-settings.json`.
  Without it, VS Code forwards the keypress to the terminal instead of running the command when focus is in a terminal (the normal state when a claude session is open).
  mill-plan must verify this against VS Code docs/behaviour, since it is stated from knowledge, not tested.
  Fallback if verification shows the key is unnecessary: drop it from the template.
  Fallback if the shortcuts still do not fire with terminal focus: keep the key, document in the mill-setup report that the shortcuts work with editor focus or via Run Task, and do not add further workarounds.
- `mill-setup` Phase 7 currently skips an already-green `.vscode/settings.json`.
  Extend the skip condition: skip only if the colour is green **and** `commandsToSkipShell` already contains `workbench.action.tasks.runTask`; otherwise back up to `.bak` and overwrite, as the existing "different" rows do.
- `task.allowAutomaticTasks: "on"` is already in the template; no change (harmless with no auto-run tasks).

### tasks.json ownership and idempotency

- Decision: `tasks.json` is mill-owned and starts with a `// managed by mill` comment line (tasks.json is JSONC).
  `mill-spawn` always writes it (fresh worktree), with rollback on spawn failure alongside the existing `.vscode/settings.json` rollback.
  `mill-setup` writes it in a new Phase 7b, rewriting only when content differs; an existing file without the managed marker is backed up to `tasks.json.bak` first.
- Rationale: mirrors how `.vscode/settings.json` is already handled in Phase 7 and in `millpy-spawn.py`.
- Rejected: merging into a user's own tasks.json.

### Module layout

- Decision: two new helpers in `plugins/mill/scripts/`, flat like the rest:
  `_vscode_tasks.py` (`render_tasks(slug_or_name, sessions_cfg) -> str`, `write_tasks(target, ...)`) and `_vscode_keybindings.py` (`keybindings_path(platform)`, `merge_bindings(text) -> (text, skipped)`, `write_bindings()`).
  A `tasks.json` template lives in `plugins/mill/templates/vscode-tasks.json` and is rendered through `_render`, same as `vscode-settings.json`.
- Rationale: follows `_vscode.py`'s separation of rendering from the caller's when-to-write decision.

## Technical context

- `plugins/mill/scripts/_vscode.py`: `render_settings` / `write_settings` render `templates/vscode-settings.json` via `_render.render`.
  New tasks helper should mirror its API and docstring style.
- `plugins/mill/scripts/millpy-spawn.py` (around lines 261–271): picks a colour, writes `dest_hub / ".vscode" / "settings.json"` and pushes a rollback lambda onto `_cleanup_stack`.
  `cfg` and `slug` are in scope; `dest_hub` (not `worktree_path`) is where `.vscode/` goes when `hub_relative_path` is set.
  Add the tasks write right after, with its own rollback lambda.
- `plugins/mill/skills/mill-setup/SKILL.md`: Phase 7 (VS Code window colour, ~line 505) is where the hub's `settings.json` is written and skipped when green.
  Add Phase 7b (tasks.json + keybindings), extend Phase 7's skip rule, update Phase 8 verify/report, `## Idempotency`, and the helper list on line ~91.
- Config loading: `_config.load_config(hub_root, worktree_root)` deep-merges `mill-config.yaml` and `.millhouse/config.local.yaml`.
  Existing `spawn:` section holds only `branch_prefix`; read `cfg["spawn"]["sessions"]` with per-key fallback to the defaults above when absent.
  Check whether `_config` has a defaults/schema table that needs the new keys.
- `_paths.resolve_short_name(cfg, repo_name)`: hub-side name for `mill-setup`.
- `claude --help` (2.1.281): `-n/--name`, `--model <model>`, `--effort <low|medium|high|xhigh|max>`, positional `[prompt]`.
  That an initial prompt of `/mill-start …` is executed as a slash command in interactive mode is expected but must be verified by mill-plan/implementer before relying on it.
  Fallback if it is passed as plain text instead: render the task prompt as `Invoke the mill:mill-<skill> skill with args "<flag>"` (omit args when there is no flag), which makes the model call the Skill tool; the task labels, session names and everything else stay the same.
  The hub worktree's session names use `<short_name>:<phase>` (no task slug exists there).
- User's existing model shortcuts (`~/.config/Code/User/keybindings.json`) use `workbench.action.terminal.newWithProfile` with `ctrl+shift+alt+{o,f,s}`; they are untouched and cannot collide with `alt+shift+<digit>`.
- Repo conventions: `print()` output ASCII only; no `sed`; no junction paths to Python helpers; `_mill/` paths never cited from permanent docs.

## Constraints

- `mill-config.yaml` (hub) and `plugins/mill/templates/mill-config.yaml` must stay in sync.
- Never write outside the worktree except the user-level keybindings file, and only from `mill-setup`, only inside the mill marker block.
- Windows and Linux must both work; keybindings path and the task `command` string must not depend on a POSIX shell.
- Unit tests use in-memory/tempfile fixtures; no real VS Code, git or LLM.
  Keybindings tests must redirect the target path to a tempfile (never the real user file).

## Testing

- **`_vscode_tasks`** (TDD candidate): rendered JSON parses after stripping the leading comment; six tasks with the expected labels; slug and per-phase model/effort appear in the command strings; `start-auto`/`start-orch` carry the flag and the `:start` session name; missing config keys fall back to defaults; overridden values are honoured.
- **`_vscode_keybindings`** (TDD candidate): creates the file when missing; inserts the block into an existing JSONC array without disturbing comments or other entries; re-running is idempotent (no diff); updates the block when bindings change; skips and reports a conflicting `alt+shift+N` bound outside the block; leaves entries inside the block replaceable; platform path resolution for linux/win/darwin.
- **`millpy-session-tasks.py`**: re-render after a config change updates model/effort in the existing file; unchanged config leaves the file byte-identical; hub versus task-worktree name selection.
- **Keybindings parser**: comments inside and outside strings (`//` in a string value is not a comment), trailing commas, and unparsable input (nothing written, warning emitted).
- **`millpy-spawn`**: existing spawn tests extended to assert `tasks.json` exists in `dest_hub/.vscode/` with the literal slug, including the `hub_relative_path != "."` layout, and that rollback removes it.
- **`test-vscode.py`**: template now contains `commandsToSkipShell`.
- **mill-setup**: Phase 7 skip-rule change and Phase 7b idempotency are skill prose; cover the helper-level behaviour in unit tests and list manual verification steps in the plan (open a worktree, press `Alt+Shift+4` inside and outside a terminal).
- Manual/verification items for mill-plan: slash-prompt executes as a command; `commandsToSkipShell` need; no default VS Code binding on `alt+shift+<digit>`.

## Q&A log

- **Q:** Which phase vocabulary in `<slug>:<phase>`? **A:** Skill names start/plan/go, plus quick; finalize gets no name (mill-go calls it in its own session, no spawned agent).
- **Q:** Can a skill rename the session itself? **A:** No; confirmed no skill/tool/hook/setting/env path exists. Only `-n` at launch or `/rename`.
- **Q:** Auto-open three terminals via `runOn: folderOpen`? **A:** Rejected by the user; too noisy. Tasks are started explicitly with shortcuts.
- **Q:** How are `--auto`/`--orch` chosen? **A:** Separate tasks per variant, each with its own shortcut.
- **Q:** Default models? **A:** start opus/medium, plan opus/medium, go sonnet/high; effort configurable; easy to edit in mill-config; `quick` unspecified, defaulted to go's values.
- **Q:** Who seeds keybindings? **A:** `mill-setup`, automatically; tasks.json is seeded per worktree by `mill-spawn` and by `mill-setup` in its own worktree; spawn reuses its own resolved config values for the child.
- **Q:** Shortcut keys? **A:** `Alt+Shift+1..6`, chosen after checking `~/SHORTCUTS.md` and xremap config; letters rejected as illogical.
- **Q:** Conflicting existing binding? **A:** Skip and warn; never overwrite.
- **Q:** Remove the "claude ready" terminal? **A:** Requested, but no repo-side source was found; treated as out of scope unless mill-plan finds one.
