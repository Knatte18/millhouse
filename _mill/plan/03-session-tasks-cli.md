# Batch: session-tasks-cli

```yaml
task: "Auto-name task sessions <slug>:<phase>"
batch: "session-tasks-cli"
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-session-tasks.py test-shortcut-wrapper.py test-skill-writer.py
depends-on: [1]
```

## Batch Scope

Delivers the `millpy-session-tasks.py` CLI that re-renders the current worktree's `.vscode/tasks.json` from the current merged config, its unit test, and its registration as a shortcut-wrapped user-callable script with a matching skill and index entry.
One batch because the registration in `_shortcuts.SHORTCUT_SCRIPTS` fans out into the skill-writer test, the wrapper tests and the skill index, all of which only make sense once the script exists.
Batch-local decision: the hub-versus-task decision is made solely by whether `_marker.slug_from_branch` raises `MarkerError`; every other failure exits 1 and writes nothing.

## Cards

### Card 7: Add millpy-session-tasks CLI

- **Context:**
  - `plugins/mill/scripts/millpy-color.py`
  - `plugins/mill/scripts/_vscode_tasks.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-session-tasks.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `plugins/mill/scripts/millpy-session-tasks.py` in `millpy-color.py`'s style (module docstring with usage and exit codes, `main(argv: list[str] | None = None) -> int`, `if __name__ == "__main__": sys.exit(main())`).
  It takes no arguments beyond `-h`.
  Flow inside `main`: bind `git_root = resolve_git_root()`, `hub = resolve_hub_path()`, `wiki_path = resolve_wiki_path(git_root)`, `cfg = _load_config(hub_root=hub, worktree_root=git_root)`; `target = hub / ".vscode" / "tasks.json"`; if `target.parent` does not exist, print a one-line ASCII message to stderr and return 1 without writing.
  Name selection: `name = _marker.slug_from_branch(git_root, wiki_path, cfg)`; on `_marker.MarkerError` treat the worktree as the hub and use `resolve_short_name(cfg, git_root.name)`.
  Then call `_vscode_tasks.write_tasks(target, name, (cfg.get("spawn") or {}).get("sessions"))` and print `tasks: <status> <target>`.
  Any other failure (any `Exception`, including a wiki-startup error that `_marker.slug_from_branch` deliberately propagates unwrapped, plus `SystemExit` from config/path resolution) is caught, reported as one ASCII line on stderr prefixed `[mill-session-tasks]`, and returns 1 with nothing written.
  Exit codes: 0 success (including `unchanged`), 1 any error.
  Import the helpers with the same module-level import style `millpy-color.py` uses so tests can patch them.
- **Commit:** `feat(session-tasks): add millpy-session-tasks to re-render tasks.json from config`

### Card 8: Unit tests for millpy-session-tasks

- **Context:**
  - `plugins/mill/scripts/millpy-session-tasks.py`
  - `plugins/mill/scripts/_vscode_tasks.py`
  - `plugins/mill/unit_tests/test-millpy-color.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-millpy-session-tasks.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-millpy-session-tasks.py`, loading the hyphenated script through `importlib.util.spec_from_file_location` and patching its module-level path/config/marker functions exactly as `test-millpy-color.py` does; fixtures live in tempdirs, no real git, wiki or VS Code.
  Cover: a task worktree (patched `slug_from_branch` returns a slug) renders `<slug>:start` names into `<hub>/.vscode/tasks.json`; a hub worktree (`slug_from_branch` raises `MarkerError`) renders names using the short name from `resolve_short_name`; after changing `spawn.sessions` in the patched config, re-running updates model and effort in the existing file; an unchanged config leaves the file byte-identical (mtime preserved) and prints `unchanged`; a missing `.vscode/` directory returns 1, writes nothing and prints one ASCII line to stderr; a non-`MarkerError` failure from `slug_from_branch` (a `SystemExit`, and a plain `RuntimeError` standing in for a wiki startup error) returns 1 and writes nothing; a `ValueError` from an invalid configured model value returns 1 and leaves any existing file untouched.
- **Commit:** `test(session-tasks): cover hub/task naming, re-render and error paths`

### Card 9: Register millpy-session-tasks as a wrapped script with a skill

- **Context:**
  - `plugins/mill/skills/mill-color/SKILL.md`
  - `plugins/mill/scripts/millpy-session-tasks.py`
  - `plugins/mill/unit_tests/test-shortcut-wrapper.py`
- **Edits:**
  - `plugins/mill/scripts/_shortcuts.py`
  - `plugins/mill/unit_tests/test-skill-writer.py`
  - `SKILLS.md`
- **Creates:**
  - `plugins/mill/skills/mill-session-tasks/SKILL.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/scripts/_shortcuts.py`, append `"millpy-session-tasks"` to the end of `SHORTCUT_SCRIPTS` (after `"millpy-wikipush"`).
  In `plugins/mill/unit_tests/test-skill-writer.py`, update the `iter_target_scripts` test: add `"millpy-session-tasks"` to `expected_stems`, change the expected count from 10 to 11 (the failure message, the PASS text and the comments that mention 10 and 11 total), so the test again matches `SHORTCUT_SCRIPTS` minus the skip-listed `mill-add`.
  `test-shortcut-wrapper.py` derives every expected count from `len(SHORTCUT_SCRIPTS)`, so it needs no edit; it stays in this batch's `verify:` to prove that.
  Create `plugins/mill/skills/mill-session-tasks/SKILL.md` in `mill-color`'s exact shape: frontmatter `name: mill-session-tasks` and `description: re-render this worktree's .vscode/tasks.json (session launch tasks) from the current mill config.`; body explaining that it rewrites `.vscode/tasks.json` with the model/effort from `spawn.sessions` in `mill-config.yaml` / `.millhouse/config.local.yaml`, that it must be re-run after changing those values because model and effort are baked into the file, a `## Run it` fenced bash block using `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-session-tasks.py"`, and the exit codes (0 success, 1 error).
  In `SKILLS.md`, insert one table row for `mill-session-tasks` in alphabetical position (between the `mill-self-report` and `mill-setup` rows), in the same format as its neighbours and with a description identical to the SKILL.md frontmatter.
- **Commit:** `feat(session-tasks): register millpy-session-tasks wrapper, skill and index entry`

## Batch Tests

`verify:` runs `test-millpy-session-tasks.py` (new), `test-skill-writer.py` (updated count and stems) and `test-shortcut-wrapper.py` (unchanged, proves the wrapper count is derived from `SHORTCUT_SCRIPTS`).
All use tempdir fixtures and patched path/config functions.
