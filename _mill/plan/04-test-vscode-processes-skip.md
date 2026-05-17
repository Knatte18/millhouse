# Batch: test-vscode-processes-skip

```yaml
task: 59 (A) -- Small infra fixes batch 8
batch: test-vscode-processes-skip
number: 4
cards: 1
verify: "C:/Code/millhouse/wts/millhouse/plugins/mill/.venv/Scripts/python.exe plugins/mill/unit_tests/test-vscode-processes.py"
depends-on: []
```

## Batch Scope

Wraps the two posix-mocked tests in `test-vscode-processes.py` with an `os.name != "nt"` guard so they SKIP on Windows instead of failing (#305). The Windows path module (`ntpath`) cannot be swapped by `patch("os.name", "posix")` alone, so the assertions fail on Windows runs. Skipping is consistent with the existing inline-skip pattern at line 273 (`path_match_helper_windows_case_insensitive`).

## Cards

### Card 6: Skip posix-mocked tests on Windows in `test-vscode-processes.py`

- **Context:**
  - `plugins/mill/scripts/_vscode_processes.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-vscode-processes.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/unit_tests/test-vscode-processes.py`:
  1. The test `posix_parser_basic` (current lines 92-117): wrap the entire `with (patch(...), patch(...))` block plus the result-assertion block in `if os.name != "nt":` and add an `else: print("SKIP: posix_parser_basic (Windows)")` branch. The test counter `errors` is unchanged on the SKIP path (matches the existing `path_match_helper_windows_case_insensitive` skip at line 273-274).
  2. The test `posix_parser_no_code_processes` (current lines 119-139): same wrap; SKIP message `"SKIP: posix_parser_no_code_processes (Windows)"`.
  3. Both `os.name` reads use the existing `os` import at line 4 -- no new imports needed.
  4. Keep the existing Windows-mocked tests (`windows_parser_basic`, `windows_parser_quoted_paths`, `windows_parser_empty_output`) unchanged -- they pass on Windows already and the same logic runs on Linux via the same mocks.
  5. The non-platform tests (`probe_subprocess_nonzero_exit`, `probe_subprocess_timeout`, `probe_subprocess_oserror`, `path_match_helper_*`) are unchanged.
  6. After applying the wraps, running the file on Windows produces `SKIP: posix_parser_basic (Windows)` and `SKIP: posix_parser_no_code_processes (Windows)` lines plus the existing PASS lines for the rest; exit code is 0. On Linux/macOS, all PASS lines fire and exit is 0.
- **Commit:** `fix(test-vscode-processes): skip posix-mocked tests on Windows (#305)`

## Batch Tests

`verify` runs `test-vscode-processes.py`. On the implementer's Windows machine it must exit 0 with the two `SKIP:` lines present. The non-skipped tests must continue to pass without modification.
