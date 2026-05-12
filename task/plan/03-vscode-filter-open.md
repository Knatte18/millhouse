# Batch: vscode-filter-open

```yaml
task: 53 (A) — Speed up PS1 wrappers by invoking venv Python directly
batch: vscode-filter-open
number: 3
cards: 2
verify: "python plugins/mill/unit_tests/test-millpy-vscode.py"
depends-on: [1]
```

## Batch Scope

This batch adds `--filter-open` to `millpy-vscode.py` and gates the `_filter_open_worktrees` call on that flag. Without `--filter-open` the `powershell.exe Get-Process Code` spawn never happens; with it, the existing filtering behavior is preserved. `import _vscode_processes` stays at module level to keep existing `patch("mill_vscode._vscode_processes...")` mock paths working in the test suite. Two existing tests that assert probe-based filtering are updated to pass `--filter-open`; one additional test is updated to preserve its stated behavior; two new tests are added. This batch is parallel with batch 02 — no shared files.

Batch-local decision: see `filter-open-flag-default-off` in discussion.md § Decisions.

## Cards

### Card 4: Add --filter-open flag to millpy-vscode.py

- **Context:**
  - `plugins/mill/scripts/_vscode_processes.py`
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-vscode.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add `--filter-open` argument to the `argparse.ArgumentParser` in `main()`:
    ```python
    parser.add_argument(
        "--filter-open",
        action="store_true",
        help="Filter out worktrees that already have a VS Code window open.",
    )
    ```
    This argument is standalone (not mutually exclusive with `--new`/`--slug`).
  - In `main()`, in the `else:` branch (around current line 212) where `_filter_open_worktrees` is called, gate the call on `args.filter_open`:
    ```python
    if args.filter_open:
        filtered = _filter_open_worktrees(active, wiki_path, cfg.get("hub_relative_path", "."))
        if not filtered:
            return _spawn_and_open(worktrees_dir, active, wiki_path, home_tasks, branch_prefix)
    else:
        filtered = active
    ```
    The subsequent show-list / prompt loop is unchanged and operates on `filtered` in both branches.
  - `import _vscode_processes` at line 31 stays at module level — do NOT move it inside the function.
  - The `_filter_open_worktrees` function definition (lines 65–88) is unchanged.
  - Update the module-level docstring's `Usage:` section to document `--filter-open`.
- **Commit:** `feat(vscode): add --filter-open flag to gate PowerShell process probe`

### Card 5: Update test-millpy-vscode.py for --filter-open

- **Context:**
  - `plugins/mill/scripts/millpy-vscode.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-vscode.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - **Line 535** (`filter_excludes_open_worktree` test): change `mill_vscode.main([])` → `mill_vscode.main(["--filter-open"])`. This test asserts probe-based filtering which only occurs with the flag.
  - **Line 581** (`filter_empties_list_calls_spawn_then_opens` test): change `mill_vscode.main([])` → `mill_vscode.main(["--filter-open"])`. Same reason.
  - **Line 914** (`probe_returns_unrelated_paths` test): change `mill_vscode.main([])` → `mill_vscode.main(["--filter-open"])`. Without `--filter-open` the mock at line 911 is never called, so the test no longer tests its stated behavior ("unrelated probe paths → no filter"). With `--filter-open` the behavior is preserved.
  - All other existing tests that call `main([])` with `find_open_vscode_paths` mocked to `return_value=set()` are unchanged — those mocks are now irrelevant but harmless (the probe is not called without `--filter-open`).
  - **Add new test** `default_no_probe — without --filter-open, find_open_vscode_paths is never called`:
    - Set up one active worktree.
    - Mock `find_open_vscode_paths` and track whether it is called.
    - Call `main([])` with mocked `input` returning `"q"` (to exit promptly).
    - Assert `find_open_vscode_paths` was NOT called.
  - **Add new test** `filter_open_probe_called — with --filter-open, find_open_vscode_paths is called once`:
    - Set up one active worktree.
    - Mock `find_open_vscode_paths` returning `set()`.
    - Call `main(["--filter-open"])` with mocked `input` returning `"q"`.
    - Assert `find_open_vscode_paths` was called exactly once.
- **Commit:** `test(vscode): update tests for --filter-open flag gating the process probe`

## Batch Tests

`verify: python plugins/mill/unit_tests/test-millpy-vscode.py` — runs after both cards. All tests must pass. Key assertions: default no-probe behavior, `--filter-open` activates probe, existing filter tests still pass with the flag.
