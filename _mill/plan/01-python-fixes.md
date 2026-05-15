# Batch: python-fixes

```yaml
task: 56 (A) -- Fix mill-go/start/plan/merge runtime behavioral bugs
batch: python-fixes
number: 1
cards: 2
verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Fix two Python functions and update their unit tests. Card 1 fixes `resolve_task_path` in `_paths.py` to treat an empty directory as non-existent so the `task/` fallback triggers (bug #281). Card 2 fixes `_forward_output` in `_implementer_common.py` to require an absolutely clean working tree before emitting inferred success (bug #282 Gap 1). Each card updates the corresponding unit test file. No new Python modules are introduced.

## Cards

### Card 1: resolve_task_path -- empty dir falls back to task/

- **Context:**
  - `plugins/mill/unit_tests/test-paths.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `_paths.py`, function `resolve_task_path` (currently at approximately line 448): after `target.exists()` returns `True`, add a check: if `target.is_dir()` and the directory contains no entries (`not any(target.iterdir())`), skip the early return and fall through to the `_mill/` → `task/` fallback block. The fallback block and compat stderr message (`[compat] falling back to task/ for ...`) must print on this path, identical to the existing non-existent-dir fallback. If the directory is non-empty, the early return fires as before (unchanged behavior). File targets are unaffected (only `is_dir()` paths get the new guard).

  In `test-paths.py`, add **Case 7** after the existing Case 6. Case 7: create a temporary directory, inside it create `_mill/plan/` as an empty directory (via `.mkdir(parents=True)`, no files inside) AND `task/plan/` as a non-empty directory (write one file inside so the fallback path exists). Call `_paths.resolve_task_path(root, "_mill/plan/")`. Assert the returned path equals `root / "task" / "plan"`. Assert `[compat]` appears in stderr. Print `"PASS resolve_task_path case 7: empty _mill/plan/ dir + task/plan/ present -> task/plan/, [compat] stderr"`.

  Note on existing Case 4: Case 4 creates an empty `_mill/plan/` with NO `task/plan/` fallback. After the fix, Case 4's behavior is unchanged — the empty-dir guard fires, tries the fallback, finds no `task/plan/`, and returns the original `target` (the same value as before). Case 4's assertion (`got == root / "_mill" / "plan"`) still passes post-fix. Do not modify Case 4.
- **Commit:** `fix(_paths): treat empty _mill/ dir as non-existent in resolve_task_path (#281)`

### Card 2: _forward_output -- absolute cleanliness on inferred success

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `_implementer_common.py`, function `_forward_output`: in the inferred-success branch (the `try` block that checks `start_sha`, `snapshot_path`, `new_dirt == []`, and `HEAD != start_sha`), add a full working-tree cleanliness check BEFORE emitting the inferred-success JSON. After computing `new_dirt == []` (confirmed), run:
  ```python
  result_full = _subprocess_util.run(
      ["git", "-C", str(project_root), "status", "--porcelain", "--untracked-files=no"],
      check=True,
  )
  ```
  If `result_full.stdout.strip()` is non-empty (any dirty files, pre-existing or new), emit:
  ```python
  print(json.dumps({"status": "stuck", "stuck_type": "logic", "reason": "inferred success but working tree dirty -- implementer likely skipped git-commit on modified files"}))
  return 0
  ```
  instead of the inferred-success JSON. If stdout is empty, emit the inferred-success JSON as before (unchanged). The `check=True` in the `_subprocess_util.run` call means a non-zero git exit code raises, which is caught by the outer `except Exception` and falls through to the final `stuck/logic` sentinel — acceptable behavior.

  In `test-implementer-common.py`, **update Case 3b**: (a) change the setup comment from `# Case 3b: snapshot has pre-existing dirt; no new dirt added -> inference succeeds` to `# Case 3b: pre-existing dirt survives in full-tree check -> stuck/logic`; (b) change the `assert data["status"] == "success"` and `assert data.get("inferred") is True` assertions to `assert data["status"] == "stuck"` and `assert data["stuck_type"] == "logic"`; (c) update the print message to `"PASS: pre-existing dirt in snapshot, no new dirt -> stuck/logic (inferred-success requires clean tree)"`. Case 3b's setup block (pre-existing dirty README.md captured in snapshot, empty commit, README.md remains dirty, no JSON in output) is unchanged.
- **Commit:** `fix(_implementer_common): require clean worktree for inferred success (#282-gap1)`

## Batch Tests

Both unit test files (`test-paths.py`, `test-implementer-common.py`) are exercised by `run-all.py`. The verify command `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` covers the full unit test suite including the updated and new cases.
