# Batch: core-helpers

```yaml
task: Prefix session names with repo short name; add MH:orch session
batch: core-helpers
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-vscode-tasks.py test-vscode-keybindings.py test-paths-short-name.py test-setup-short-name.py
depends-on: []
```

## Batch Scope

Delivers every shared helper the callers in batch 2 and the docs in batch 3 consume:
`_vscode_tasks.session_prefix`, the hub-only `orch` task (`HUB_TASK_SPECS`, `hub=True` on `render_tasks`/`write_tasks`, the `<HUB_TASKS>` template token and the orch fragment template), phase-scoped `resolve_sessions`, the `orch` model/effort default in code and in both config files, `_paths.short_name_is_derived`, and `_setup.set_repo_short_name`.
These are leaf helpers with no dependency on the scripts that call them, so they land first and are unit-tested in isolation.

## Cards

### Card 1: session_prefix, hub-only orch task and orch session defaults

- **Context:**
  - `plugins/mill/scripts/_render.py`
  - `plugins/mill/scripts/_vscode_keybindings.py`
- **Edits:**
  - `plugins/mill/scripts/_vscode_tasks.py`
  - `plugins/mill/templates/vscode-tasks.json`
  - `plugins/mill/templates/mill-config.yaml`
  - `mill-config.yaml`
  - `plugins/mill/unit_tests/test-vscode-tasks.py`
- **Creates:**
  - `plugins/mill/templates/vscode-tasks-orch.json`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/_vscode_tasks.py`:
  - Add `"orch": {"model": "opus", "effort": "high"}` as the last entry of `DEFAULT_SESSIONS`.
  - Keep `TASK_SPECS` unchanged. Add `HUB_TASK_SPECS: tuple[tuple[str, str, str | None], ...] = TASK_SPECS + (("orch", "orch", None),)` directly after it, with a one-line comment that it is the hub-only spec list.
  - Add `_NO_PROMPT_PHASES = frozenset({"orch"})`. In `build_command`, when `phase in _NO_PROMPT_PHASES`, return `f'claude -n "{name}:{phase}" --model {model} --effort {effort}'` with no trailing quoted prompt; every other phase keeps today's output byte-for-byte. `_prompt` stays unchanged.
  - Add `session_prefix(short_name: str, slug: str | None = None) -> str`. It raises `ValueError` when `short_name` is empty, contains `:`, or fails `_validate_name`; it builds `short_name` (hub) or `f"{short_name}:{slug}"` (worktree), runs `_validate_name` on that result, and returns it `.lower()`. Docstring states it is the only place a session name is lower-cased.
  - `resolve_sessions(sessions_cfg: dict | None, phases: Iterable[str] | None = None)`: when `phases` is `None`, resolve every `DEFAULT_SESSIONS` key (so `resolve_sessions(None) == DEFAULT_SESSIONS` still holds); otherwise resolve and validate only the listed phases, iterating in `DEFAULT_SESSIONS` order. A listed phase that is not a `DEFAULT_SESSIONS` key raises `ValueError`. Update its docstring.
  - `render_tasks(name, sessions_cfg=None, *, hub: bool = False)`: pick `specs = HUB_TASK_SPECS if hub else TASK_SPECS`; call `resolve_sessions(sessions_cfg, phases={phase for _, phase, _ in specs})`; fill `CMD_<KEY>` tokens exactly as today for every spec. Then set `values["HUB_TASKS"]`: for `hub=False` the empty string; for `hub=True` the output of `_render.render(_ORCH_TEMPLATE_PATH, {"CMD_ORCH": values.pop("CMD_ORCH")})` with trailing newlines stripped (`.rstrip("\n")`). `_ORCH_TEMPLATE_PATH` sits next to `_TEMPLATE_PATH` and points at `templates/vscode-tasks-orch.json`. `_validate_name(name)` still runs first. Update the docstring (`name` is now the prefix built by `session_prefix`; document `hub`).
  - `write_tasks(target, name, sessions_cfg=None, *, hub: bool = False)` passes `hub` through to `render_tasks`; everything else unchanged.
  - Rewrite the module docstring: sessions are named `<prefix>:<phase>`, where the prefix comes from `session_prefix` (`<short_name>:<slug>` in a task worktree, `<short_name>` on the hub, lower-cased); the hub additionally gets the `orch` task. Update the Public API block for `HUB_TASK_SPECS`, `session_prefix`, and the new `resolve_sessions`/`render_tasks`/`write_tasks` signatures.

  In `plugins/mill/templates/vscode-tasks.json`: append the literal token `<HUB_TASKS>` directly after the closing `}` of the `mill: quick` task object, on the same line (the line becomes `        }<HUB_TASKS>`), so the empty-string render leaves the file byte-identical to today's output.

  Create `plugins/mill/templates/vscode-tasks-orch.json` containing, first, a line holding only `,` and then one task object in the same shape and indentation (8 spaces) as the other tasks: `"label": "mill: orch"`, `"type": "shell"`, `"command": "<CMD_ORCH>"`, the same `presentation` and `problemMatcher` lines. No HTML comment at the top (it would be rendered into tasks.json). The fragment's text after rendering and stripping trailing newlines must slot in so the hub output stays valid JSON after the `MANAGED_MARKER` line.

  In `plugins/mill/templates/mill-config.yaml`: add `orch: { model: opus, effort: high }` as the last entry under `spawn.sessions`; extend the `sessions` comment block with one line saying `orch` applies to the hub's `.vscode/tasks.json` only and starts with no initial prompt; extend the `short_name` comment so it says the value is also the (lower-cased) prefix of Claude Code session names: `<short_name>:<phase>` on the hub, `<short_name>:<slug>:<phase>` in a worktree.

  In the hub `mill-config.yaml` (bootstrap justification for the `wiki-config-mutation` check): add `orch: { model: opus, effort: high }` as the last entry under `spawn.sessions`. This addition is safe mid-flight: the running cached `_vscode_tasks.resolve_sessions` iterates only its own `DEFAULT_SESSIONS` keys and ignores unknown `spawn.sessions` keys, and `spawn.sessions` has no other reader, so every in-flight spawn and session-tasks run behaves exactly as before until the new code ships.

  In `plugins/mill/unit_tests/test-vscode-tasks.py`, keep the existing test structure and add/update:
  - Worktree render with `render_tasks(session_prefix("MH", "my-task"))`: every `TASK_SPECS` entry produces `claude -n "mh:my-task:<phase>" ...` with its prompt; there is no `mill: orch` label; output parses as JSON after the marker line; output is byte-identical to a render where the template had no `<HUB_TASKS>` token (assert the text contains no `<HUB_TASKS>` and the six labels in order).
  - Hub render with `render_tasks(session_prefix("MH"), hub=True)`: the six tasks named `mh:<phase>` in the old order, then `mill: orch` whose command is exactly `claude -n "mh:orch" --model opus --effort high`; output parses as JSON after the marker line.
  - `spawn.sessions.orch` override (`{"orch": {"model": "sonnet", "effort": "max"}}`) reaches the hub orch command.
  - An invalid `{"orch": {"model": "a b"}}` raises `ValueError` for a hub render and does not raise for a worktree render.
  - `resolve_sessions({}, phases=["go"])` returns only the `go` key; `resolve_sessions(None)` still equals `DEFAULT_SESSIONS`; an unknown phase in `phases` raises `ValueError`.
  - `session_prefix("MH") == "mh"`, `session_prefix("MH", "my-task") == "mh:my-task"`; `session_prefix("")`, `session_prefix("M:H")`, `session_prefix('M"H')` each raise `ValueError`.
  - `write_tasks(..., hub=True)` writes the hub render.
  - Existing forbidden-character name tests still pass unchanged; existing `_test_render` assertions keep working for the plain `SLUG` prefix (its six-label check stays).
  - `_test_template_defaults_consistent` is unchanged and must pass because the template now carries `orch`.
- **Commit:** `feat(vscode-tasks): add session_prefix and hub-only orch session task`

### Card 2: derived short-name predicate in _paths

- **Context:**
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-paths-short-name.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/_paths.py`, add `short_name_is_derived(cfg: dict) -> bool` directly after `resolve_short_name`.
  It returns `True` exactly when `resolve_short_name` would use its fallback: the `repo` block is absent or not a dict, `short_name` is missing, or its value is falsy (e.g. `""`).
  Read the block as `cfg.get("repo") or {}` so `repo: null` counts as absent.
  It prints nothing.
  Add `"short_name_is_derived"` to `__all__` right after `"resolve_short_name"`, and add a two-line entry for it to the module docstring's Public API list after the `resolve_short_name` family (keep the docstring's existing style).

  Create `plugins/mill/unit_tests/test-paths-short-name.py` in the repo's plain-script test style (a `main()` returning 0/1, `PASS:`/`FAIL:` lines, `sys.path` insert of `plugins/mill/scripts` as the sibling tests do). Cases: `{}` -> True; `{"repo": None}` -> True; `{"repo": {}}` -> True; `{"repo": {"short_name": ""}}` -> True; `{"repo": {"short_name": "MH"}}` -> False.
- **Commit:** `feat(paths): add short_name_is_derived predicate`

### Card 3: line-level repo.short_name writer in _setup

- **Context:**
  - `plugins/mill/templates/mill-config.yaml`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/scripts/_setup.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-setup-short-name.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/_setup.py`, add a module constant `SHORT_NAME_RE = re.compile(r"^[A-Za-z0-9]{2,4}$")` and a function `set_repo_short_name(config_path: Path, value: str) -> bool`.
  Behaviour:
  - Raise `ValueError` (writing nothing) when `value` does not fullmatch `SHORT_NAME_RE`.
  - Read the file as UTF-8 and split with `splitlines(keepends=True)`; use `"\r\n"` for any inserted line when the file's first line ending is `"\r\n"`, else `"\n"`.
  - Locate the top-level `repo:` line (regex `^repo:\s*(#.*)?$` on the line without its ending). The block is every following line that is blank, a comment, or indented, up to the next non-indented, non-blank, non-comment line.
  - If the block has a line matching `^(?P<indent>[ \t]+)short_name:(?P<ws>[ \t]*)(?P<val>"[^"]*"|'[^']*'|[^\s#]*)(?P<rest>.*)$`, replace that one line with `f"{indent}short_name: {value}{rest}"` plus its original line ending; `rest` keeps the whitespace and trailing comment (the template line `  short_name: ""    # e.g. "MH" for millhouse` becomes `  short_name: MH    # e.g. "MH" for millhouse`).
  - If the `repo:` block exists without a `short_name:` line, insert `  short_name: <value>` right after the `repo:` line, using the indent of the block's first indented non-comment line when there is one, else two spaces.
  - If a top-level `repo:` line carries an inline value (e.g. `repo: {}`), raise `ValueError` — flow style is not edited.
  - If there is no `repo:` line, insert `repo:` and `  short_name: <value>` as the first two lines of the file.
  - Before writing, `yaml.safe_load` the new text and raise `ValueError` (writing nothing) unless `["repo"]["short_name"] == value`; import `yaml` locally inside the function to keep module import cost unchanged.
  - Never round-trip through `yaml.dump`: every line other than the replaced/inserted ones stays byte-identical.
  - Return `True` when the file changed, `False` when the new text equals the old text (the file is then not rewritten).
  Add a Public API entry for `set_repo_short_name` and `SHORT_NAME_RE` to the module docstring in its existing style.

  Create `plugins/mill/unit_tests/test-setup-short-name.py` (plain-script style, fixtures in `_test_helpers.safe_temp_dir()`). Cases:
  - Copy of `plugins/mill/templates/mill-config.yaml` with `short_name: ""`: after `set_repo_short_name(path, "MH")` the file differs from the original only on the `short_name:` line, that line keeps its trailing comment, and `yaml.safe_load` gives `repo.short_name == "MH"`; the function returned `True`.
  - A second call with `"MH"` returns `False` and leaves bytes and mtime unchanged.
  - An existing value `short_name: MH` replaced by `"LYX"`.
  - A file with no `repo:` block gains `repo:` / `  short_name: AB` as its first two lines; the rest is byte-identical.
  - A `repo:` block without `short_name:` gains the key under it.
  - A CRLF file keeps CRLF line endings on inserted lines.
  - `value` of `"A"`, `"ABCDE"`, `"A:B"` and `"a-b"` each raise `ValueError` and leave the file untouched.
- **Commit:** `feat(setup): add line-level set_repo_short_name helper`

## Batch Tests

`verify:` runs `test-vscode-tasks.py` (card 1), `test-vscode-keybindings.py` (confirms the untouched `TASK_SPECS`-driven keybindings stay at six), and the two new test files from cards 2 and 3.
Existing `test-paths.py` and `test-setup-hub-links.py` are not re-run here: card 2 only appends a new function and an `__all__` entry, and card 3 only adds new names, so neither changes behaviour those suites cover; batch 3's full-suite run covers them.
