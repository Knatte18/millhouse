# Batch: worktree-asarray

```yaml
task: Fix mill-merge-in stale ref check, PowerShell 5.1 ConvertTo-Json, and _status str-path crash
batch: worktree-asarray
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-worktree.py
depends-on: []
```

## Batch Scope

Fixes GitHub #602: `_worktree._default_enumerate_processes` invokes `powershell -Command "... | ConvertTo-Json -AsArray"`. `-AsArray` is a PowerShell-7-only parameter; on Windows PowerShell 5.1 (the default `powershell` alias) the command exits non-zero, so the helper's `except`/`returncode != 0` path silently returns `[]`, disabling the live-process safety guard before `kill_stale_holders` runs. Card 3 removes the flag; Card 4 adds regression coverage for the previously-untested default enumerator path. No external interface changes — the next batch does not depend on this one.

## Cards

### Card 3: Drop -AsArray from _default_enumerate_processes

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_worktree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_default_enumerate_processes` (nested function inside `kill_stale_holders`, `plugins/mill/scripts/_worktree.py` lines ~358-386), change the three-part string literal passed to `-Command` from:
  ```
  "Get-CimInstance Win32_Process | "
  "Select-Object ProcessId, CommandLine | "
  "ConvertTo-Json -AsArray",
  ```
  to:
  ```
  "Get-CimInstance Win32_Process | "
  "Select-Object ProcessId, CommandLine | "
  "ConvertTo-Json",
  ```
  (drop only the ` -AsArray` suffix on the third line; no other change to the string, the surrounding `_subprocess_util.run(...)` call, or the normalization logic at lines 375-376 that already turns a single non-list JSON result into a one-element list). Do not touch the non-Windows early-return branch (`if sys.platform != "win32": return []`) or the `taskkill` logic below.
- **Commit:** `fix(worktree): drop PS7-only -AsArray flag from process-enum ConvertTo-Json (#602)`

### Card 4: Add regression test for the real _default_enumerate_processes path

- **Context:**
  - `plugins/mill/scripts/_worktree.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new test case to `test-worktree.py` (near the existing `kill_stale_holders` tests around lines 339-400, following the same `patch("_worktree._subprocess_util.run", side_effect=...)` pattern already used there) that exercises the real default enumerator rather than an injected fake — i.e. call `kill_stale_holders(worktree)` (or `kill_stale_holders(worktree, enumerate_processes=None)`) with `_worktree._subprocess_util.run` patched to a fake that captures the `argv` it was called with and returns `MagicMock(returncode=0, stdout=<json>, stderr="")`. Guard the whole case with `if sys.platform == "win32":` (print a `SKIP` line and continue otherwise) since `_default_enumerate_processes` itself early-returns `[]` on non-Windows before ever building the command.
  Within the guarded case, add two assertions using the captured argv:
  1. Join the captured argv (or inspect its `-Command` string element directly) and assert the substring `"-AsArray"` is absent — this is the regression check for #602.
  2. Re-invoke with the fake `run` returning `stdout` set to a JSON-encoded **single dict** (not a list) shaped like `{"ProcessId": 999, "CommandLine": f"poll {worktree}/file"}`, and assert `kill_stale_holders` still produces a `taskkill` call for pid `999` (via the same `kill_calls`-capturing pattern used at lines 347-363) — this confirms the existing `data = [data] if data else []` normalization (lines 375-376) still correctly handles the single-object case that `-AsArray` used to (incorrectly) guarantee against on PS7.
  Print a `PASS:` line for each of the two assertions, matching the file's existing style (see e.g. line 363).
- **Commit:** `test(worktree): cover real process-enum command shape and single-dict JSON normalization`

## Batch Tests

`verify:` scopes to `test-worktree.py` only via `run-all.py --only test-worktree.py` — both cards touch only this file's subject module (`_worktree.py`) and its own test file, with no cross-cutting helper involved.
