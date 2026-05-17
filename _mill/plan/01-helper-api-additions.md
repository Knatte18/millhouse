# Batch: helper-api-additions

```yaml
task: 59 (A) -- Small infra fixes batch 8
batch: helper-api-additions
number: 1
cards: 2
verify: "C:/Code/millhouse/wts/millhouse/plugins/mill/.venv/Scripts/python.exe plugins/mill/unit_tests/test-status.py && C:/Code/millhouse/wts/millhouse/plugins/mill/.venv/Scripts/python.exe plugins/mill/unit_tests/test-paths.py"
depends-on: []
```

## Batch Scope

Adds two minimal helper APIs that several callers already expect: `_status.read(status_path)` returning the parsed top YAML block as a dict (#295), and `_paths.resolve_git_root(start=None)` accepting an optional path to operate from (#296). Both are additive; existing call-sites in `_status.py` and `_paths.py` keep working unchanged. Tests are added to the existing `test-status.py` and `test-paths.py` files. No SKILL.md edits in this batch -- documentation (signature lines in mill-plan / mill-start SKILL.md) lives in Batch 5.

External interface this batch exposes:

- `_status.read(status_path: Path) -> dict` -- parses the top fenced-YAML block, returns its keys as a plain dict. Raises `ValueError` on a missing file or malformed YAML.
- `_paths.resolve_git_root(start: Path | None = None) -> Path` -- when `start is None`, behaviour is unchanged (cwd-based `git rev-parse --show-toplevel`). When `start` is provided, runs `git -C <start> rev-parse --show-toplevel`. The existing wiki-cwd safety guards (file lines 121-141) operate on the resolved `repo_root` and need no change.

## Cards

### Card 1: Add `_status.read()`

- **Context:**
  - `plugins/mill/scripts/_yaml_writer.py`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a top-level function `read(status_path: Path) -> dict` to `plugins/mill/scripts/_status.py`. Behaviour: call the existing `_split_fences(text, _YAML_FENCE)` to locate the top fenced-YAML block, `yaml.safe_load` the body, and return the result as a dict. On a missing `status_path` (`not status_path.exists()`), raise `ValueError(f"status file not found: {status_path}")`. On a `yaml.YAMLError`, re-raise as `ValueError(f"Malformed yaml block in {status_path}: {exc}") from exc`. On a missing or unterminated YAML fence, the `ValueError` from `_split_fences` propagates unchanged. Update the module docstring's `Public API:` block (lines 18-33) to add the new entry: `read(status_path) -> dict` between `render_initial(...)` and the existing `read_full(...)` line. Add `read` to the public `from _status import (...)` list in `plugins/mill/unit_tests/test-status.py` (line ~17 imports). Add a new test function `test_read_returns_yaml_block_dict()` that writes a fixture status.md to a `tempfile.TemporaryDirectory`, calls `_status.read(p)`, and asserts the returned dict contains the keys `phase`, `slug`, `branch`, `parent`, `task`, `task_description`, `plan`, with the expected scalar values. Add a second test `test_read_raises_on_missing_file()` that calls `_status.read(Path(tmpdir) / "absent.md")` inside a temp dir and asserts the raised exception is `ValueError` with a message matching `"status file not found"`. Wire both into the existing test runner pattern (top-level `main()` invocation) so `python plugins/mill/unit_tests/test-status.py` exits 0 when both new tests pass and the existing ones still pass.
- **Commit:** `feat(_status): add read() returning parsed top YAML block as dict (#295)`

### Card 2: Add optional `start` argument to `_paths.resolve_git_root()`

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Change the signature of `resolve_git_root` in `plugins/mill/scripts/_paths.py` (current line 115) from `def resolve_git_root() -> Path:` to `def resolve_git_root(start: Path | None = None) -> Path:`. Inside the function, change the subprocess call from `_subprocess_util.run(["git", "rev-parse", "--show-toplevel"])` to: when `start is None`, run the existing command unchanged; when `start is not None`, run `_subprocess_util.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"])`. The wiki-cwd safety guards (lines 121-141) and the rest of the function body (return value, `resolve_wiki_path` cross-check, `samefile` check) stay unchanged. Update the function's docstring (line 116) to: `"""Return the git toplevel for ``start`` (default: current working directory)."""`. Add a new test function in `plugins/mill/unit_tests/test-paths.py` named `test_resolve_git_root_accepts_start_arg()`: inside a `tempfile.TemporaryDirectory`, run `_subprocess_util.run(["git", "init", "--quiet"], cwd=tmpdir)` to create a fresh repo (use the real `_subprocess_util.run`, not the mocked one; resolve via direct subprocess if necessary). Assert that `_paths.resolve_git_root(Path(tmpdir))` returns a `Path` equal to `Path(tmpdir).resolve()`. Cover the no-arg path by adding `test_resolve_git_root_no_args_uses_cwd()` that uses `unittest.mock.patch` on `_subprocess_util.run` to confirm the argv has no `-C` flag when `start is None`. Wire both tests into the existing `main()` runner. If the real `git init` call would conflict with the existing module-level patch of `_subprocess_util.run` (the file uses `MagicMock` patches at module scope -- check `test-paths.py:25-30`), scope the real-subprocess call to a `with patch.stopall()` block or simply use `subprocess.run` directly via `import subprocess` to bypass the mock. The implementer should pick whichever path keeps the existing mocks intact.
- **Commit:** `feat(_paths): accept optional start arg in resolve_git_root() (#296)`

## Batch Tests

`verify` runs the two extended test files: `test-status.py` (existing tests + the two new `read()` tests) and `test-paths.py` (existing tests + the two new `resolve_git_root` argument tests). Both files must exit 0. The existing tests in both files must continue to pass without modification.
