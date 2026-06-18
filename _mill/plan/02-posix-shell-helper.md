# Batch: posix-shell-helper

```yaml
task: Fix nested-junction teardown, Windows verify gate in merge-in, and review-plan --round threading
batch: posix-shell-helper
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-merge-in-subagent.py test-millpy-merge-in-subagent.py
depends-on: []
```

## Batch Scope

Fixes `millpy-merge-in-subagent.py` so its verify commands run through bash on Windows instead of cmd.exe. `_implementer_common._run_verify_gate` already has the bash-routing fix (applied in a prior session); the same logic needs to be shared with the merge-in subagent, which has three `subprocess.run(cmd, shell=True)` call sites that hit cmd.exe on Windows and fail on the POSIX `PYTHONPATH= ` prefix. Fix: extract the bash-detection logic from `_run_verify_gate` into a new module-level helper `_posix_shell_run_args`; import and use it in `millpy-merge-in-subagent.py`.

## Cards

### Card 3: extract _posix_shell_run_args helper and apply to merge-in subagent

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  **In `_implementer_common.py`:**
  Add `def _posix_shell_run_args(cmd: str) -> tuple:` as a module-level function immediately before `_run_verify_gate`. Both `os` and `shutil` are already imported at module level. Body:
  ```python
  bash = shutil.which("bash") if os.name == "nt" else None
  if bash:
      return [bash, "-c", cmd], {}
  return cmd, {"shell": True}
  ```
  Refactor `_run_verify_gate`: replace the inline bash-routing block (the `bash = shutil.which("bash") if os.name == "nt" else None` section, currently lines ~130-143) with a call to `_posix_shell_run_args`:
  ```python
  run_args, run_kwargs = _posix_shell_run_args(verify_cmd)
  result = subprocess.run(
      run_args,
      capture_output=True,
      text=True,
      cwd=project_root,
      **run_kwargs,
  )
  ```
  Keep all other logic in `_run_verify_gate` unchanged.

  **In `millpy-merge-in-subagent.py`:**
  Add `_posix_shell_run_args` to the existing `from _implementer_common import ...` line (~line 42). The import list already contains `_forward_output, emit_prepare, emit_prepare_no_dispatch, finalize_from_output`.

  Replace all three `subprocess.run(args.cmd, shell=True, capture_output=True, text=True, cwd=project_root)` call sites with the two-line pattern:
  ```python
  _run_args, _run_kwargs = _posix_shell_run_args(args.cmd)
  result = subprocess.run(_run_args, capture_output=True, text=True, cwd=project_root, **_run_kwargs)
  ```
  The three call sites are:
  1. In `--stage finalize` verify-fix branch (~line 175): the `subprocess.run` that checks verify after the agent ran.
  2. In `_run_verify_fix` full-stage, initial verify check (~line 274): the very first `subprocess.run(args.cmd, ...)`.
  3. In `_run_verify_fix` full-stage, post-agent re-verification (~line 341): the second `subprocess.run(args.cmd, ...)`.
  All three currently use `shell=True`. Variable names may differ between call sites (`result`, `post_verify_result`) — preserve the existing variable names.
- **Commit:** `fix(millpy-merge-in-subagent): route verify commands through bash on Windows (#508)`

### Card 4: _posix_shell_run_args routing tests

- **Context:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  `_implementer_common` is already imported at the top of `test-merge-in-subagent.py`. Add `import unittest.mock` if not already present.

  Add three test cases after the existing ones (before the summary `print` and `return` at the end of `main()`). Each uses `unittest.mock.patch` to override the module-level `os.name` attribute on `_implementer_common` and the `shutil.which` function on `_implementer_common`.

  Test case `posix-shell-args-windows-with-bash`:
  - Use `unittest.mock.patch.object(_implementer_common, "os", ...)` is NOT the right approach because `os` is a module. Instead, use `unittest.mock.patch("_implementer_common.os") as mock_os` and set `mock_os.name = "nt"`. Use `unittest.mock.patch("_implementer_common.shutil") as mock_shutil` and set `mock_shutil.which.return_value = "/usr/bin/bash"`.
  - Call `_implementer_common._posix_shell_run_args("PYTHONPATH= uv run foo")`.
  - Assert result equals `(["/usr/bin/bash", "-c", "PYTHONPATH= uv run foo"], {})`.

  Test case `posix-shell-args-windows-no-bash`:
  - Patch `_implementer_common.os` with `name = "nt"`. Patch `_implementer_common.shutil` with `which.return_value = None`.
  - Assert result equals `("PYTHONPATH= uv run foo", {"shell": True})`.

  Test case `posix-shell-args-posix`:
  - Patch `_implementer_common.os` with `name = "posix"`.
  - Assert result equals `("PYTHONPATH= uv run foo", {"shell": True})`.
  (On POSIX, `shutil.which("bash")` is not called — the `if os.name == "nt"` guard short-circuits.)
- **Commit:** `test(_implementer_common): _posix_shell_run_args routing tests (#509)`

## Batch Tests

`verify:` runs `test-merge-in-subagent.py` (the edited file with new tests) and `test-millpy-merge-in-subagent.py` (existing tests that exercise the changed `millpy-merge-in-subagent.py` code). Both files test the merge-in subagent; running both ensures the `shell=True` replacement didn't break existing behavior while also validating the new helper.
