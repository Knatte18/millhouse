# Batch: junction-walker-long-path-safety

```yaml
task: 'millpy-implement --stage baseline: Windows verify-baseline worktree teardown fails (WinError 145 / long paths), leaves orphaned artifacts'
batch: junction-walker-long-path-safety
number: 3
cards: 2
verify: null
depends-on: [1]
```

## Batch Scope

Fixes Cluster B's `_junction.py` half: the `strip_all_in_worktree`/`_walk` recursive scandir walk, `_is_junction_or_symlink`, and `remove()` all build their OS-call path strings from a raw `str(path)` today, which raises `FileNotFoundError` on genuine (non-vanished) entries whose absolute path exceeds Windows' 260-char `MAX_PATH` — a real, existing entry the walker then silently skips, leaving any junction nested under it unstripped. This batch switches every such call site to route through batch 1's `_long_path.to_extended()` proactively. Depends only on batch 1 (the helper module); independent of batch 4 (`_safe_rmtree.py`) — different file, no shared edit target.

## Cards

### Card 5: Apply `_long_path.to_extended` in `_junction.py`'s scandir walk, `_is_junction_or_symlink`, and `remove()`

- **Context:**
  - `plugins/mill/scripts/_long_path.py`
- **Edits:**
  - `plugins/mill/scripts/_junction.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add `import _long_path` to `_junction.py`'s import block, alongside the existing `import _subprocess_util`.
  - In the nested `_walk` function inside `strip_all_in_worktree`, change:
    ```
    def _walk(dir_path: Path) -> None:
        """Recursively walk dir_path, stopping at junctions/symlinks."""
        try:
            entries = list(os.scandir(str(dir_path)))
    ```
    so the `os.scandir` call reads `os.scandir(_long_path.to_extended(dir_path))` in place of `os.scandir(str(dir_path))` — proactively, per the overview's `proactive-extended-path-prefix` Shared Decision, not as a retry inside the existing `except FileNotFoundError` block. Leave the surrounding `except PermissionError` and `except FileNotFoundError` handlers, and their log messages, unchanged — see the overview's `preserve-genuine-vanished-handling` Shared Decision: a `FileNotFoundError` from the extended-path-prefixed call still means a genuine vanished entry and is still logged and skipped exactly as today.
  - In `_is_junction_or_symlink(link_path: Path) -> bool`, bind `p = _long_path.to_extended(link_path)` as the first statement in the function body, and replace every `str(link_path)` argument passed to `os.path.lexists`, `os.path.isjunction`, `os.lstat`, and `os.path.islink` within this function with `p`.
  - In `remove(link_path: Path) -> None`, bind `p = _long_path.to_extended(link_path)` as the first statement in the function body (immediately after the docstring), and replace every `str(link_path)` argument passed to `os.path.lexists`, `os.path.islink`, `os.unlink`, and `os.rmdir` within this function with `p`. Do not change the `_is_junction_or_symlink(link_path)` call inside `remove()` — it keeps passing the `Path` object, not `p`, since `_is_junction_or_symlink` performs its own `to_extended` conversion internally per the previous bullet.
- **Commit:** `fix(worktree): apply extended-length path prefix to junction scandir/removal calls`

### Card 6: Add long-path-safety tests to `test-junction.py`

- **Context:**
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_long_path.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-junction.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add two new cases to `test-junction.py::main()`, placed after case `(h)` ("strip_all_in_worktree entry-point window") and before the final pass/fail summary block, following the file's existing `try: ... ok(name) / except Exception as exc: fail(name, exc)` per-case structure:
  - **Case (i) — extended-path form is what `_walk` actually passes to `os.scandir`:** create a `wt` directory under a `tempfile.mkdtemp()`-backed `tmp_path`. Patch `_junction._long_path.to_extended` with `MagicMock(return_value="LONGPATH-MARKER-SUCCESS")`. Patch `_junction.os.scandir` with a `side_effect` function that asserts its single argument equals `"LONGPATH-MARKER-SUCCESS"` (raising `AssertionError` otherwise) and returns `[]`. Call `_junction.strip_all_in_worktree(wt, junctions_cfg={})`. Assert the call did not raise (the `side_effect`'s internal assertion is what actually proves the marker was passed) and that the result is `[]`.
  - **Case (j) — vanished-entry handling still fires when the extended-path call itself raises `FileNotFoundError`:** same `wt` setup. Patch `_junction._long_path.to_extended` with `MagicMock(return_value="LONGPATH-MARKER-VANISHED")`. Patch `_junction.os.scandir` with a `side_effect` function that asserts its argument equals `"LONGPATH-MARKER-VANISHED"` and then raises `FileNotFoundError("vanished")`. Call `_junction.strip_all_in_worktree(wt, junctions_cfg={})`. Assert it returns `[]` without raising — proving the existing "genuinely vanished" skip-and-log handling still applies once the walk is exercising the extended-path call site, not the raw one.
  Both cases must wrap their body in the file's existing `try`/`finally: _safe_rmtree.safe_rmtree(tmp_path, allowed_root=tmp_path, ignore_errors=True)` cleanup pattern, matching every other case in this file.
- **Commit:** `test(junction): cover extended-length path usage in strip_all_in_worktree's scandir call`

## Batch Tests

`verify:` runs `test-junction.py`, covering the pre-existing cases (a)-(h) plus the two new cases (i)/(j) added by Card 6.
