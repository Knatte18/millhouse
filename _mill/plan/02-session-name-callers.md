# Batch: session-name-callers

```yaml
task: Prefix session names with repo short name; add MH:orch session
batch: session-name-callers
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-spawn.py test-millpy-session-tasks.py test-millpy-terminal.py
depends-on: [1]
```

## Batch Scope

Switches the three scripts that put a short name into a session name onto the batch 1 helpers.
Each derives the fallback short name from the main worktree's directory name (`resolve_main_worktree_root(git_root).name`), builds the prefix with `_vscode_tasks.session_prefix`, and prints one ASCII stderr warning when `_paths.short_name_is_derived(cfg)` is true.
Warning text shape, shared by all three (only the `[<tool>]` tag differs): `[<tool>] WARNING: repo.short_name is not set; using derived short name '<SHORT>'. Set repo.short_name in mill-config.yaml or run /mill-setup.` where `<SHORT>` is the `resolve_short_name` result before lower-casing.

## Cards

### Card 4: millpy-spawn names worktree sessions <short>:<slug>:<phase>

- **Context:**
  - `plugins/mill/scripts/_vscode_tasks.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/millpy-spawn.py`:
  - Add `short_name_is_derived` to the existing `from _paths import ...` line.
  - Change `short = resolve_short_name(cfg, git_root.name)` to `short = resolve_short_name(cfg, resolve_main_worktree_root(git_root).name)`; the same `short` keeps feeding `_vscode.write_settings`.
  - Right after computing `short`, when `short_name_is_derived(cfg)` is true, print the batch's warning line with tag `[spawn]` to `sys.stderr` (the tag the script already uses for its other stderr lines).
  - Change the `_vscode_tasks.write_tasks(tasks_path, slug, ...)` call to pass `_vscode_tasks.session_prefix(short, slug)` as the name; the rollback line after it is unchanged. No `hub=` argument (worktree render).
  - Update the module docstring's step 8 wording from `<slug>:<phase>` to `<short_name>:<slug>:<phase>` (lower-cased).

  In `plugins/mill/unit_tests/test-millpy-spawn.py`:
  - `_run_spawn_real_fs` gains keyword parameters `main_root: Path | None = None` (return value of the patched `resolve_main_worktree_root`; default keeps today's `hub`), `short_name_side_effect=None` (when given, `resolve_short_name` is patched with `side_effect=` instead of `return_value="MI"`), and `derived: bool = False` (patches `short_name_is_derived` with `return_value=derived`, needed because the module's `_paths` import is a `MagicMock` stub in this helper). It also captures stderr with `contextlib.redirect_stderr` and returns it as a fifth tuple element; update every caller's tuple unpacking.
  - `test_spawn_standard_layout_regression`: expected commands become `mi:test-task:start`, `mi:test-task:plan`, `mi:test-task:go`, `mi:test-task:quick`; also assert `"mill: orch"` does not appear in tasks.json.
  - `test_spawn_propagates_session_config_to_tasks_json`: fix the f-string in its failure message so it indexes `by_label["mill: go"]` rather than the nonexistent `"test-task:go"` key.
  - New `test_spawn_session_names_use_main_worktree_fallback`: `main_root = tmpdir / "millhouse"` (created), `short_name_side_effect=lambda cfg, name: name[:2].upper()`, `derived=True`; assert tasks.json contains `mi:test-task:start`, the side effect received `"millhouse"` (not `test-task`), and captured stderr has exactly one `WARNING: repo.short_name is not set` line naming `'MI'` that is ASCII.
  - New `test_spawn_no_warning_when_short_name_set`: default helper arguments (`derived=False`); captured stderr contains no `repo.short_name is not set`.
  - Register both new tests in `main()`'s test list.
  - Any other test that stubs `_paths` via `paths_mock` or patches `resolve_short_name` must keep passing; add `short_name_is_derived` patches only where a test needs a deterministic warning outcome.
- **Commit:** `feat(spawn): prefix worktree session names with repo short name`

### Card 5: millpy-session-tasks prefixes names and renders the hub orch task

- **Context:**
  - `plugins/mill/scripts/_vscode_tasks.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_marker.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-session-tasks.py`
  - `plugins/mill/unit_tests/test-millpy-session-tasks.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/millpy-session-tasks.py`, inside the existing `try:` in `main`, after the `.vscode` existence check:
  - `short = resolve_short_name(cfg, resolve_main_worktree_root(git_root).name)` (import `resolve_main_worktree_root` and `short_name_is_derived` on the existing `from _paths import ...` line).
  - On `_marker.slug_from_branch` success: `name = _vscode_tasks.session_prefix(short, slug)`, `hub = False`. On `_marker.MarkerError`: `name = _vscode_tasks.session_prefix(short)`, `hub = True`.
  - When `short_name_is_derived(cfg)` is true, print the batch's warning line with tag `[mill-session-tasks]` to stderr, before calling `write_tasks`.
  - Call `_vscode_tasks.write_tasks(target, name, sessions, hub=hub)`.
  - The missing-`.vscode` early return stays before all of this, so that path still prints exactly one stderr line.
  - Update the module docstring: session names are `<short_name>:<slug>:<phase>` on a task worktree and `<short_name>:<phase>` on the hub (lower-cased), the hub also gets the `mill: orch` task, and the fallback short name comes from the main worktree's directory name with a stderr warning.

  In `plugins/mill/unit_tests/test-millpy-session-tasks.py`:
  - `_run` gains keyword parameters `short: str | None = "HUBSHORT"` (when `None`, `resolve_short_name` is not patched and the real function runs) and `main_root: Path | None = None` (patched return of `mill_session_tasks.resolve_main_worktree_root`; default `repo`). Always patch `resolve_main_worktree_root`, since the tempdir is not a git repo.
  - Worktree case expects `hubshort:my-task:start` (not the old `my-task:start`) and no `mill: orch` label.
  - Hub case expects `hubshort:start` and a `mill: orch` task whose command contains `hubshort:orch`.
  - New worktree fallback case: tempdir named via a subdirectory `session-name-short-prefix`, `main_root` a sibling path ending in `millhouse`, `short=None`, cfg `{}`; the tasks.json uses `mi:session-name-short-prefix:start` (not `se:`), and stderr has one warning line naming `'MI'`.
  - New case: cfg `{"repo": {"short_name": "MH"}}` with `short=None` renders `mh:my-task:start` and stderr has no warning.
  - Existing cases (update/unchanged, missing `.vscode`, marker failures, invalid model) keep their assertions; they run with cfg `{}` so a warning line may now precede the failure line — the `err.startswith("[mill-session-tasks]")` assertions still hold because the warning carries the same tag.
- **Commit:** `feat(session-tasks): prefix session names and add hub orch task`

### Card 6: millpy-terminal names its session <short>:<slug>

- **Context:**
  - `plugins/mill/scripts/_vscode_tasks.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-terminal.py`
  - `plugins/mill/unit_tests/test-millpy-terminal.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/millpy-terminal.py`:
  - Add `import _vscode_tasks`, and add `resolve_main_worktree_root`, `resolve_short_name` and `short_name_is_derived` to the existing `from _paths import ...` line.
  - After the worktree is selected (after `selected_slug` is bound) compute `repo_name` as `resolve_main_worktree_root(git_root).name`, falling back to `git_root.name` on `(SystemExit, Exception)` to match this script's tolerant config loading; `short = resolve_short_name(cfg, repo_name)`.
  - `session_name = _vscode_tasks.session_prefix(short, selected_slug)`; on `ValueError` print `[mill-terminal] invalid session name: <ascii message>` to stderr and return 1.
  - When `short_name_is_derived(cfg)` is true, print the batch's warning line with tag `[mill-terminal]` to stderr.
  - The `Session name:` line prints `session_name`, and both launch branches (`os.name == "nt"` via `cmd /c`, and POSIX) pass `"--name", session_name` instead of `selected_slug`.
  - Update `main`'s docstring (`--name <short>:<slug>`, lower-cased).

  In `plugins/mill/unit_tests/test-millpy-terminal.py`, add tests (existing ones stay unchanged and must keep passing):
  - POSIX branch: patch `mill_terminal._load_config` to return `{"repo": {"short_name": "MH"}}` and `mill_terminal.wiki.list_tasks_brief` to return `[]`, a single active worktree `solo-task`; the captured argv is `["claude", "--name", "mh:solo-task"]` and captured stderr has no `repo.short_name is not set`.
  - `nt` branch: same setup plus `patch("mill_terminal.os", types.SimpleNamespace(name="nt"))` (the script reads only `os.name`); argv is `["cmd", "/c", "claude", "--name", "mh:solo-task"]`.
  - Fallback: `_load_config` returns `{}`, `mill_terminal.resolve_main_worktree_root` patched to return a path ending in `millhouse`; argv carries `--name mi:solo-task` and stderr has one warning line naming `'MI'`.
  - Invalid short name: `_load_config` returns `{"repo": {"short_name": "M:H"}}`; `main` returns 1, `subprocess.run` is never called, and stderr contains `[mill-terminal] invalid session name:`.
  Capture stderr with `contextlib.redirect_stderr`.
- **Commit:** `feat(terminal): prefix terminal session name with repo short name`

## Batch Tests

`verify:` runs the three test files edited in this batch (`test-millpy-spawn.py`, `test-millpy-session-tasks.py`, `test-millpy-terminal.py`), which cover every script this batch changes.
