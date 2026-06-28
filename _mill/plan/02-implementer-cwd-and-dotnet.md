# Batch: implementer-cwd-and-dotnet

```yaml
task: Fix review finding-count parser, nested-layout brief path, verify cwd, process leaks, and missing done-gate
batch: implementer-cwd-and-dotnet
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py
depends-on: []
```

## Batch Scope

Fixes two bugs in the implementer verify path: #554 (finalize stage runs batch verify from hub cwd instead of git_root in nested layouts, producing spurious MSB1009 errors) and #556 (dotnet test verify leaves orphaned testhost/build-server processes on Windows that lock files for subsequent runs). Both bugs are fixed in `_implementer_common.py`. `millpy-implement.py` is modified to pass `git_root` to the finalize path. Unit tests cover the cwd-selection logic and the dotnet cleanup call. Card 5 edits `_implementer_common.py`, Card 6 edits `millpy-implement.py`, and Card 7 edits `test-implementer-common.py`; all three touch different files. The implementer should implement card 5 first, then card 6 (relies on the expanded API from card 5), then card 7 (tests the expanded API).

## Cards

### Card 5: Add `git_root` param to verify helpers and dotnet cleanup in `_implementer_common.py` (#554, #556)

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Make four changes to `_implementer_common.py`, all in the verify-gate chain:

  **Change 1 — `_run_verify_gate` (#554 + #556):**
  Add `git_root: Path | None = None` as a keyword-only parameter after the existing positional parameters. Docstring update: add "git_root: Optional git root directory used as cwd for the verify subprocess. When None, falls back to project_root." Change the `subprocess.run` call at line 383 from `cwd=project_root` to `cwd=(git_root if git_root is not None else project_root)`.

  Also add dotnet cleanup (#556): place the cleanup immediately after `result = subprocess.run(...)`, **before the `if result.returncode != 0:` check** — this ensures cleanup fires on both success and failure. Failed dotnet runs (the re-run lock scenario #556 targets) also release testhost/build-server processes. The placement is:

  ```python
  result = subprocess.run(...)
  # dotnet cleanup: release testhost/MSBuild locks before caller retries.
  # Wrapped in try/except so a TimeoutExpired or FileNotFoundError here
  # never poisons the verify verdict (best-effort, non-fatal).
  if sys.platform == "win32" and verify_cmd is not None and "dotnet" in verify_cmd.lower():
      try:
          subprocess.run(["dotnet", "build-server", "shutdown"], capture_output=True, timeout=30)
      except Exception:
          pass
  if result.returncode != 0:
      ...  # existing error handling
  ```

  The `subprocess` module is already imported in this file — do not use a new alias. The `try/except Exception: pass` wrapper is required: without it, a `TimeoutExpired` or `FileNotFoundError` from the cleanup call would be caught by the outer verify `except Exception` handler and returned as a stuck dict, turning a passing verify into a false failure.

  **Change 2 — `_run_verify_gates` (#554):**
  Add `git_root: Path | None = None` as a keyword-only parameter. Thread it to both `_run_verify_gate` calls: `_run_verify_gate(project_root, verify_cmd, git_root=git_root)` and `_run_verify_gate(project_root, module_wide_verify_cmd, git_root=git_root)`. Update the docstring to document `git_root`.

  **Change 3 — `_forward_output` (#554):**
  Add `git_root: Path | None = None` as a keyword-only parameter (position in the signature: after the last existing kw-only param). Thread it to all four `_run_verify_gates` call sites inside `_forward_output`. The four call sites (as of the current file state) are:
  - Line 647: single-line `gate_result = _run_verify_gates(project_root, verify_cmd, module_wide_verify_cmd)`
  - Lines 771-773: multi-line form:
    ```python
    gate_result = _run_verify_gates(
        project_root, verify_cmd, module_wide_verify_cmd
    )
    ```
  - Line 826: single-line `gate_result = _run_verify_gates(project_root, verify_cmd, module_wide_verify_cmd)`
  - Line 882: single-line `gate_result = _run_verify_gates(project_root, verify_cmd, module_wide_verify_cmd)`

  Add `git_root=git_root` to every call. The multi-line form at 771-773 must expand to:
  ```python
  gate_result = _run_verify_gates(
      project_root, verify_cmd, module_wide_verify_cmd, git_root=git_root
  )
  ```
  Before editing, re-read the function to confirm these line numbers and catch any additional call sites added after this plan was written.

  **Change 4 — `finalize_from_output` (#554):**
  Add `git_root: Path | None = None` as a keyword-only parameter. Thread it to the `_forward_output` call: add `git_root=git_root` to the call at line 561.

  All four new parameters default to `None`. No existing callers need to change.
- **Commit:** `fix(_implementer_common): add git_root verify cwd and dotnet build-server shutdown (#554 #556)`

---

### Card 6: Pass `git_root` to `finalize_from_output` in `millpy-implement.py` (#554)

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `millpy-implement.py`, in the `--stage finalize` branch (lines 234-266):

  `project_root` is `_paths.resolve_hub_path()` (line 105) and `git_root` is `_paths.resolve_git_root()` (line 108). Both are already in scope at the start of `main()`.

  The `finalize_from_output` call at line 255 currently does not pass `git_root`. Add `git_root=git_root` as a keyword argument to this call. The full call becomes:
  ```python
  return finalize_from_output(
      Path(args.agent_output),
      project_root,
      start_sha=start_sha,
      snapshot_path=snapshot_path,
      session_id=session_id,
      verify_cmd=verify_cmd,
      module_wide_verify_cmd=module_wide_verify_cmd,
      card_count=card_count,
      task_dir=status_path.parent,
      parent_branch=parent_branch,
      git_root=git_root,
  )
  ```
  No other changes needed in `millpy-implement.py`.
- **Commit:** `fix(millpy-implement): pass git_root to finalize_from_output for nested-layout verify cwd (#554)`

---

### Card 7: Add `_run_verify_gate` cwd and dotnet-cleanup tests to `test-implementer-common.py` (#554, #556)

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add three new test functions (or test blocks) to `test-implementer-common.py`. The file already imports `unittest.mock` and `_run_verify_gates`; import `_run_verify_gate` from `_implementer_common` if it is not already imported.

  **Test A — git_root kwarg selects cwd (#554):**
  Use a temp dir setup. Create two directories: `project_root = tmpdir / "hub"` and `git_root = tmpdir / "repo"`. Write a shell script (or batch file on Windows; use `sys.platform` to pick the right script) in `git_root` that exits 0, and place a script of the same name in `project_root` that exits 1 (so the cwd is observable via exit code). Run `_run_verify_gate(project_root, "./check.sh", git_root=git_root)` (adjust command for Windows). Assert the result is `None` (the git_root script exits 0). Then run without `git_root` kwarg; assert result is not None (project_root script exits 1). If writing actual scripts is complex in a cross-platform unit test, an alternative: mock `subprocess.run` via `unittest.mock.patch("_implementer_common.subprocess.run")` and assert the `cwd` kwarg passed to `subprocess.run` equals `git_root` when `git_root` is provided and equals `project_root` when `git_root=None`.

  **Test B — git_root=None falls back to project_root (#554):**
  Mock `subprocess.run`; call `_run_verify_gate(project_root, "echo ok")`. Assert `subprocess.run` is called with `cwd=project_root`. This confirms the default behavior is unchanged.

  **Test C — dotnet cleanup fires regardless of verify exit code (#556):**
  Use `unittest.mock.patch("sys.platform", "win32")` and `unittest.mock.patch("_implementer_common.subprocess.run")` (or the module-level subprocess) to capture calls. Run two sub-cases:
  - Sub-case C1: main verify mock returns exit code 0. Assert `["dotnet", "build-server", "shutdown"]` is called (cleanup on success).
  - Sub-case C2: main verify mock returns exit code 1 (failure). Assert `["dotnet", "build-server", "shutdown"]` is STILL called (cleanup on failure — this is the key regression guard for #556). The mock's `returncode` attribute must be set to 1 for the second call.
  Also assert the dotnet shutdown call is NOT made when the verify command does not contain "dotnet".

  Print PASS messages for each test using the existing pattern in the file.
- **Commit:** `test(_implementer_common): add git_root cwd and dotnet cleanup unit tests (#554 #556)`

## Batch Tests

The `verify:` command runs only `test-implementer-common.py` via `--only`. This file exercises the `_run_verify_gate` cwd-selection behavior (Test A, B) and the dotnet cleanup call (Test C). Existing tests in the file continue to run as regression coverage. No LLM or real git subprocess is required for the new mock-based tests; the existing `_setup_fixture` helper is available if a real git repo fixture is needed for Test A.
