# Plan: 'millpy-vscode rework: hybrid spawn/pick + filter active editors'

```yaml
task: 'millpy-vscode rework: hybrid spawn/pick + filter active editors'
slug: mill-vscode-rework
approved: true
started: 20260509-154605
parent: main
root: ""
verify: python plugins/mill/unit_tests/run-all.py
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: vscode-processes-helper
    file: 01-vscode-processes-helper.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-vscode-processes.py
  - number: 2
    name: vscode-cli-integration
    file: 02-vscode-cli-integration.md
    depends-on: [1]
    verify: python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: helper-module-isolation

- **Decision:** All process-probe logic — both the OS-dispatch entry point `find_open_vscode_paths()` and the cmdline-matching predicate `_path_matches_cmdline()` — lives in the new helper module `plugins/mill/scripts/_vscode_processes.py`. `millpy-vscode.py` imports the public symbol `find_open_vscode_paths`. `_path_matches_cmdline` is module-private (single leading underscore) but is also imported by `millpy-vscode.py` since it is the predicate the CLI uses to filter candidate worktrees.
- **Rationale:** Keeps the parser pure and unit-testable independently of the picker; mirrors the discussion's `vscode-processes-helper-module` decision.
- **Applies to:** all batches.

### Decision: subprocess-via-_subprocess_util

- **Decision:** The only subprocess invocations made by `_vscode_processes.py` go through `_subprocess_util.run` with `timeout=5` and `check=False`. Tests mock `_vscode_processes._subprocess_util.run` (NOT `subprocess.run`).
- **Rationale:** Keeps probe failures (non-zero exit, `TimeoutExpired`, `FileNotFoundError`) routable through one boundary; matches the discussion's `probe-failure-silent-fallback` and `probe-timeout-5s` decisions.
- **Applies to:** all batches.

### Decision: silent-empty-set-on-failure

- **Decision:** Every error path in `_vscode_processes.py` (subprocess returncode != 0, `subprocess.TimeoutExpired`, `OSError`/`FileNotFoundError` raised by `_subprocess_util.run`, parser-internal `Exception`) returns the empty `set[Path]`. No stderr writes from this helper. Errors are NOT silently swallowed — `_subprocess_util.run` already prints its own `[subprocess] exit code=...` breadcrumb, which is enough trail for diagnostics.
- **Rationale:** Per the `probe-failure-silent-fallback` decision; keeps the picker usable when the probe wedges or is missing.
- **Applies to:** all batches.

### Decision: tests-mock-find_open_vscode_paths-not-subprocess

- **Decision:** `test-millpy-vscode.py` patches `mill_vscode._vscode_processes.find_open_vscode_paths` (the function symbol imported into `mill_vscode`'s namespace) directly. It does NOT patch `subprocess.run` or `_subprocess_util.run` for any new test — only the existing `mill_vscode.subprocess.run` patch (used to capture the `code <path>` invocation) is preserved. `test-vscode-processes.py` patches `_vscode_processes._subprocess_util.run` with canned `subprocess.CompletedProcess` returns OR a `side_effect=` that raises the exception under test.
- **Rationale:** End-to-end tests focus on picker behavior given a known set of "already-open" paths; parser tests focus on the canned-output → set-of-Paths transformation. Keeps each test file's mocking minimal and unambiguous.
- **Applies to:** batch 1 (parser tests), batch 2 (CLI tests).

### Decision: argparse-mutex-via-add_mutually_exclusive_group

- **Decision:** `--new` and `--slug` are placed in an `argparse.add_mutually_exclusive_group()`. Passing both produces argparse's standard usage error and `SystemExit(2)`. No custom validation is added.
- **Rationale:** Matches the discussion's `new-and-slug-mutually-exclusive` decision; uses the stdlib's existing exit-2 convention.
- **Applies to:** batch 2.

## All Files Touched

- `plugins/mill/scripts/_vscode_processes.py`
- `plugins/mill/scripts/millpy-vscode.py`
- `plugins/mill/skills/mill-vscode/SKILL.md`
- `plugins/mill/unit_tests/test-millpy-vscode.py`
- `plugins/mill/unit_tests/test-vscode-processes.py`
