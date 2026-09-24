# Batch: spawn-wiring

```yaml
task: "Auto-name task sessions <slug>:<phase>"
batch: "spawn-wiring"
number: 4
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-spawn.py
depends-on: [1]
```

## Batch Scope

Makes `millpy-spawn.py` seed a slug-baked `.vscode/tasks.json` into every new worktree, with rollback, and extends the existing spawn tests accordingly.
One batch because the production edit and the stub-map changes it forces in the spawn test file must land together to keep that test file green.
Batch-local decision: spawn always writes (fresh worktree) through `_vscode_tasks.write_tasks`, using `dest_hub`, not `worktree_path`, as the `.vscode/` parent so the `hub_relative_path != "."` layout is correct.

## Cards

### Card 10: Write tasks.json during spawn

- **Context:**
  - `plugins/mill/scripts/_vscode_tasks.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/scripts/millpy-spawn.py`, add `import _vscode_tasks` alongside the existing `import _vscode` line.
  In `main`, immediately after the block that writes `.vscode/settings.json` and pushes its rollback lambda onto `_cleanup_stack`, add: `tasks_path = dest_hub / ".vscode" / "tasks.json"`; a call `_vscode_tasks.write_tasks(tasks_path, slug, (cfg.get("spawn") or {}).get("sessions"))`; and `_cleanup_stack.append(lambda: tasks_path.unlink(missing_ok=True))` with a one-line `# Rollback:` comment matching the neighbouring rollback comments.
  `cfg` is the already-loaded merged config and `slug` the claimed task slug, both in scope at that point.
  Update the module docstring's step 8 so it says the step also writes `.vscode/tasks.json` (session launch tasks named `<slug>:<phase>`).
- **Commit:** `feat(spawn): seed .vscode/tasks.json with slug-named session tasks`

### Card 11: Extend spawn tests for tasks.json

- **Context:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/_vscode_tasks.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/unit_tests/test-millpy-spawn.py`, every place that installs a `"_vscode"` stub for `millpy-spawn.py` (the `test_smoke_import` stub-name list and every `stub_map` / stubs dict that contains `"_vscode"`) must also install `"_vscode_tasks"` as a `MagicMock` (a bare `types.ModuleType` in the smoke-import list), so those tests never write to fake paths.
  Exception: `_run_spawn_real_fs` must not stub `_vscode_tasks`; it lets the real module run against the tempdir so the file can be asserted.
  Add an optional parameter to `_run_spawn_real_fs` (for example `fail_status_write: bool = False`) that makes `spawn_core_mock.write_initial_status` raise, so rollback can be exercised against the real filesystem; keep the existing return tuple and all existing callers unchanged.
  Extend `test_spawn_standard_layout_regression`: after the run, `wt / ".vscode" / "tasks.json"` exists, starts with `// managed by mill`, and contains the literal slug in each of the six commands (`test-task:start`, `test-task:plan`, `test-task:go`, `test-task:quick`; `start-auto` and `start-orch` also `test-task:start`).
  Extend `test_spawn_subfolder_install_destination_layout` so the file exists at `dest_hub / ".vscode" / "tasks.json"` and does not exist at the worktree root's `.vscode/`.
  Add a rollback test using the new parameter: when the initial status write fails, the run exits non-zero and `tasks.json` no longer exists in `.vscode/`.
  Add a config-propagation test: when the patched `_load_config` return value carries `spawn: {sessions: {go: {model: haiku, effort: low}}}`, the rendered `go` command contains `--model haiku --effort low` while `plan` keeps its defaults.
- **Commit:** `test(spawn): assert tasks.json seeding, layout and rollback`

## Batch Tests

`verify:` runs the single `test-millpy-spawn.py` file, which covers both the stubbed and the real-filesystem spawn paths (stubs are updated in card 11).
It does not run the full suite because no shared helper outside `_vscode_tasks` and `millpy-spawn.py` changes in this batch.
