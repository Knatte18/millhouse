Perfect! All work is complete. Both cards have been successfully implemented and committed, and the verify command passes all tests. Here's a summary of what was accomplished:

## Implementation Summary

### Card 3: Extract _posix_shell_run_args helper and apply to merge-in subagent
- **File: `plugins/mill/scripts/_implementer_common.py`**
  - Added `_posix_shell_run_args(cmd: str) -> tuple` helper function that detects the platform and bash availability
  - On Windows with bash available, routes commands through `bash -c` to honor POSIX syntax (e.g., `PYTHONPATH=`)
  - On other platforms or without bash, returns the command string with `shell=True`
  - Refactored `_run_verify_gate` to use the new helper instead of inline bash-detection logic

- **File: `plugins/mill/scripts/millpy-merge-in-subagent.py`**
  - Added `_posix_shell_run_args` to the import list from `_implementer_common`
  - Replaced all three `subprocess.run(args.cmd, shell=True, ...)` call sites with the new helper pattern:
    1. Line ~175: Finalize stage verify check
    2. Line ~275: Full-stage initial verify check
    3. Line ~343: Full-stage post-agent re-verification

### Card 4: _posix_shell_run_args routing tests
- **File: `plugins/mill/unit_tests/test-merge-in-subagent.py`**
  - Added import for `_implementer_common`
  - Added three comprehensive test cases:
    1. **posix-shell-args-windows-with-bash**: Verifies Windows with bash available routes through `[bash, "-c", cmd]`
    2. **posix-shell-args-windows-no-bash**: Verifies Windows without bash falls back to `(cmd, {"shell": True})`
    3. **posix-shell-args-posix**: Verifies POSIX platform uses `(cmd, {"shell": True})`

All tests pass successfully, confirming the implementation correctly routes POSIX shell commands through bash on Windows while maintaining backward compatibility on other platforms.

{"status":"success","commit_sha":"41741b189db06244bfc1299fc3f2da1b29db2955","session_id":"d965e1bd-7de4-4b57-94f3-5332c9c14db1"}