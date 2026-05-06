# Batch: core-script

```yaml
task: '5 (A) — mill-bg.py: project-lokal backgrounding'
batch: core-script
cards: 2
verify: python plugins/mill/unit_tests/test-shortcut-wrapper.py
depends-on: []
```

## Batch Scope

This batch creates the `millpy-bg.py` CLI script and wires it into the shortcut registry. After this batch, the script is importable as a mill CLI entry point, the shortcut-wrapper test confirms `SHORTCUT_SCRIPTS` includes the new entry, and the script can be invoked manually to background any command with output routed to `.scratch/`.

## Cards

### Card 1: Create `millpy-bg.py`

- **Reads:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_shortcuts.py`
- **Modifies:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Deletes:** none
- **Requirements:**

  The script has two modes, selected by whether `"--_worker"` appears in `sys.argv`.

  **Launcher mode** (default — `"--_worker"` absent):

  Parse `sys.argv[1:]` by locating `"--"` manually. Everything before `"--"` is mill-bg args; everything after is the command to background. Required flag before `"--"`: `--slug <str>`. Missing `--slug` or missing `--` → print error to stderr and exit 1.

  Resolve git root by running `["git", "rev-parse", "--show-toplevel"]` via `subprocess.run` with `capture_output=True, text=True`. Non-zero exit → print error to stderr and exit 1.

  Compute log path: `<git_root>/.scratch/bg-<YYYYMMDD-HHMMSS>-<slug>.log` where the timestamp is `datetime.utcnow().strftime("%Y%m%d-%H%M%S")`. Create `.scratch/` with `Path.mkdir(exist_ok=True)` if absent.

  Build worker argv: `[sys.executable, str(Path(__file__).resolve()), "--_worker", "--log", str(log_path), "--"] + cmd`.

  Spawn the worker as a detached process via `subprocess.Popen`:
  - Windows (`os.name == "nt"`): `creationflags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB` where the three constants are `0x00000008`, `0x00000200`, `0x01000000`. Pass `stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL`.
  - Non-Windows: `start_new_session=True`. Pass `stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL`.

  Print exactly `pid=<N> log=<path>` (one line, nothing else) to stdout and return 0. The entry point is named `_launcher_main(args: list[str]) -> int`; it returns 0 on success or 1 on error. The top-level `main(argv=None)` function calls `sys.exit(_launcher_main(...))` or `sys.exit(_worker_main(...))`.

  **Worker mode** (`"--_worker"` in `sys.argv` before any import — check this early and branch before importing anything):

  Strip `"--_worker"` from the remaining argv. Locate `"--"` and split: everything before `"--"` is worker flags (`--log <abs-path>`); everything after is the command to run. Missing `--log` or empty command → print error to stderr and return 1.

  Open `log_path` for write in text mode with `encoding="utf-8"` and `buffering=1` (line-buffered). Run `subprocess.run(cmd, stdout=log_f, stderr=subprocess.STDOUT)`. After the subprocess returns, write `f"\n[mill-bg] EXIT {result.returncode}\n"` to the log file. Flush and return 0. The entry point is named `_worker_main(args: list[str]) -> int`.

  **Function signatures:** Both `_launcher_main(args: list[str]) -> int` and `_worker_main(args: list[str]) -> int` return `int` (0/1). They never call `sys.exit` themselves. The top-level `main(argv: list[str] | None = None) -> int` delegates to one of them and `if __name__ == "__main__": sys.exit(main())` handles process exit.

  **Import structure:** The worker-mode fast-path must execute before any import that requires mill modules. Use a top-of-file guard:

  ```python
  import sys
  if "--_worker" in sys.argv:
      # worker path — stdlib imports only, then _worker_main(), sys.exit()
      ...
  # launcher path continues here
  ```

  This ensures `sys.executable millpy-bg.py --_worker ...` succeeds even without `PYTHONPATH` pointing to mill scripts.

  The module docstring must document both modes and their CLI signatures.

- **Commit:** `feat(mill-bg): add millpy-bg.py launcher+worker for project-local backgrounding`

### Card 2: Register `millpy-bg` in shortcut list and fix stale test comment

- **Reads:**
  - `plugins/mill/scripts/_shortcuts.py`
  - `plugins/mill/unit_tests/test-shortcut-wrapper.py`
- **Modifies:**
  - `plugins/mill/scripts/_shortcuts.py`
  - `plugins/mill/unit_tests/test-shortcut-wrapper.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  In `_shortcuts.py`, append `"millpy-bg"` to the end of `SHORTCUT_SCRIPTS`. The list comment (`# User-callable v2 scripts…`) needs no change.

  In `test-shortcut-wrapper.py`, the comment on the first test section currently reads `# --- write_all against empty tempdir creates all 13 PS1 files ---`. Update it to remove the hardcoded count: `# --- write_all against empty tempdir creates one PS1 file per SHORTCUT_SCRIPTS entry ---`. No assertion changes are needed — the assertions already use `len(SHORTCUT_SCRIPTS)` dynamically.

  Similarly update the comment `# --- write_all against tempdir with legacy .py wrappers → .py files deleted, .ps1 files present ---` if it contains any hardcoded count (check and fix if so).

- **Commit:** `feat(shortcuts): add millpy-bg to SHORTCUT_SCRIPTS`

## Batch Tests

The verify command `python plugins/mill/unit_tests/test-shortcut-wrapper.py` runs the existing shortcut wrapper test suite. After Card 2, `SHORTCUT_SCRIPTS` has 14 entries. The test's `expected_count = len(SHORTCUT_SCRIPTS)` assertion is dynamic and will automatically validate the new count. The test also verifies that `write_all` creates a `millpy-bg.ps1` wrapper and that legacy `millpy-bg.py` wrapper cleanup works.
