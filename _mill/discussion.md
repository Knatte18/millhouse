# Discussion: Prefix session names with repo short name; add mh:orch session

```yaml
task: Prefix session names with repo short name; add mh:orch session
slug: session-name-short-prefix
status: discussing
parent: main
```

## Problem

Claude Code session names are machine-global: `ListAgents` lists sessions from every repo on the machine (a `lyx:orch` session showed up next to the millhouse ones), and `SendMessage` addresses sessions by name.
A task worktree's `.vscode/tasks.json` names its sessions `<slug>:<phase>` with no repo part, so two repos with the same slug collide.
The hub's tasks already use `<short_name>:<phase>` (e.g. `MH:start`), so the two naming styles are also inconsistent.

The orchestrator session in the hub has no named launch task.
The derived short-name fallback (`repo_name[:2].upper()`) can also be wrong (`lyx` -> `LY`), and the short name is about to become part of every session address.

## Scope

**In:**

- Worktree session names become `<short_name>:<slug>:<phase>`, e.g. `mh:remove-batch-review:plan`.
- Hub session names stay `<short_name>:<phase>`, e.g. `mh:start`.
- Every session name is lower-cased at the one place its prefix is assembled (a new `_vscode_tasks.session_prefix` helper, see Decisions).
  `repo.short_name` in config is unchanged (stays `MH`, still used verbatim in the VS Code window title).
- `millpy-terminal.py`'s session (today `claude --name <slug>`) becomes `<short_name>:<slug>`, lower-cased, via the same helper.
- The derived short-name fallback uses the main worktree's directory name, not the current worktree's, wherever this task resolves a short name for a session name.
- A new hub-only `orch` session task, `mill: orch`, launching a session named `<short_name>:orch` (e.g. `mh:orch`).
- `spawn.sessions.orch` model/effort config key with a built-in default.
- `mill-setup` prompts for `repo.short_name` when the hub `mill-config.yaml` has none, and writes it.
- A one-line stderr warning from `millpy-spawn`, `millpy-session-tasks` and `millpy-terminal` when the short name comes from the derived fallback.
- Docstrings, SKILL.md prose, config-template comments and unit tests that mention the old `<slug>:<phase>` form or the task list.

**Out:**

- Migrating existing worktrees' `.vscode/tasks.json`.
  They keep the old names until `/mill-session-tasks` is re-run there.
- A keybinding for the `orch` task (see Decisions).
- The `parent-thread` field in `status.md` and the ask-your-parent escalation, tracked separately.
- The VS Code window title format (`<short_name>: <slug>`), `_vscode.py`, `millpy-color.py`, `millpy-claim.py`.
  Their own `resolve_short_name(cfg, git_root.name)` calls keep their current repo-name argument.
- `millpy-vscode.py`: it does not launch `claude`, so it names no session.
- Changing the set of tasks the hub already gets (start, start-auto, start-orch, plan, go, quick stay on the hub too).
- Changing `resolve_short_name`'s fallback rule or its return casing.

## Decisions

### Name composition and lower-casing

- Decision: add `session_prefix(short_name: str, slug: str | None = None) -> str` to `_vscode_tasks.py`.
  It returns `short_name.lower()` for the hub, or `f"{short_name}:{slug}".lower()` for a worktree.
  It is the only place a session name is lower-cased.
  It raises `ValueError` when `short_name` is empty, contains `:`, or contains a character `_validate_name` forbids.
  `render_tasks`/`write_tasks`/`build_command` keep taking the already-built prefix as `name` and append `:<phase>` without changing case.
  `_validate_name` still runs on the full prefix in `render_tasks`; the colon between short name and slug is allowed there.
- Rationale: one assembly site, as the task body asks, shared by the tasks.json writers and `millpy-terminal.py` (whose session has no phase, so the lower-casing cannot live in `build_command`).
  Slugs and phases are already lower-case, so lower-casing only affects the short name.
  It also avoids depending on whether `SendMessage`/`ListAgents` name lookup is case-sensitive, which is unverified.
  Rejecting `:` in the short name covers hand-edited `repo.short_name` values too, not only the mill-setup prompt, so `<short>:<slug>:<phase>` stays unambiguous.
- Rejected: lower-casing inside `resolve_short_name` (it also feeds the window title, which must stay `MH`); lower-casing in `build_command` (misses the terminal session); leaving hand-edited values unvalidated.

### Where the prefix is built

- Decision: every caller builds the prefix with `session_prefix`.
  `millpy-spawn.py` passes `session_prefix(short, slug)`.
  `millpy-session-tasks.py` passes `session_prefix(short, slug)` on a task worktree and `session_prefix(short)` on the hub (the `MarkerError` branch).
  mill-setup Phase 7b passes `session_prefix(resolve_short_name(cfg, '<repo-name>'))` plus the new `hub=True` argument.
  `millpy-terminal.py` passes `session_prefix(short, selected_slug)` to `claude --name` (both the `nt` and POSIX branches) and prints that name in its "Session name:" line.
- Decision: the repo-name argument to `resolve_short_name` is `resolve_main_worktree_root(git_root).name` in `millpy-spawn.py`, `millpy-session-tasks.py` and `millpy-terminal.py`, not `git_root.name`.
  On a task worktree `git_root` is `wts/<slug>`, so `git_root.name` is the slug and the fallback would derive e.g. `SE` from `session-name-short-prefix`.
  `resolve_main_worktree_root` (`_paths.py`, pygit2 common-dir based) returns the main worktree from any worktree; `millpy-spawn.py` already uses it for its `REPO` token.
  `millpy-spawn.py` normally runs from the hub, where both are equal, but it switches for correctness when run from a worktree.
  mill-setup keeps `'<repo-name>'`, which is already the repo name.
- Rationale: these are the only callers that put a short name into a session name, and each already knows whether it is hub or worktree.

### Hub-only orch task

- Decision: add a hub-only task spec list, e.g. `HUB_TASK_SPECS = TASK_SPECS + (("orch", "orch", None),)`, and a keyword-only `hub: bool = False` parameter on `render_tasks` and `write_tasks`.
  `hub=True` renders the orch task after `quick`.
  `TASK_SPECS` (worktree set) is unchanged.
- Rationale: the orchestrator runs only in the hub; an `orch` task in a task worktree is meaningless.
  Leaving `TASK_SPECS` alone keeps `_vscode_keybindings.desired_bindings()` (which enumerates `TASK_SPECS`) at six bindings, unchanged.
- Rejected: adding `orch` to `TASK_SPECS` for everyone, which would put it in every worktree and also add a seventh keybinding.

### Orch task rendering through the template

- Decision: the tasks template `plugins/mill/templates/vscode-tasks.json` gets one extra token, `<HUB_TASKS>`, placed right after the `quick` task object.
  For worktrees it renders as the empty string.
  For the hub it renders as the rendered text of a new template fragment `plugins/mill/templates/vscode-tasks-orch.json` (rendered with `_render.render`, token `<CMD_ORCH>`).
  The fragment itself starts with the separating `,` before the orch task object, so Python adds no JSON syntax of its own.
  The rendered output must stay valid JSON after the `MANAGED_MARKER` line in both modes.
- Rationale: `_render.py`'s docstring forbids format-specific rendering code outside templates, so the orch task's JSON shape belongs in a template, not in a Python string.
- Rejected: a second full hub template (duplicates all six task blocks, which can drift); building the orch task dict in Python and `json.dumps`-ing it (format-specific rendering in code).

### Orch session command

- Decision: the orch session starts with no initial prompt: `claude -n "<short>:orch" --model <m> --effort <e>`.
  `build_command` omits the trailing quoted prompt for phases that have no slash command.
  How to mark that (a set such as `_NO_PROMPT_PHASES = {"orch"}` consulted by `_prompt`/`build_command`, or a `None` prompt) is left to the plan.
- Rationale: there is no `/mill-orch` skill.
  The orchestrator is a human-driven hub session that runs `mill-spawn`, `orch-review`, `mill-status` etc. on demand.
- Rejected: an initial `/mill-status` prompt (arbitrary, and costs a turn on every launch).

### Orch model/effort default

- Decision: add `"orch": {"model": "opus", "effort": "high"}` to `DEFAULT_SESSIONS`, and `orch: { model: opus, effort: high }` under `spawn.sessions` in both `plugins/mill/templates/mill-config.yaml` and the hub `mill-config.yaml` (CLAUDE.md: hub file and template must stay in sync).
  Update the template's `sessions` comment to say `orch` applies to the hub only.
- Decision: `resolve_sessions` gains an optional `phases` argument (an iterable of phase names; default: every key of `DEFAULT_SESSIONS`, so `resolve_sessions(None) == DEFAULT_SESSIONS` still holds).
  It resolves and validates only those phases.
  `render_tasks` passes the distinct phases of the spec list it renders: `TASK_SPECS` for a worktree (no `orch`), `HUB_TASK_SPECS` for the hub.
  An invalid `spawn.sessions.orch` value therefore fails only hub renders, never a worktree spawn or a worktree `millpy-session-tasks` run.
- Rationale: the orchestrator does judgment-heavy work (hand-written `orch-review`s, triage), so it gets the strongest default.
  Today `resolve_sessions` validates every `DEFAULT_SESSIONS` key before `TASK_SPECS` is read, so without the `phases` scoping a bad hub-only `orch` value in the shared `mill-config.yaml` would break every worktree render for a task it has nothing to do with.
- Rejected: accepting that a bad `orch` value breaks worktree spawns (collateral failure from config the worktree never uses).

### No keybinding for orch

- Decision: `_vscode_keybindings` stays at six bindings, derived from `TASK_SPECS` only.
- Rationale: keybindings are user-level and apply in every VS Code window.
  An `alt+shift+7` -> `mill: orch` binding would fail with "task not found" in every task-worktree window.
  The orch session is launched about once per hub session, so Run Task is enough.
- Rejected: a seventh binding (dead key in worktree windows).

### Explicit short_name in mill-setup

- Decision: add a mill-setup step right after Phase 3.1 (mill-config.yaml seed/upsert): if the hub `mill-config.yaml` has no non-empty `repo.short_name`, prompt the operator as a numbered list per `mill:conversation`.
  Option 1 is the derived value from `resolve_short_name` (marked Recommended), option 2 lets the operator type a different value as free text.
  Validate against `^[A-Za-z0-9]{2,4}$` (the template comment already documents 2-4 characters); re-prompt on failure.
  The derived value is offered as option 1 only when it passes that regex itself.
  It can fail for a 1-character repo name (`resolve_short_name` then returns 1 character) or a repo name whose first two characters are not alphanumeric (e.g. `a-b` -> `A-`).
  In that case the prompt has no recommended option and asks only for a typed value.
  Write the value into `mill-config.yaml` and stage/commit it the same way Phase 3.1 commits its upsert.
  When `repo.short_name` is already set, the step is a silent no-op (idempotent).
- Decision: the write goes through a new helper in `_setup.py` (e.g. `set_repo_short_name(config_path, value)`) that edits the file at line level: replace the value on the `short_name:` line inside the `repo:` block, or insert a `repo:` block with `short_name:` at the top of the file when absent.
  It must preserve every other line and comment byte-for-byte, so it must not round-trip through `yaml.safe_load`/`yaml.dump`.
- Rationale: mill-setup is the one per-repo setup entry point, and it is idempotent, so re-running it in an existing repo fills the gap.
  Alphanumeric-only keeps the short name from introducing a `:` (which would break `<short>:<slug>:<phase>` parsing) or a character `_validate_name` rejects.
- Rejected: failing hard when unset (breaks existing repos for a cosmetic issue); validating inside `resolve_short_name` (it has many callers, and the fallback must keep working).

### Fallback warning

- Decision: add a small predicate in `_paths.py` next to `resolve_short_name`, e.g. `short_name_is_derived(cfg) -> bool` (true when `repo.short_name` is absent or empty).
  `millpy-spawn.py`, `millpy-session-tasks.py` and `millpy-terminal.py` each print one ASCII-only line to stderr when it is true, naming the derived value and pointing at `repo.short_name` in `mill-config.yaml` / `/mill-setup`.
  The derived value in the warning is the one computed from the main worktree's name (see "Where the prefix is built"), so it matches the name that was baked in.
  mill-setup's new step covers its own case by prompting, so it does not warn separately.
- Rationale: these three scripts are every place outside mill-setup where a short name becomes part of a session name (tasks.json for spawn and session-tasks, the live `claude --name` for terminal), so they cover repos that never re-run mill-setup.
  A warning, not an error: the fallback still produces a working name.
- Rejected: warning inside `resolve_short_name` (it is also called by `millpy-color`, `millpy-claim` and `_vscode` paths, which would get noisy, and a path resolver should not print).

## Technical context

- `plugins/mill/scripts/_vscode_tasks.py` — `TASK_SPECS`, `DEFAULT_SESSIONS`, `_prompt`, `build_command(name, phase, model, effort, flag)` (currently `f'claude -n "{name}:{phase}" ...'`), `_validate_name`, `render_tasks(name, sessions_cfg)`, `write_tasks(target, name, sessions_cfg)`.
  `render_tasks` fills `CMD_<TASK_KEY>` tokens with `json.dumps(command)[1:-1]`; the orch fragment's `<CMD_ORCH>` token uses the same escaping.
  The module docstring's `<slug>:<phase>` wording and the Public API block need updating for the new signature.
- `plugins/mill/templates/vscode-tasks.json` — static six-task template with `<CMD_*>` tokens.
  `_render.render` raises `KeyError` on any unresolved token, so `<HUB_TASKS>` must always be supplied (empty string for worktrees).
  A token whose value is the empty string must not leave a trailing comma or break JSON.
- `plugins/mill/scripts/_render.py` — the single substitution helper; token grammar `<[A-Z][A-Z0-9_]*>`; strips a leading `<!-- -->` comment.
- `plugins/mill/scripts/millpy-spawn.py` — around the `_vscode_tasks.write_tasks(tasks_path, slug, ...)` call; `short` is already computed a few lines earlier for `_vscode.write_settings`, currently as `resolve_short_name(cfg, git_root.name)`.
  Switching that one computation to the main worktree's name also changes the short name passed to `_vscode.write_settings`, which is intended: the window title then shows the same short name.
  Module docstring mentions `<slug>:<phase>`.
- `plugins/mill/scripts/millpy-session-tasks.py` — `slug_from_branch` success = worktree, `MarkerError` = hub.
  Docstring says "The session name is the task slug on a task worktree and the repo short name on the hub."
- `plugins/mill/scripts/_paths.py` — `resolve_short_name(cfg, repo_name)` at the end of the resolve helpers; exported via the module's `__all__`-style list near the top (add the new predicate there).
- `plugins/mill/scripts/_setup.py` — mill-setup helpers module; the new `set_repo_short_name` helper goes here.
- `plugins/mill/scripts/millpy-terminal.py` — picks an active worktree (`selected_path`, `selected_slug`), loads `cfg` from the hub (falling back to `{}` on error, which `resolve_short_name` tolerates), and launches `claude --name <selected_slug>` in two branches (`os.name == "nt"` via `cmd /c`, else direct).
  It needs imports of `resolve_short_name`, `resolve_main_worktree_root` and `_vscode_tasks.session_prefix`.
  Its unit test is `plugins/mill/unit_tests/test-millpy-terminal.py`.
- `plugins/mill/scripts/_vscode_keybindings.py` — no code change; its docstring says "six session tasks", which stays true because the hub-only orch task is not bound.
- `plugins/mill/skills/mill-setup/SKILL.md` — Phase 3.1 (seed/upsert mill-config.yaml, with a commit), Phase 7 (window title via `resolve_short_name`), Phase 7b (tasks.json: add `hub=True`; update the "six session launch tasks" wording since the hub now gets seven).
  Also the "Helpers used by this skill" line if the new `_setup` helper is referenced.
- `plugins/mill/skills/mill-spawn/SKILL.md` — the description paragraph says session names are `<slug>:<phase>`.
- `plugins/mill/skills/mill-session-tasks/SKILL.md` — mention that the hub also gets the `orch` task.
- `plugins/mill/templates/mill-config.yaml` — `repo.short_name` comment says it is used in window titles; extend it to session names.
  The `sessions` comment block and the `spawn.sessions` mapping get `orch`.
- Hub `mill-config.yaml` — `spawn.sessions` gets `orch`.
- `SKILLS.md` is generated from SKILL.md frontmatter; no descriptions change, so no regeneration is needed unless a frontmatter `description:` is edited.

## Constraints

- `_validate_name` forbids `"`, backslash, `$`, backtick and control characters; the composite prefix `<short>:<slug>` must still pass it.
- `print()`/`_log()` output is ASCII only (Windows cp1252), including the new warnings.
- The hub `mill-config.yaml` and `plugins/mill/templates/mill-config.yaml` must stay in sync.
- No `sed` in any script, SKILL.md command, or implementer instruction.
- Plan `verify:` commands start with `PYTHONPATH=` (empty) per CLAUDE.md.
- Unit tests use in-memory/tempfile fixtures, no real git or LLM.

## Testing

- `plugins/mill/unit_tests/test-vscode-tasks.py` (TDD candidate): worktree render with prefix `session_prefix("MH", "my-task")` produces `claude -n "mh:my-task:<phase>"` for every `TASK_SPECS` entry and no orch task; hub render (`hub=True`) with prefix `session_prefix("MH")` produces the six tasks named `mh:<phase>` plus `mill: orch` with `claude -n "mh:orch" --model opus --effort high` and no prompt argument; both outputs parse as JSON after the marker line; `spawn.sessions.orch` overrides apply; an invalid `spawn.sessions.orch.model` raises `ValueError` for a hub render but not for a worktree render; `resolve_sessions(cfg, phases=...)` resolves only the listed phases, and `resolve_sessions(None)` still equals `DEFAULT_SESSIONS` (the existing test that compares the template's `spawn.sessions` to `DEFAULT_SESSIONS` then also requires `orch` in the template); a forbidden character in the prefix still raises `ValueError`.
- `plugins/mill/unit_tests/test-millpy-session-tasks.py`: worktree case expects `<short>:<slug>:start` lower-cased; hub case expects `hubshort:start` and `hubshort:orch` (the fixture's `HUBSHORT` lower-cased); the derived-fallback warning appears on stderr when `repo.short_name` is unset and not when it is set.
- `plugins/mill/unit_tests/test-millpy-spawn.py`: the expected commands (currently `test-task:start` etc.) become `<short>:test-task:<phase>` lower-cased; the worktree tasks.json contains no orch task; the fallback warning behaves as above.
- `plugins/mill/unit_tests/test-vscode-keybindings.py`: no expectation changes; still six bindings.
  Existing tests must still pass.
- New tests for `_setup.set_repo_short_name` (TDD candidate): replaces an empty `short_name: ""` in the template form, keeping the trailing comment and every other line byte-identical; replaces an existing value; inserts a `repo:` block when absent; idempotent on a second call.
- New tests for the `_paths` derived-short-name predicate: absent `repo` block, empty string, and set value.
- `session_prefix` tests in `test-vscode-tasks.py` (TDD candidate): hub form lower-cases `MH` to `mh`; worktree form gives `mh:my-task`; a short name containing `:`, an empty short name, or one with a forbidden character raises `ValueError`.
- Worktree fallback test (in `test-millpy-session-tasks.py`, and the same shape in `test-millpy-spawn.py`): the current worktree directory is slug-named (e.g. `session-name-short-prefix`), the main worktree is `millhouse`, `repo.short_name` is unset; the rendered names use `mi:` (derived from `millhouse`), not `se:`, and the warning names `MI`.
- `plugins/mill/unit_tests/test-millpy-terminal.py`: the launched argv carries `--name <short>:<slug>` lower-cased, on both the `nt` and POSIX branches; the fallback warning appears on stderr only when `repo.short_name` is unset.
- Run the full suite via `run-all.py`.

## Q&A log

- **Q:** Where does lower-casing happen? **A:** [auto-pick] In a new `_vscode_tasks.session_prefix` helper that every session-naming caller uses (revised after review round 1, from `build_command`, so the phase-less terminal session is covered too). **Why:** one assembly point, and config/window title stay `MH`.
- **Q:** What happens to `millpy-terminal.py`'s bare-slug session name? **A:** [auto-pick] It becomes `<short>:<slug>` via `session_prefix`. **Why:** it collides across repos the same way (added after review round 1).
- **Q:** Should the `orch` task go into every worktree or only the hub? **A:** [auto-pick] Hub only, via `hub=True` and a separate hub spec list. **Why:** the orchestrator runs only in the hub, and `TASK_SPECS`/keybindings stay untouched.
- **Q:** How is the hub-only task rendered? **A:** [auto-pick] A `<HUB_TASKS>` token in the existing template filled from a new orch-task fragment template. **Why:** keeps JSON shape in templates per `_render.py`'s rule without duplicating the six task blocks.
- **Q:** What does the orch session run on launch? **A:** [auto-pick] Nothing: a named session with model/effort only. **Why:** no `/mill-orch` skill exists, and the orchestrator is human-driven.
- **Q:** Orch default model/effort? **A:** [auto-pick] `opus` / `high`. **Why:** judgment-heavy orchestration and hand-written reviews.
- **Q:** Add a keybinding for orch? **A:** [auto-pick] No. **Why:** user-level bindings would be a dead key in every worktree window.
- **Q:** How does mill-setup make `repo.short_name` explicit? **A:** [auto-pick] Prompt (numbered list, derived value as option 1) only when unset, validate `^[A-Za-z0-9]{2,4}$`, write via a line-level `_setup` helper, commit like Phase 3.1. **Why:** idempotent, preserves config comments, and keeps `:` out of the short name.
- **Q:** Where is the fallback warning emitted? **A:** [auto-pick] stderr in `millpy-spawn` and `millpy-session-tasks`, via a `_paths` predicate. **Why:** that is where names get baked in; `resolve_short_name` has other callers and should stay silent.
- **Q:** Migrate existing worktrees' tasks.json? **A:** [auto-pick] No; they are refreshed by re-running `/mill-session-tasks`. **Why:** matches the task body's care point.
