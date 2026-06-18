# Batch: vscode-watcher-exclude

```yaml
task: "Fix agent error recovery, implementer/review false-success contracts, VS Code watcher, and plan-validator Deletes"
batch: "vscode-watcher-exclude"
number: 2
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-vscode.py
depends-on: []
```

## Batch Scope

Fixes issue #498: VS Code's recursive file-watcher follows the `.portals` / `.wiki` / `.active` junctions into every other worktree's `_mill/` and holds directory handles that block `git worktree remove` after a task finishes. The fix seeds `files.watcherExclude` into the worktree settings template so the watcher never follows those junctions. Because `_vscode.render_settings` does pure token substitution and every writer (mill-spawn, mill-color, mill-claim, mill-setup) re-renders the whole template, a static template key is seeded on every future write — no `_vscode.py` logic change needed. Scope decision (per discussion Q2): template-only; no in-place migration of existing worktrees.

## Cards

### Card 2: Seed files.watcherExclude into the VS Code settings template

- **Context:**
  - `plugins/mill/scripts/_vscode.py`
- **Edits:**
  - `plugins/mill/templates/vscode-settings.json`
  - `plugins/mill/unit_tests/test-vscode.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `templates/vscode-settings.json`, add a top-level `"files.watcherExclude"` key (a sibling of the existing `"workbench.colorCustomizations"` and `"window.title"` keys) with exactly these three glob entries set to `true`: `"**/.portals/**"`, `"**/.wiki/**"`, `"**/.active/**"`. The file must remain valid JSON after the addition (mind the trailing comma between top-level keys). Do not introduce a new `<TOKEN>` placeholder — this is a static block; `_vscode.render_settings` only substitutes `<COLOR_HEX>` and `<WINDOW_TITLE>` and must continue to do so unchanged.
  - In `test-vscode.py`, extend `_test_render_settings` (or add a sibling test in the same file) to assert that the rendered output from `render_settings(...)` contains `"files.watcherExclude"` and all three glob keys (`**/.portals/**`, `**/.wiki/**`, `**/.active/**`). The existing assertions about `window.title` and the color hex must still pass.
- **Commit:** `fix(vscode): seed files.watcherExclude for junctions in settings template`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-vscode.py` (standalone `__main__` runner), covering `render_settings`/`write_settings` including the new watcherExclude assertion. Scoped to the single test file because this batch touches only the template and its renderer's test. No migration test — migration is out of scope by decision.
