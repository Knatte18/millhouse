# Batch: tasks-render

```yaml
task: "Auto-name task sessions <slug>:<phase>"
batch: "tasks-render"
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-vscode-tasks.py test-vscode.py test-config.py
depends-on: []
```

## Batch Scope

Delivers the `spawn.sessions` config keys, the `tasks.json` template, the `_vscode_tasks` rendering/writing helper, and the `commandsToSkipShell` entry in the settings template.
This is one batch because the helper, its template and the config defaults must agree on the same phase vocabulary and default values; later batches (keybindings, CLI, spawn wiring, skill docs) all consume `_vscode_tasks`.
External interface consumed by later batches: `_vscode_tasks.TASK_SPECS`, `_vscode_tasks.LABEL_PREFIX`, `_vscode_tasks.DEFAULT_SESSIONS`, `_vscode_tasks.resolve_sessions`, `_vscode_tasks.render_tasks`, `_vscode_tasks.write_tasks`.

## Cards

### Card 1: Seed spawn.sessions config keys (bootstrap card)

- **Context:**
  - `plugins/mill/scripts/_vscode.py`
- **Edits:**
  - `mill-config.yaml`
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a `sessions:` mapping under the existing `spawn:` block in both files, with identical values: `start: { model: opus, effort: medium }`, `plan: { model: opus, effort: medium }`, `go: { model: sonnet, effort: high }`, `quick: { model: sonnet, effort: high }`.
  In `plugins/mill/templates/mill-config.yaml`, extend the existing `# mill-spawn` comment block above `spawn:` with a `sessions` paragraph: values are passed verbatim to `claude --model` / `--effort`; effort levels are low, medium, high, xhigh, max; `quick` defaults to the same values as `go`; override per worktree in `.millhouse/config.local.yaml`; run `millpy-session-tasks` after changing values to refresh an existing worktree's `.vscode/tasks.json`.
  Bootstrap safety (why this `mill-config.yaml` edit is safe mid-flight): the only consumer of `spawn.sessions` is the new `_vscode_tasks.resolve_sessions`, which falls back per key to built-in defaults when a key is absent, and no existing code reads `spawn:` beyond `branch_prefix`.
  A stale plugin cache or an un-updated hub config therefore behaves identically before and after this change.
  The hub `mill-config.yaml` and the plugin template must stay in sync.
- **Commit:** `feat(config): add spawn.sessions model/effort defaults per phase`

### Card 2: Add tasks.json template and _vscode_tasks helper

- **Context:**
  - `plugins/mill/scripts/_vscode.py`
  - `plugins/mill/scripts/_render.py`
  - `plugins/mill/templates/vscode-settings.json`
- **Edits:** none
- **Creates:**
  - `plugins/mill/templates/vscode-tasks.json`
  - `plugins/mill/scripts/_vscode_tasks.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `plugins/mill/scripts/_vscode_tasks.py`, mirroring `_vscode.py`'s module-docstring style (public-API list, caller-decides-when-to-write note) and loading its template through `_render.render`.
  Module constants: `LABEL_PREFIX = "mill: "`; `MANAGED_MARKER = "// managed by mill"`; `DEFAULT_SESSIONS = {"start": {"model": "opus", "effort": "medium"}, "plan": {"model": "opus", "effort": "medium"}, "go": {"model": "sonnet", "effort": "high"}, "quick": {"model": "sonnet", "effort": "high"}}`; `TASK_SPECS`, an ordered tuple of `(task_key, phase, flag)` triples: `("start", "start", None)`, `("start-auto", "start", "--auto")`, `("start-orch", "start", "--orch")`, `("plan", "plan", None)`, `("go", "go", None)`, `("quick", "quick", None)`.
  A task's label is `LABEL_PREFIX + task_key`.
  Functions:
  - `resolve_sessions(sessions_cfg: dict | None) -> dict[str, dict[str, str]]` returns a complete `{phase: {"model", "effort"}}` mapping; every missing or empty key (including a `None`/non-dict input, a missing phase, a missing `model` or `effort`) falls back per key to `DEFAULT_SESSIONS`; values are stripped `str`s; a value that is not a plain token (allowed characters: letters, digits, `.`, `_`, `-`, `[`, `]`, `:`; must not be empty or start with `-`) raises `ValueError` naming the phase and key.
  - `build_command(name: str, phase: str, model: str, effort: str, flag: str | None = None) -> str` returns exactly `claude -n "<name>:<phase>" --model <model> --effort <effort> "<prompt>"`, where the prompt comes from a single private helper `_prompt(phase, flag)` returning `/mill-<phase>` or `/mill-<phase> <flag>`.
  Keep the prompt construction in that one helper so the plain-text fallback (`Invoke the mill:mill-<phase> skill with args "<flag>"`) is a one-function change if the slash form turns out not to execute as a command.
  - `render_tasks(name: str, sessions_cfg: dict | None = None) -> str` validates `name` (non-empty, no `"`, backslash, `$`, backtick or control characters, else `ValueError`; `$` and backtick would expand inside the double quotes in both bash and PowerShell), resolves sessions, builds one command per `TASK_SPECS` entry, JSON-escapes each command (the inner text of `json.dumps(command)`), and substitutes the tokens `<CMD_START>`, `<CMD_START_AUTO>`, `<CMD_START_ORCH>`, `<CMD_PLAN>`, `<CMD_GO>`, `<CMD_QUICK>` into the template.
  - `write_tasks(target: Path, name: str, sessions_cfg: dict | None = None) -> str` renders and writes with these rules and returns a status string: `"created"` when `target` did not exist; `"unchanged"` (no write) when existing content is byte-identical; `"updated"` when an existing file that starts with `MANAGED_MARKER` differs (overwritten, no backup); `"replaced"` when an existing file does not start with `MANAGED_MARKER` (first copied to `<target name>.bak` beside it, overwriting any older `.bak`, then overwritten).
  Creates parent directories as needed.
  Create `plugins/mill/templates/vscode-tasks.json`: first line `// managed by mill`, then a JSON object with `"version": "2.0.0"` and a `"tasks"` array of six shell tasks labelled `mill: start`, `mill: start-auto`, `mill: start-orch`, `mill: plan`, `mill: go`, `mill: quick`, in that order.
  Each task has `"type": "shell"`, its own `"command": "<CMD_...>"` token, `"presentation": {"reveal": "always", "panel": "new", "focus": true}` and `"problemMatcher": []`; no task has `runOptions`.
  All output produced by these helpers is ASCII.
- **Commit:** `feat(vscode): render mill session tasks.json from spawn.sessions config`

### Card 3: Unit tests for _vscode_tasks

- **Context:**
  - `plugins/mill/scripts/_vscode_tasks.py`
  - `plugins/mill/templates/vscode-tasks.json`
  - `plugins/mill/templates/mill-config.yaml`
  - `plugins/mill/unit_tests/test-vscode.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-vscode-tasks.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-vscode-tasks.py` following `test-vscode.py`'s structure (sys.path insert of the scripts dir, `errors` list, PASS/FAIL prints, `main()` returning 0 or 1, tempfile fixtures only).
  Cover: the rendered text starts with `MANAGED_MARKER` and parses with `json.loads` after dropping that first line; exactly six tasks with the expected labels in order; the slug, per-phase model and per-phase effort appear in each command string; `start`, `start-auto` and `start-orch` all carry the session name `<slug>:start` while `start-auto`/`start-orch` prompts end in ` --auto"` / ` --orch"`; `plan`, `go` and `quick` use `:plan`, `:go`, `:quick`; no task contains `runOptions`; missing config keys fall back to `DEFAULT_SESSIONS` per key (e.g. only `go.effort` overridden leaves every other value at its default); overridden values are honoured; `resolve_sessions(None)` equals `DEFAULT_SESSIONS`; an invalid model value and a slug containing `"`, `$` or a backtick raise `ValueError`.
  `write_tasks` cases against a tempdir: `created` on a missing file (parent dir created), `unchanged` on a second call with the file's bytes and mtime preserved, `updated` after a config change with no `.bak` created, `replaced` for an existing file without the marker with the old content preserved in `tasks.json.bak`.
  Add a consistency test: `spawn.sessions` parsed with `yaml.safe_load` from `plugins/mill/templates/mill-config.yaml` equals `DEFAULT_SESSIONS`.
- **Commit:** `test(vscode): cover _vscode_tasks rendering, writing and config fallbacks`

### Card 4: commandsToSkipShell in settings template

- **Context:**
  - `plugins/mill/scripts/_vscode.py`
- **Edits:**
  - `plugins/mill/templates/vscode-settings.json`
  - `plugins/mill/unit_tests/test-vscode.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/templates/vscode-settings.json`, add the key `"terminal.integrated.commandsToSkipShell": ["workbench.action.tasks.runTask"]` directly after `"task.allowAutomaticTasks": "on"`, keeping the file valid JSON.
  Rationale, verified against the VS Code terminal docs during planning: commands on that setting's list have their keybindings handled by VS Code instead of being sent to the shell when a terminal has focus, and `workbench.action.tasks.runTask` is not documented as part of the default list, so the key is kept.
  In `plugins/mill/unit_tests/test-vscode.py`, extend `_test_render_settings` with a check that the output of `render_settings` parses with `json.loads` and that `["terminal.integrated.commandsToSkipShell"]` equals `["workbench.action.tasks.runTask"]`; print a PASS line in the file's existing style.
- **Commit:** `feat(vscode): let runTask shortcuts skip the shell when a terminal has focus`

## Batch Tests

`verify:` runs `test-vscode-tasks.py` (new), `test-vscode.py` (template assertion) and `test-config.py` (guards against the two `mill-config.yaml` edits breaking config loading or template sync).
All three are self-contained unit tests with tempfile fixtures; no real VS Code, git or LLM.
