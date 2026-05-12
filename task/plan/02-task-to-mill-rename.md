# Batch: task-to-mill-rename

```yaml
task: 33 (A) -- Working-dir rename + portals redesign + junction cleanup
batch: task-to-mill-rename
number: 2
cards: 7
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

Updates `wiki/config.yaml`, the config template, spawn/implement scripts, and unit tests so that `_mill/` is the canonical working-state subdirectory. After this batch `wiki/config.yaml` says `_mill/discussion.md`, `_mill/plan/`, `_mill/reviews/`, and the scripts that write working state do so under `_mill/`. The compat shim from batch 01 ensures in-flight `task/`-based worktrees continue to work transparently until they are cleaned up.

## Cards

### Card 8: Update `wiki/config.yaml` paths block

- **Context:**
  - `wiki/config.yaml`
- **Edits:**
  - `wiki/config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `wiki/config.yaml`, update the three entries under the `paths:` key:
  - `discussion_file: task/discussion.md` → `discussion_file: _mill/discussion.md`
  - `plan_dir:        task/plan/` → `plan_dir:        _mill/plan/`
  - `reviews_dir:     task/reviews/` → `reviews_dir:     _mill/reviews/`
  Leave all other keys, comments, and whitespace untouched.
  **Bootstrap safety justification:** This config mutation is safe mid-flight because batch 01 wired every caller through `_paths.resolve_task_path`. After batch 01, when a caller reads `paths.plan_dir = "_mill/plan/"` from config, the shim checks `_mill/plan/` first; if absent (in-flight worktree), it falls back to `task/plan/` and logs a compat warning. No in-flight worktree is broken by this change. New worktrees spawned after batch 02 will write to `_mill/` natively. Old worktrees remain on `task/` until cleaned up.
- **Commit:** `feat(config): rename task/ paths to _mill/ in wiki config`

### Card 9: Update `plugins/mill/templates/wiki-config.yaml` paths block

- **Context:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Edits:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Read the template's `paths:` block carefully before editing. The template uses `active/<SLUG>/discussion.md` format (NOT `task/discussion.md`), so a mechanical `task/ -> _mill/` string replace will silently miss it. Rewrite the three path entries in the `paths:` block to use the new canonical names:
  - `discussion_file: _mill/discussion.md`
  - `plan_dir:        _mill/plan/`
  - `reviews_dir:     _mill/reviews/`
  Preserve all surrounding comment lines and other keys verbatim. Do not alter indentation, spacing, or comment style.
- **Commit:** `feat(templates): rename task/ paths to _mill/ in wiki-config template`

### Card 10: Update `_spawn_core.py` `write_initial_status`

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_spawn_core.py`, locate `write_initial_status`. Make three changes within this function:
  (1) Line 718: `worktree_path / "task" / "status.md"` → `worktree_path / "_mill" / "status.md"`.
  (2) Line 722: `["git", "-C", str(worktree_path), "add", "task/status.md"]` → `["git", "-C", str(worktree_path), "add", "_mill/status.md"]`.
  (3) The error message string at line 726 `"git add task/status.md failed: ..."` → `"git add _mill/status.md failed: ..."`.
  The `parent.mkdir(parents=True, exist_ok=True)` call derives its directory from the updated path on line 718, so it will automatically create `_mill/` instead of `task/` — no change needed there.
- **Commit:** `feat(spawn-core): write initial status to _mill/status.md`

### Card 11: Update `millpy-implement.py` default plan_dir and cleanliness snapshot

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  (1) Find the `cfg.get` call that reads `plan_dir` with a fallback default string `"task/plan/"` (typically `cfg.get("paths", {}).get("plan_dir", "task/plan/")`). Change the fallback from `"task/plan/"` to `"_mill/plan/"`.
  (2) Find both occurrences of the cleanliness snapshot path construction (pattern: `project_root / "task" / f".cleanliness-snapshot-..."` or `/ "task" / ".cleanliness-snapshot-"`). Replace `"task"` with `"_mill"` in both. These two lines were explicitly excluded from the batch 01 shim because they are internal mill state paths, not config-driven paths.
  Do not touch any other `"task"` string in this file — the remaining ones will be handled by the batch 01 shim at runtime.
- **Commit:** `feat(implement): update default plan_dir and cleanliness snapshot to _mill/`

### Card 12: Update dry-run prints in `millpy-spawn.py` and `millpy-claim.py`

- **Context:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/millpy-claim.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/millpy-claim.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In both files, find the dry-run print statement that describes creating the `task/` working-state directory (look for strings containing `task/` near a `--dry-run` or `[dry-run]` context). Update the user-visible string to say `_mill/` instead. These are display strings only — no filesystem path logic changes. If no dry-run print for `task/` exists in a file, skip that file.
- **Commit:** `feat(spawn,claim): update dry-run prints to reference _mill/`

### Card 13: Update `millpy-migrate-layout.py` log message strings

- **Context:**
  - `plugins/mill/scripts/millpy-migrate-layout.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-migrate-layout.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-migrate-layout.py`, find all occurrences of `"task/"` inside `_log(...)` call string literals and `print(...)` call string literals that describe the migration operation (e.g., `"task/ move for {slug}"`, `"moving task/"`, `"task/ migration"` in log output). Replace `task/` with `_mill/` in those string literals only. Do NOT change any path construction logic (e.g., `src = wt / "task"`) — those filesystem paths are the migration's source layout and must remain `task/` to locate the directories being moved.
- **Commit:** `docs(migrate-layout): update log messages to reference _mill/`

### Card 14: Update unit tests to use `_mill/` fixture paths

- **Context:**
  - `plugins/mill/unit_tests/test-abandon.py`
  - `plugins/mill/unit_tests/test-cleanliness.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
  - `plugins/mill/unit_tests/test-spawn-core.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-abandon.py`
  - `plugins/mill/unit_tests/test-cleanliness.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
  - `plugins/mill/unit_tests/test-spawn-core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In each test file, find all fixture path constructions that create the working-state subdirectory or files within it. Replace `"task"` with `"_mill"` in those fixture lines. Patterns to look for: `tmp / "task"`, `tmp_dir / "task"`, `Path(...) / "task"`, `mkdir(.../task/...)`, string literals `"task/status.md"`, `"task/plan/"`, `"task/reviews/"` in path construction. Also update assertion lines that check for `task/status.md`, `task/plan/`, or `task/reviews/` to check `_mill/status.md`, `_mill/plan/`, `_mill/reviews/`. Do NOT change any line that is intentionally testing the compat shim added in batch 01 — those tests explicitly create `task/` as a fallback path and must remain unchanged.
- **Commit:** `test: update unit test fixtures from task/ to _mill/`

## Batch Tests

Run `python plugins/mill/unit_tests/run-all.py`. All existing tests must pass, including the `test_resolve_task_path` shim tests from batch 01 which explicitly use `task/` as the fallback path. New `_mill/` fixtures must be found and read correctly.
