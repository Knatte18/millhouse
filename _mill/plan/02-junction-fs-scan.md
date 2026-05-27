# Batch: junction-fs-scan

```yaml
task: V3 wiki adoption follow-up bugs
batch: junction-fs-scan
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Replaces `_junction.strip_all_in_worktree`'s config-driven loop with a one-level FS scan so legacy worktrees with `.active` (or any other undeclared junction) clean up correctly. Adds a new unit test (`test-junction.py`) covering the FS-scan behaviour. Independent of every other batch — touches only `_junction.py` and a brand-new test file. The DAG places this batch in parallel with Batches 1 and 4.

External interface: `strip_all_in_worktree(worktree_path, junctions_cfg)` signature is preserved. The `junctions_cfg` parameter is retained for backward compatibility but the function no longer iterates it. All existing callers (`_cleanup.py`, `_worktree.remove_safe`, etc.) work unchanged.

Batch-local decisions:

- One-level scan only (`os.scandir(worktree_path)`), not recursive. Junctions in mill-spawned worktrees always live at the worktree root (per `_junction` module docstring and `mill-config.yaml`'s `junctions:` block). Recursion is unnecessary and would slow cleanup of large worktrees.
- The function continues to return a `list[Path]` of stripped link paths so existing callers that inspect the return value (if any) keep working.

## Cards

### Card 6: Replace strip_all_in_worktree config-loop with FS scan

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_junction.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Replace the body of `strip_all_in_worktree(worktree_path: Path, junctions_cfg: dict[str, str]) -> list[Path]` (`_junction.py:279`) with: walk `worktree_path` exactly one level via `os.scandir(str(worktree_path))`, for each entry that is a symlink (`entry.is_symlink()`) OR a junction (use the existing `_is_junction_or_symlink(ep)` helper at `_junction.py:150`), call the existing module-level `remove(ep)` function and append `ep` to a `removed: list[Path]` accumulator. Return `removed`. Use the context-manager form `with os.scandir(str(worktree_path)) as it:` so the scandir handle closes before the function returns.
  - Convert each `entry.path` to `Path(entry.path)` so the return type is `list[Path]` per the existing signature.
  - The `junctions_cfg` parameter is retained for backward compatibility (callers like `_cleanup.py` continue to pass it). Do NOT raise or warn if it is non-empty; just ignore it. Update the function's docstring to reflect the new behaviour: it no longer reads `junctions_cfg`; junctions are discovered by FS scan. Keep the existing docstring's "wiki-wipe incident" rationale paragraph — the safety motivation is unchanged.
  - Guard against `FileNotFoundError`: if `worktree_path` does not exist, return `[]` without scanning (the function is documented as idempotent on missing paths, and the existing config-loop happened to satisfy this trivially because each `remove` was idempotent; the scandir version must replicate that property).
- **Commit:** `fix(junction): strip junctions via FS scan to handle legacy .active links (#385)`

### Card 7: Create test-junction.py covering FS-scan stripping

- **Context:**
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/unit_tests/test-wiki-daemon.py`
  - `plugins/mill/unit_tests/test-safe-rmtree.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-junction.py`
- **Deletes:** none
- **Requirements:**
  - Create a new `test-junction.py` in `plugins/mill/unit_tests/`. Follow the `main()` + `ok()` / `fail()` style used by `test-wiki-daemon.py`. Module docstring: one paragraph stating it covers `_junction.strip_all_in_worktree` FS-scan behaviour added for #385.
  - Standard preamble (mirror `test-safe-rmtree.py`):
    ```python
    HUB = Path(__file__).resolve().parent.parent.parent.parent
    sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))
    import _junction
    import _safe_rmtree
    ```
  - Add `if __name__ == "__main__": sys.exit(main())` at the bottom matching the convention.
  - Test cases:
    1. **strips-undeclared-junction case** — `tempfile.mkdtemp()`, then create a real directory `<tmp>/target` plus a junction/symlink `<tmp>/wt/.active -> <tmp>/target` via `_junction.create`. Call `strip_all_in_worktree(<tmp>/wt, junctions_cfg={})` (deliberately empty config). Assert the return value contains the `.active` path AND the `.active` junction no longer exists (`(<tmp>/wt/.active).exists() is False` AND `_junction._is_junction_or_symlink(<tmp>/wt/.active) is False`) AND `<tmp>/target` still exists (junction removal does not follow the target).
    2. **multiple-junctions case** — create `.wiki` and `.active` and `.portals` junctions, all pointing to distinct targets, all at the worktree root. Call with `junctions_cfg={}`. Assert all three are stripped and the return value contains all three paths.
    3. **non-junction-untouched case** — create a regular directory `<tmp>/wt/_mill/` (not a junction) and a regular file `<tmp>/wt/CLAUDE.md`. Also create one junction `<tmp>/wt/.wiki -> <tmp>/target`. Call with `junctions_cfg={}`. Assert the regular dir and file are NOT removed (they still exist) and the junction IS removed.
    4. **missing-worktree case** — call `strip_all_in_worktree(<tmp>/does-not-exist, {})`. Assert it returns `[]` and does not raise.
  - Use `_safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)` (already imported pattern; copy from `test-safe-rmtree.py`) for cleanup. Do NOT use bare `shutil.rmtree`.
- **Commit:** `test(junction): cover strip_all_in_worktree FS-scan behaviour (#385)`

## Batch Tests

Batch-level `verify:` runs the full unit-test suite. The new `test-junction.py` is auto-discovered by `run-all.py` (it globs `test-*.py`). The existing `test-no-direct-rmtree.py` allowlist gate continues to pass because the new file uses `_safe_rmtree.safe_rmtree`, not raw `shutil.rmtree`.
