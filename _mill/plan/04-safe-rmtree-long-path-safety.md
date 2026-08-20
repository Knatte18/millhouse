# Batch: safe-rmtree-long-path-safety

```yaml
task: 'millpy-implement --stage baseline: Windows verify-baseline worktree teardown fails (WinError 145 / long paths), leaves orphaned artifacts'
batch: safe-rmtree-long-path-safety
number: 4
cards: 2
verify: null
depends-on: [1]
```

## Batch Scope

Fixes Cluster B's `_safe_rmtree.py` half: `_walk_strip_reparse_points`'s recursive scandir walk and `safe_rmtree`'s `shutil.rmtree` root argument both build their OS-call path strings from a raw `str(path)` today, hitting the same genuine (non-vanished) `MAX_PATH` `FileNotFoundError` misclassification as `_junction.py`'s walker, and then `WinError 145` on the actual `shutil.rmtree` call once a mis-skipped directory turns out to still hold content. This batch switches both call sites to route through batch 1's `_long_path.to_extended()` proactively. Depends only on batch 1 (the helper module); independent of batch 3 (`_junction.py`) — different file, no shared edit target. (`safe_rmtree` calls `_junction.remove()` for entries it strips, but that call's own internal `to_extended` handling — added by batch 3 — is a no-op on POSIX and functionally unchanged for this batch's own callers, so no ordering dependency exists between batch 3 and batch 4.)

## Cards

### Card 7: Apply `_long_path.to_extended` in `_safe_rmtree.py`'s walker scandir and `safe_rmtree`'s `shutil.rmtree` root

- **Context:**
  - `plugins/mill/scripts/_long_path.py`
- **Edits:**
  - `plugins/mill/scripts/_safe_rmtree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add `import _long_path` to `_safe_rmtree.py`'s import block, alongside the existing `import _junction` and `import _paths`.
  - In `_is_reparse_point(p: Path) -> bool`, bind `p = _long_path.to_extended(p)` as the first statement in the function body (immediately after the `if os.name != "nt": return False` guard, so the POSIX no-op path is unaffected), and replace both `str(p)` arguments passed to `os.path.isjunction` and `os.lstat` within this function with `p`. This function is named explicitly by the overview's `proactive-extended-path-prefix` Shared Decision and is called both from `_walk_strip_reparse_points` (the recursive walk) and directly from `safe_rmtree` on the top-level `original` path (the wiki-wipe-incident safety check deciding whether `path` is itself a junction/reparse point) — mirror Card 5's `_is_junction_or_symlink` treatment in `_junction.py` for the same reason: both are structurally parallel "is this a reparse point" probes gated on raw `str(path)` today.
  - In `_walk_strip_reparse_points(root: Path) -> None`, change:
    ```
    try:
        with os.scandir(str(root)) as it:
    ```
    so the `os.scandir` call reads `os.scandir(_long_path.to_extended(root))` in place of `os.scandir(str(root))` — proactively, per the overview's `proactive-extended-path-prefix` Shared Decision. Leave the surrounding `except FileNotFoundError` handlers (both the per-entry one inside the loop and the whole-call one wrapping the `with` block), and their log messages, unchanged — see the overview's `preserve-genuine-vanished-handling` Shared Decision: a `FileNotFoundError` from the extended-path-prefixed call still means a genuine vanished entry and is still logged and skipped exactly as today.
  - In `safe_rmtree(path: Path, *, allowed_root: Path, ignore_errors: bool = False) -> None`, change both `shutil.rmtree` calls:
    ```
        if ignore_errors:
            shutil.rmtree(str(original), ignore_errors=True)
        else:
            shutil.rmtree(str(original), onexc=_onexc_chmod_retry)
    ```
    so both calls pass `_long_path.to_extended(original)` as the root positional argument in place of `str(original)`. This is sufficient to cover every descendant path: `shutil.rmtree` builds each child path string via `os.path.join` on whatever root string it is given, so an extended-prefixed root makes every descendant operation long-path-safe with no per-file change. Do not alter `_onexc_chmod_retry` or the surrounding `try`/`except OSError` block.
- **Commit:** `fix(worktree): apply extended-length path prefix to safe_rmtree's walker and rmtree root`

### Card 8: Add long-path-safety tests to `test-safe-rmtree.py`

- **Context:**
  - `plugins/mill/scripts/_safe_rmtree.py`
  - `plugins/mill/scripts/_long_path.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-safe-rmtree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add five new cases to `test-safe-rmtree.py::main()`, placed after the "top-level safe_rmtree entry-point window: outermost scandir vanishes" case and before the "non-container allowed_root does not crash" case, using this file's existing `# --- <description> ---` comment-banner convention (no lettered case names) and its `with tempfile.TemporaryDirectory() as tmp: tmp_path = Path(tmp); tree_dir = tmp_path / "tree"; tree_dir.mkdir()` setup pattern:
  - **`os.scandir` receives the extended-path form:** patch `_safe_rmtree._long_path.to_extended` with `MagicMock(return_value="LONGPATH-MARKER-SUCCESS")`. Build an empty-iterator context manager the same way the existing "vanished file entry mid-walk" case does (`scandir_cm = MagicMock(); scandir_cm.__enter__ = MagicMock(return_value=iter([])); scandir_cm.__exit__ = MagicMock(return_value=False)`). Patch `_safe_rmtree.os.scandir` with a `side_effect` function that asserts its argument equals `"LONGPATH-MARKER-SUCCESS"` and returns `scandir_cm`. Patch `_safe_rmtree.shutil.rmtree`. Call `safe_rmtree(tree_dir, allowed_root=tree_dir)`. The `side_effect`'s internal assertion is what proves the marker was passed.
  - **Vanished-entry handling still fires when the extended-path scandir call itself raises `FileNotFoundError`:** patch `_safe_rmtree._long_path.to_extended` with `MagicMock(return_value="LONGPATH-MARKER-VANISHED")`. Patch `_safe_rmtree.os.scandir` with a `side_effect` function that asserts its argument equals `"LONGPATH-MARKER-VANISHED"` and then raises `FileNotFoundError("vanished")`. Patch `_safe_rmtree.shutil.rmtree` with a `MagicMock` named e.g. `mock_rmtree`. Call `safe_rmtree(tree_dir, allowed_root=tree_dir)`. Assert `mock_rmtree.assert_called_once()` and that no exception propagated — mirroring the existing "top-level safe_rmtree entry-point window" case's assertion shape, but now tied to the extended-path call site via the marker assertion.
  - **`shutil.rmtree` is invoked with the extended-path-prefixed root string:** patch `_safe_rmtree._long_path.to_extended` with `MagicMock(return_value="LONGPATH-MARKER-RMTREE-ROOT")`. Patch `_safe_rmtree.os.scandir` to return an empty-iterator context manager (same pattern as the first new case, no entries to walk). Patch `_safe_rmtree.shutil.rmtree` with a `MagicMock` named e.g. `mock_rmtree`. Call `safe_rmtree(tree_dir, allowed_root=tree_dir, ignore_errors=True)`. Assert `mock_rmtree.call_args[0][0] == "LONGPATH-MARKER-RMTREE-ROOT"` — the positional root argument equals the marker, not the plain `str(tree_dir)`.
  - **`_is_reparse_point`'s `os.path.isjunction` branch routes through `_long_path.to_extended`:** patch `_safe_rmtree._long_path.to_extended` with `MagicMock(return_value="LONGPATH-MARKER-REPARSE-ISJUNCTION")`. Patch `_safe_rmtree.os.name` to `"nt"` (so the Windows branch of `_is_reparse_point` executes on the POSIX test runner) and patch `_safe_rmtree.os.path.isjunction` with a `side_effect` function that asserts its argument equals `"LONGPATH-MARKER-REPARSE-ISJUNCTION"` and returns `False`. Call `_safe_rmtree._is_reparse_point(tree_dir)` directly (no `safe_rmtree` wrapper call needed — this is a direct unit test of the helper). The `side_effect`'s internal assertion is what proves the marker was passed; also assert the call returns `False` (the mocked `isjunction` result passed through unchanged).
  - **`_is_reparse_point`'s `os.lstat` fallback branch also routes through `_long_path.to_extended`:** patch `_safe_rmtree._long_path.to_extended` with `MagicMock(return_value="LONGPATH-MARKER-REPARSE-LSTAT")`. Patch `_safe_rmtree.os.name` to `"nt"`. Patch `_safe_rmtree.hasattr` with `MagicMock(return_value=False)` — this forces `_is_reparse_point`'s `if hasattr(os.path, "isjunction"):` check to take the `else`/fallback branch unconditionally, regardless of the actual Python version's `os.path.isjunction` availability on the runner (the real `_junction.py`/`_safe_rmtree.py` house style calls the bare builtin `hasattr`, unqualified, so `patch("_safe_rmtree.hasattr", ...)` intercepts it the same way `patch("module.open", ...)` intercepts an unqualified builtin call inside that module). Patch `_safe_rmtree.os.lstat` with a `side_effect` function that asserts its argument equals `"LONGPATH-MARKER-REPARSE-LSTAT"` and returns a `MagicMock(st_file_attributes=0x400)`. Call `_safe_rmtree._is_reparse_point(tree_dir)` directly. Assert the call returns `True` (the `0x400` reparse-point bit set on the mocked `st_file_attributes`) — the `side_effect`'s internal assertion is what proves the marker reached `os.lstat`.
- **Commit:** `test(safe-rmtree): cover extended-length path usage in walker scandir, rmtree root, and both _is_reparse_point branches`

## Batch Tests

`verify:` runs `test-safe-rmtree.py`, covering the file's pre-existing coverage plus the five new cases added by Card 8.
