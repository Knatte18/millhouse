# Batch: long-path-helper

```yaml
task: 'millpy-implement --stage baseline: Windows verify-baseline worktree teardown fails (WinError 145 / long paths), leaves orphaned artifacts'
batch: long-path-helper
number: 1
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Introduces the shared `_long_path.py` helper module (`to_extended(path: Path) -> str`) that batches 3 and 4 both build on to make their scandir/rmtree/junction-removal calls Windows-long-path-safe. This batch is standalone: a pure-function module plus its unit tests, no dependency on any other batch, and no existing call site touched yet. It is root of the DAG alongside batch 2.

## Cards

### Card 1: Add `_long_path.py` extended-length path helper

- **Context:**
  - `plugins/mill/scripts/_junction.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_long_path.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create a new module `_long_path.py` exposing `to_extended(path: Path) -> str`. On non-Windows platforms (`sys.platform != "win32"`), return `str(path)` unchanged. On Windows: if `str(path)` already starts with the extended-length prefix `\\?\`, return it unchanged (idempotent — the function must be safe to call on an already-prefixed string); otherwise, if `str(path)` starts with `\\` (a UNC path, e.g. `\\server\share\x`), return `\\?\UNC\` followed by the remainder of the string after the leading `\\` (e.g. `\\?\UNC\server\share\x`); otherwise (a drive-absolute path, e.g. `C:\foo\bar`), return `\\?\` followed by `str(path)` unchanged (e.g. `\\?\C:\foo\bar`). The function performs no path resolution or validation itself — the caller is responsible for passing an already-resolved absolute path; this is a pure string transform gated only by `sys.platform`. Follow the module-docstring house style used elsewhere in `plugins/mill/scripts/` (a short purpose paragraph plus a "Public API" list, as in `_junction.py`'s module docstring) — module and function bodies otherwise carry no comments per this repo's `mill:code-comments` conventions.
- **Commit:** `feat(worktree): add _long_path.to_extended for Windows extended-length path prefixing`

### Card 2: Add `test-long-path.py` unit tests for `to_extended`

- **Context:**
  - `plugins/mill/scripts/_long_path.py`
  - `plugins/mill/unit_tests/test-junction.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-long-path.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `test-long-path.py` covering `_long_path.to_extended` with these four cases, following `test-junction.py`'s `ok(name)`/`fail(name, exc)` accumulate-and-report structure (a `passed`/`failed` counter, one `try`/`except Exception as exc: fail(...)` block per case, a final pass/fail summary print, and `sys.exit(main())` at module scope) and the same `HUB = Path(__file__).resolve().parent.parent.parent.parent` / `sys.path.insert(0, ...)` import-setup pattern already used by every file in `plugins/mill/unit_tests/`:
  1. **Already-prefixed idempotency:** with `sys.platform` patched to `"win32"` (via `patch("_long_path.sys.platform", "win32")`), `to_extended(Path("\\\\?\\C:\\foo\\bar"))` returns the string `"\\\\?\\C:\\foo\\bar"` unchanged.
  2. **Drive-absolute path:** with `sys.platform` patched to `"win32"`, `to_extended(Path("C:\\foo\\bar"))` returns `"\\\\?\\C:\\foo\\bar"`.
  3. **UNC path:** with `sys.platform` patched to `"win32"`, `to_extended(Path("\\\\server\\share\\x"))` returns `"\\\\?\\UNC\\server\\share\\x"`.
  4. **POSIX no-op:** without any `sys.platform` patch (real OS value, expected non-`win32` in this repo's test environment), `to_extended(Path("/some/posix/path"))` returns `str(path)` unchanged; then, separately in the same case, with `sys.platform` explicitly patched to `"darwin"` (a second non-`win32` value), `to_extended(Path("/some/posix/path"))` still returns `str(path)` unchanged — proving the branch guard is `sys.platform != "win32"`, not an OS-family check, and that mocking to a non-Windows value never triggers the Windows branch.
- **Commit:** `test(worktree): add test-long-path.py for _long_path.to_extended`

## Batch Tests

`verify:` runs `test-long-path.py` directly (a single new file with no filesystem or git dependency — pure string-transform unit tests, all four `to_extended` scenarios covered via `sys.platform` mocking).
