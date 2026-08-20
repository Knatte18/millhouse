# Batch: worktree-removal-longpaths

```yaml
task: 'millpy-implement --stage baseline: Windows verify-baseline worktree teardown fails (WinError 145 / long paths), leaves orphaned artifacts'
batch: worktree-removal-longpaths
number: 2
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Fixes Cluster A: `_worktree.remove_safe`'s `git worktree remove`/`git worktree prune` invocations omit `-c core.longpaths=true`, while `_verify_baseline.py`'s `git worktree add` (the creation side of the same worktree) already passes it. This batch is a small, self-contained argv fix plus its test, independent of the `_long_path.py` helper batch — it does not touch Python-level path strings, only the git command line. Root of the DAG alongside batch 1.

## Cards

### Card 3: Add `-c core.longpaths=true` to `remove_safe`'s `git worktree remove`/`prune` argv

- **Context:**
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/unit_tests/test-verify-baseline.py`
- **Edits:**
  - `plugins/mill/scripts/_worktree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_worktree.py::remove_safe`, insert `-c`, `core.longpaths=true` immediately after `-C`, `str(cwd)` and before the `worktree` subcommand token, mirroring `_verify_baseline.py:106`'s existing creation-side placement (`["git", "-C", str(git_root), "-c", "core.longpaths=true", "worktree", "add", ...]`) exactly. Two call sites inside `remove_safe`:
  - The `git worktree remove` argv construction:
    ```
    cmd = ["git", "-C", str(cwd), "worktree", "remove"]
    ```
    becomes:
    ```
    cmd = ["git", "-C", str(cwd), "-c", "core.longpaths=true", "worktree", "remove"]
    ```
  - The `git worktree prune` invocation:
    ```
    prune = _subprocess_util.run(
        ["git", "-C", str(cwd), "worktree", "prune"],
    )
    ```
    becomes:
    ```
    prune = _subprocess_util.run(
        ["git", "-C", str(cwd), "-c", "core.longpaths=true", "worktree", "prune"],
    )
    ```
  Do not modify the plain `remove()` function's argv (its own `git worktree remove` call) — `remove_safe` is the sole teardown path this task's `_mill/discussion.md` scopes in; `remove()` has no callers in `plugins/mill/scripts/` and is explicitly out of scope.
- **Commit:** `fix(worktree): pass -c core.longpaths=true on git worktree remove/prune in remove_safe`

### Card 4: Add argv-shape assertions for `-c core.longpaths=true` to `test-worktree.py`

- **Context:**
  - `plugins/mill/unit_tests/test-verify-baseline.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new test case to `test-worktree.py::main()` (place it directly after the existing "remove_safe prunes a stale nested-worktree registration after force-removing the enclosing task worktree" case) that:
  1. Creates a `tempfile.TemporaryDirectory()`-backed `path` (the worktree to remove, must exist on disk) and `cwd` directory.
  2. Patches `_worktree._subprocess_util.run` with a `side_effect` function that appends every received `argv` list to a local `captured_argv` list and returns `MagicMock(returncode=0, stdout="", stderr="")` for every call (covering both the `worktree remove` and `worktree prune` invocations `remove_safe` makes).
  3. Patches `_worktree.kill_stale_holders` to a no-op (`patch("_worktree.kill_stale_holders")`), matching the existing mocking convention used by the other `remove_safe`-with-mocked-subprocess cases in this file.
  4. Calls `remove_safe(path, cwd=cwd, junctions_cfg={})`.
  5. Asserts `len(captured_argv) == 2` (the `worktree remove` call followed by the `worktree prune` call).
  6. For `captured_argv[0]` (the `worktree remove` argv), asserts `-c`/`core.longpaths=true` appears as an adjacent pair (`argv[i] == "-c" and argv[i + 1] == "core.longpaths=true"`) and that this pair's index sits after the `-C` index and before the `worktree` index — mirroring `test-verify-baseline.py`'s existing `-c core.longpaths=true` pair-and-order assertion pattern (the `longpaths_index is not None` check plus the `c_index < longpaths_index < worktree_index` ordering check) applied to the removal-side argv instead of the creation-side one.
  7. Repeats the identical adjacent-pair-and-order assertion for `captured_argv[1]` (the `worktree prune` argv).
- **Commit:** `test(worktree): assert -c core.longpaths=true in remove_safe's remove/prune argv`

## Batch Tests

`verify:` runs `test-worktree.py`, which covers the new argv-shape assertions for Card 3's `-c core.longpaths=true` fix alongside the file's existing `remove`/`remove_safe`/`kill_stale_holders`/`processes_holding_path` coverage.
