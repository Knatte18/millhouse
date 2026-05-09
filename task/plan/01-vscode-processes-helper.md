# Batch: vscode-processes-helper

```yaml
task: 'millpy-vscode rework: hybrid spawn/pick + filter active editors'
batch: vscode-processes-helper
number: 1
cards: 2
verify: python plugins/mill/unit_tests/test-vscode-processes.py
depends-on: []
```

## Batch Scope

This batch ships the standalone process-probe module — pure helper code with no dependency on `millpy-vscode.py` or any picker logic. The external interface batch 2 consumes is two callables exported from `plugins/mill/scripts/_vscode_processes.py`:

- `find_open_vscode_paths() -> set[Path]` — returns the set of resolved (and on Windows lowercased) paths whose substrings appear inside running VS Code processes' cmdlines. Empty set on probe failure.
- `_path_matches_cmdline(launch_path: Path, cmdline: str) -> bool` — boundary-safe predicate batch 2 uses to filter the active-worktree list against the open-paths set when the matching has to happen against pre-resolved launch paths (worktree + `hub_relative_path`) rather than the worktrees themselves.

Tests live in the new file `plugins/mill/unit_tests/test-vscode-processes.py` and run via the existing `python plugins/mill/unit_tests/run-all.py` discovery.

Batch-local decision (refines the shared `silent-empty-set-on-failure` decision): the helper's top-level `find_open_vscode_paths()` wraps its body in a single broad `try: ... except Exception: return set()` so any unexpected parser error degrades to no-filter rather than crashing the picker. Each `_probe_*` function does its own try/except for predictable subprocess failures (returncode != 0, `subprocess.TimeoutExpired`, `OSError`).

## Cards

### Card 1: implement `_vscode_processes.py`

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_vscode_processes.py`
- **Deletes:** none
- **Requirements:** Create a new helper module `plugins/mill/scripts/_vscode_processes.py` exporting two callables, no `if __name__ == "__main__":` block, no top-level side effects:

  1. `find_open_vscode_paths() -> set[Path]` — public entry point.
     - Dispatch on `os.name`: `"nt"` calls `_probe_windows()`; otherwise calls `_probe_posix()`.
     - Wrap the dispatch and parsing body in `try: ... except Exception: return set()` so any unexpected error (including parser exceptions) yields an empty set per the `silent-empty-set-on-failure` shared decision.
     - The function returns a `set[Path]` of *cmdline strings interpreted as Path objects* — concretely, the set of distinct cmdlines collected from running VS Code processes (one cmdline per matching process). Callers (batch 2) combine this set with `_path_matches_cmdline` to test individual launch paths. The return type is `set[Path]` rather than `set[str]` so callers operate on `Path` semantics; convert with `Path(cmdline)` before insertion. (Casting an arbitrary cmdline string to `Path` is safe because the caller only feeds the resulting `Path` to `_path_matches_cmdline`, which immediately calls `str(...)` on its `cmdline` argument.)

  2. `_probe_windows() -> set[Path]` — private (single leading underscore).
     - Build argv: `["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process -Filter \"Name='Code.exe'\" | Select-Object -ExpandProperty CommandLine"]`.
     - Call `_subprocess_util.run(argv, timeout=5, check=False)` inside a `try` block that catches `subprocess.TimeoutExpired`, `OSError`, and `FileNotFoundError`. On any exception, return `set()`.
     - On non-zero `result.returncode`, return `set()`.
     - On success, parse `result.stdout` by splitting on `\n` (and stripping `\r` per line), filtering out empty lines after `.strip()`. Convert each surviving line to `Path(line)`. Return the deduplicated set.

  3. `_probe_posix() -> set[Path]` — private.
     - Build argv: `["ps", "-ww", "-A", "-o", "command="]`.
     - Same exception handling and non-zero short-circuit as `_probe_windows`.
     - Parse `result.stdout`: for each non-empty stripped line, take the first whitespace-separated token (`line.split(maxsplit=1)[0]`), compute its basename (`Path(token).name`), and KEEP the line iff that basename starts with the literal string `"code"`. (Plain `code`, `/usr/share/code/code`, `/opt/visual-studio-code/code` all qualify; `/Applications/Visual Studio Code.app/Contents/MacOS/Electron …` is dropped because the first token's basename is `Visual` — see the `posix-uses-ps-linux-only` decision.) Convert each kept line to `Path(line)`. Return the deduplicated set.

  4. `_path_matches_cmdline(launch_path: Path, cmdline: str) -> bool` — module-private but explicitly exported (batch 2 imports it).
     - Resolve `launch_path` via `launch_path.resolve()` and convert to string `s`.
     - Convert `cmdline` to a string via `str(cmdline)` (callers may pass `Path` objects from `find_open_vscode_paths()`'s return set).
     - On Windows (`os.name == "nt"`) lowercase both `s` and the cmdline haystack before all comparisons; on POSIX leave both as-is.
     - Define `boundaries = {"", " ", "\t", "\"", "'"}` (the empty string represents start-of-string and end-of-string).
     - For each `needle` in the iterable `(s, s + os.sep)`: scan the haystack with `hay.find(needle, idx)` in a loop. For each occurrence, check `left = hay[idx-1] if idx > 0 else ""` and `right = hay[idx+len(needle)] if idx+len(needle) < len(hay) else ""`. Return True iff `left in boundaries and right in boundaries`. If no occurrence in either iteration satisfies the boundary check, return False.

  Module docstring at top must summarise the public API in the same style as other `_*.py` helpers under `plugins/mill/scripts/` — list the two exported names with one-line descriptions. No `if __name__ == "__main__":` block.

- **Commit:** `feat(mill): add _vscode_processes helper for open-window detection`

### Card 2: write `test-vscode-processes.py`

- **Context:**
  - `plugins/mill/unit_tests/test-millpy-vscode.py`
  - `plugins/mill/unit_tests/run-all.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_vscode_processes.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-vscode-processes.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-vscode-processes.py` containing a `main() -> int` function called from `if __name__ == "__main__": sys.exit(main())`. Use the same `sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))` bootstrap as `test-millpy-vscode.py`. Import `_vscode_processes` directly (its filename has no hyphen, so plain `import _vscode_processes` works). Each test is a sub-block inside `main()` that prints `PASS:` / `FAIL:` and increments an `errors` counter on failure; `main()` returns `1` on any failure, `0` otherwise.

  Patch target throughout: `_vscode_processes._subprocess_util.run`. Use `unittest.mock.patch` and `subprocess.CompletedProcess` (with `returncode`, `stdout`, `stderr`, `args`) for canned-success returns, or `side_effect=<exception>` for failure modes. On Windows-only assertions, additionally patch `_vscode_processes.os.name` to `"nt"`.

  Implement these test cases (one per bullet — each runs as an independent block in `main()`):

  - **windows_parser_basic**: patch `os.name="nt"`; `_subprocess_util.run` returns rc=0 with stdout `"code C:\\\\wts\\\\foo\r\ncode C:\\\\wts\\\\bar\r\ncode C:\\\\wts\\\\foo\r\n"`. Assert `find_open_vscode_paths()` returns a set whose strings (after `str(p).lower()` because Windows lowercases) contain both `"code c:\\wts\\foo"` and `"code c:\\wts\\bar"` and the duplicate is collapsed (cardinality 2).
  - **windows_parser_quoted_paths**: patch `os.name="nt"`; stdout `'"C:\\\\Program Files\\\\Microsoft VS Code\\\\Code.exe" "C:\\\\wts\\\\foo bar"\r\n'`. Assert the cmdline is preserved verbatim in the returned set (one element, equal to that string after Path-resolve coercion).
  - **windows_parser_empty_output**: patch `os.name="nt"`; stdout `""`. Assert `find_open_vscode_paths()` returns `set()`.
  - **posix_parser_basic**: patch `os.name="posix"`; stdout `"/usr/bin/code /home/u/wts/foo\nfirefox --headless\n/opt/visual-studio-code/code /home/u/wts/bar\n"`. Assert the returned set contains exactly the two `code …` lines (firefox dropped).
  - **posix_parser_no_code_processes**: patch `os.name="posix"`; stdout `"firefox --headless\n/usr/bin/python script.py\n"`. Assert empty set.
  - **probe_subprocess_nonzero_exit**: `_subprocess_util.run` returns `CompletedProcess(returncode=1, stdout="", stderr="boom", args=[])`. Assert empty set.
  - **probe_subprocess_timeout**: `_subprocess_util.run` raises `subprocess.TimeoutExpired(cmd=[], timeout=5)`. Assert empty set.
  - **probe_subprocess_oserror**: `_subprocess_util.run` raises `FileNotFoundError("powershell missing")`. Assert empty set.
  Path-match tests must use real filesystem paths via `tempfile.TemporaryDirectory()` so that `Path.resolve()` produces the same string the haystack contains, on either platform. Construct each test like:

  ```python
  with tempfile.TemporaryDirectory() as tmpdir:
      foo = Path(tmpdir) / "foo"
      foo.mkdir()
      resolved = str(foo.resolve())
      assert _path_matches_cmdline(foo, f"code {resolved}") is True
  ```

  Where the test asserts a sub-path is NOT a match, build the sub-path as `f"{resolved}{os.sep}src"` (or `resolved + os.sep + "src"`). Where the test asserts a prefix-collision is NOT a match, build the haystack as `f"code {resolved}-bar"`. Where the test exercises a quoted path with a space, materialise a directory whose name contains a space (e.g. `Path(tmpdir) / "foo bar"`).

  - **path_match_helper_bare**: build `foo` via tempfile; `_path_matches_cmdline(foo, f"code {resolved}")` returns True.
  - **path_match_helper_trailing_slash**: `_path_matches_cmdline(foo, f"code {resolved}{os.sep}")` returns True.
  - **path_match_helper_subpath_excluded**: `_path_matches_cmdline(foo, f"code {resolved}{os.sep}src")` returns False.
  - **path_match_helper_prefix_collision**: `_path_matches_cmdline(foo, f"code {resolved}-bar")` returns False.
  - **path_match_helper_quoted_path**: build `foo bar` directory via tempfile; `_path_matches_cmdline(foo_bar, f'code "{resolved}"')` returns True.
  - **path_match_helper_end_of_string**: `_path_matches_cmdline(foo, f"code {resolved}")` with no trailing whitespace returns True (asserted by the bare test, but kept as a separate block to lock in end-of-string boundary semantics — verifying that `right_index == len(hay)` triggers the boundary check).
  - **path_match_helper_windows_case_insensitive**: skip on POSIX (`if os.name != "nt": skip with a print and continue`). On Windows, build `foo` via tempfile; compute `upper = str(foo.resolve()).upper()`; assert `_path_matches_cmdline(foo, f"code {upper}")` returns True. The lowercase normalisation inside `_path_matches_cmdline` must match `resolved.lower()` against `upper.lower()`.

  All other parser tests (`windows_parser_*`, `posix_parser_*`, `probe_subprocess_*`) keep the `patch("_vscode_processes.os.name", "nt")` / `"posix"` pattern as planned — only the path-match tests need real-path tempfiles.

  All tests must be platform-independent — they run unchanged on Windows and Linux because every OS-sensitive assertion patches `os.name`. Where `Path("/wts/foo").resolve()` differs across platforms (Windows resolves to a drive-relative path on POSIX-style input, etc.), construct test paths via `tempfile.TemporaryDirectory()` if needed — but for the boundary tests, `os.name="posix"` plus `pathlib.PurePosixPath`-style strings keep the assertions deterministic.

  At the bottom: `if errors: print(f"\n{errors} test(s) FAILED", file=sys.stderr); return 1` then `print("All _vscode_processes unit tests passed.")` and `return 0`. Mirror the structure of `test-millpy-vscode.py`.

- **Commit:** `test(mill): unit tests for _vscode_processes parser and predicate`

## Batch Tests

Verify the batch by running `python plugins/mill/unit_tests/test-vscode-processes.py` standalone or the full suite via `python plugins/mill/unit_tests/run-all.py`. Both must exit 0. The standalone command is in the batch's frontmatter `verify:`; mill-go's batch-verify step uses it.
