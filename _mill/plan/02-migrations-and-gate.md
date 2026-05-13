# Batch: migrations-and-gate

```yaml
task: (A) -- Central safe-rmtree helper + ban direct rmtree
batch: migrations-and-gate
number: 2
cards: 4
verify: PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/run-all.py"
depends-on: [1]
```

## Batch Scope

Migrate every direct `shutil.rmtree` / `os.removedirs` / `rmdir /s`
callsite in `plugins/mill/` to the new `_safe_rmtree.safe_rmtree`
helper from batch 1, then install a unit-test gate that fails the
suite if any new direct callsite appears. Cards proceed in
dependency order inside the batch: production migration (`_worktree`)
first, then unit-test migrations, then integration-test
migrations, then the gate. The gate is added last because it must
not fail mid-batch -- it goes green only after every callsite has
moved.

Batch-local decision (not in `## Shared Decisions` because it only
applies here): the gate uses **regex `shutil\.rmtree`,
`os\.removedirs`, `rmdir\s+/s`** as content matches across all
`.py` files in `plugins/mill/`, with an explicit
`ALLOWED_FILES: set[str]` whitelist (paths relative to repo root)
containing exactly the files that legitimately reference the banned
patterns in docstrings, log strings, or mock patch targets
(see Card 6). The broad-match-plus-whitelist approach is preferred
over a tighter regex (e.g. `shutil\.rmtree\s*\(`) because it also
catches `addCleanup(shutil.rmtree, ...)` deferred references and
`functools.partial(shutil.rmtree, ...)`-style indirection.

## Cards

### Card 3: Migrate `_worktree.remove_safe`'s rmtree fallback

- **Context:**
  - `plugins/mill/scripts/_safe_rmtree.py`
  - `plugins/mill/scripts/_junction.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/mill/scripts/_worktree.py`: add `import _safe_rmtree` to the top-level imports (alongside the existing `import _subprocess_util`).
  - Replace the `shutil.rmtree(str(path), ignore_errors=False)` call inside `remove_safe`'s long-path / not-a-working-tree fallback (currently at `plugins/mill/scripts/_worktree.py:267`) with `_safe_rmtree.safe_rmtree(path, allowed_root=path)`. The surrounding `try: ... except PermissionError as exc: raise WorktreeLockedError(...) from exc` block stays unchanged -- `_safe_rmtree.safe_rmtree` lets `PermissionError` from the inner `shutil.rmtree` propagate when `ignore_errors=False` (the default), so the existing catch still fires.
  - Update the in-file comments and docstrings in `_worktree.py` that reference `shutil.rmtree` by name so they reference `_safe_rmtree.safe_rmtree` (or `_safe_rmtree` for short) instead. Locations to update (verify current line numbers when editing; the descriptions below describe the text not the line number): the `remove_safe` docstring paragraph mentioning "`shutil.rmtree`" as the fallback (the "``shutil.rmtree`` -- safe NOW because junctions are already gone --" sentence and the "``shutil.rmtree(ignore_errors=...)`` decision" sentence), the inline `# Long-path / not-a-working-tree fallback. Junctions are stripped, so shutil.rmtree is safe.` comment, and the `[worktree] remove_safe: git failed; falling back to shutil.rmtree (junctions already stripped)` log string. After editing, the source of `_worktree.py` must contain zero matches for the regex `shutil\.rmtree` (verifiable via `grep -E 'shutil\.rmtree' plugins/mill/scripts/_worktree.py`). The `import shutil` line stays because `shutil.copytree` / `shutil.copy2` are still used in `copy_millhouse`.
  - In `plugins/mill/scripts/millpy-cleanup.py`: the comment inside `_apply_worktree_record` currently reads "remove_safe strips all junctions before removal and falls back to shutil.rmtree on long-path failures (junctions-stripped state makes that fallback safe). See GitHub issue #100." (currently at `:405`). Rewrite as "remove_safe strips all junctions before removal and falls back to `_safe_rmtree.safe_rmtree` on long-path failures (junctions-stripped state makes that fallback safe). See GitHub issue #100." Result: zero `shutil\.rmtree` matches in `millpy-cleanup.py`.
  - In `plugins/mill/unit_tests/test-worktree.py`: two source changes are required, both affecting the three tests that exercise `remove_safe`'s rmtree fallback (currently at `:185-202`, `:227-242`, `:244-261`).
    - **Change A: patch-target rename.** Update every `patch("_worktree.shutil.rmtree", side_effect=PermissionError("locked"))` call to `patch("_safe_rmtree.shutil.rmtree", side_effect=PermissionError("locked"))`. There are two such patches (currently at `:196` and `:255`). After the edit, `_worktree.remove_safe` calls `_safe_rmtree.safe_rmtree` which internally calls `shutil.rmtree` -- patching `_safe_rmtree.shutil.rmtree` at module level intercepts that inner call. Add `import _safe_rmtree  # noqa: F401` near the existing imports so the patch target's module is loaded in the test process before the patch is constructed.
    - **Change B: stub out `_blacklist_for` to avoid an extra `_subprocess_util.run` call inside the fallback.** The migrated `safe_rmtree` calls `_blacklist_for(allowed_root)`, which calls `_paths.resolve_container_path(allowed_root)`, which calls `_subprocess_util.run(["git", "rev-parse", "--git-common-dir"])`. The existing tests patch `_worktree._subprocess_util.run` -- because `_subprocess_util` is a single module object shared with `_paths`, that patch is active for the new git call too. Without a fix, the new call either consumes a `side_effect` list entry meant for `git worktree prune` (causing `StopIteration` later when prune runs) or yields a `MagicMock` for `result.stdout` which `_paths.resolve_main_worktree_root` then passes to `Path(...).strip()` (causing `TypeError`). The cleanest fix in the test is to stub the helper that produces the blacklist so no subprocess call is made: wrap each of the three affected tests' `patch(...)` blocks with an additional `with patch("_safe_rmtree._blacklist_for", return_value=[]):` context. The `_blacklist_for` symbol is a module-private helper defined in `_safe_rmtree.py` per batch 1 Card 1; stubbing it to `[]` means `safe_rmtree` proceeds with an empty blacklist (no refusal possible against the tempdir path), which is the correct semantic for these tests -- they exercise `_worktree.remove_safe`'s fallback flow, not the blacklist. After Change B, the three tests' subprocess mock lists do NOT need new entries; the existing `mock_result` / `[mock_result, mock_prune]` shape works as before.
    - Apply Change B to all three tests that reach the fallback (path-exists PermissionError test at `:185-202`; path-exists clean-exit test at `:227-242`; path-exists PermissionError-on-not-a-working-tree test at `:244-261`). The "path absent" variant at `:263+` does not reach `safe_rmtree` (its `if path.exists():` guard skips the call) and does NOT need the `_blacklist_for` patch.
  - Inline comment + assertion messages in `test-worktree.py` that mention "rmtree" by short name (e.g. `"expected path to be removed by rmtree"` at `:241`, the `--- remove_safe raises WorktreeLockedError when shutil.rmtree raises PermissionError (long-path fallback) ---` comment header at `:185`) are NOT a problem for the Card 6 gate -- they will be whitelisted via `test-worktree.py`. No rewording needed in this card; leave them alone.
  - Run the verify command for batch 1 (`test-safe-rmtree.py`) and `test-worktree.py` locally during card execution to confirm both still pass after the migration:
    - `PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/test-worktree.py"`
    - `PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/test-safe-rmtree.py"`
- **Commit:** `refactor(worktree): route rmtree fallback through _safe_rmtree`

### Card 4: Migrate `plugins/mill/unit_tests/` shutil.rmtree callsites

- **Context:**
  - `plugins/mill/scripts/_safe_rmtree.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - The four files contain two different rmtree-call shapes; the migration handles both. For each file, locate every match of `shutil\.rmtree` and apply the appropriate transform:
    - **Shape A: `addCleanup(shutil.rmtree, self.tmp_path, ignore_errors=True)`** -- function-reference deferred call inside a `setUp` / fixture method. Transform to `addCleanup(_safe_rmtree.safe_rmtree, self.tmp_path, allowed_root=self.tmp_path, ignore_errors=True)`. Files using this shape:
      - `test-millpy-implement-holistic.py:106` (one call inside the fixture).
      - `test-millpy-implement.py:95` (one call).
      - `test-millpy-merge-in-subagent.py:36` (one call).
    - **Shape B: `shutil.rmtree(str(tmpdir), ignore_errors=True)`** -- direct call inside a `try: ... finally:` block. Transform to `_safe_rmtree.safe_rmtree(tmpdir, allowed_root=tmpdir, ignore_errors=True)` (drop the redundant `str(...)` cast -- `safe_rmtree` accepts `Path` directly and binds its own internal path objects). Files using this shape:
      - `test-millpy-spawn.py:825` (one call in a `finally` block).
      - `test-millpy-spawn.py:887` (one call in a `finally` block).
      - `test-millpy-spawn.py:1002` (one call in a `finally` block).
  - Add `import _safe_rmtree` at the top of each file, immediately after any existing `import shutil` line. Keep `import shutil` if the file uses other `shutil` functions; remove it if `shutil` is no longer referenced (verify with a regex grep after the edit).
  - For each edited file, confirm zero remaining matches of `shutil\.rmtree` in the file after the edit (use `grep -E 'shutil\.rmtree' <file>`). The files will be exempt from the Card 6 whitelist (they should not appear in `ALLOWED_FILES`).
  - Do not add `noqa` comments; the migration is complete, not exempt.
- **Commit:** `refactor(tests): route unit-test rmtree cleanup through _safe_rmtree`

### Card 5: Migrate `plugins/mill/integration_tests/` shutil.rmtree callsites

- **Context:**
  - `plugins/mill/scripts/_safe_rmtree.py`
  - `plugins/mill/scripts/_junction.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/integration_tests/smoke-llm-claude.py`
  - `plugins/mill/integration_tests/smoke-llm-gemini.py`
  - `plugins/mill/integration_tests/test-abandon.py`
  - `plugins/mill/integration_tests/test-cleanup.py`
  - `plugins/mill/integration_tests/test-go-assets.py`
  - `plugins/mill/integration_tests/test-inspect.py`
  - `plugins/mill/integration_tests/test-merge.py`
  - `plugins/mill/integration_tests/test-plan-assets.py`
  - `plugins/mill/integration_tests/test-review-code.py`
  - `plugins/mill/integration_tests/test-review-discussion.py`
  - `plugins/mill/integration_tests/test-review-plan.py`
  - `plugins/mill/integration_tests/test-spawn.py`
  - `plugins/mill/integration_tests/test-status.py`
  - `plugins/mill/integration_tests/test-wiki-concurrency.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In every edited file, replace `shutil.rmtree(<target>, ignore_errors=True)` with `_safe_rmtree.safe_rmtree(<target>, allowed_root=<target>, ignore_errors=True)`. The `<target>` expression (typically `container`, `scratch`, or `wt`) stays unchanged. Specific lines as currently present in source (verify when editing):
    - `smoke-llm-claude.py:154` -- `shutil.rmtree(tmp, ignore_errors=True)`.
    - `smoke-llm-gemini.py:142` -- `shutil.rmtree(tmp, ignore_errors=True)`.
    - `test-abandon.py:198` -- `shutil.rmtree(container, ignore_errors=True)`.
    - `test-cleanup.py:235` -- `shutil.rmtree(container, ignore_errors=True)`.
    - `test-go-assets.py:306` -- `shutil.rmtree(str(scratch), ignore_errors=True)`.
    - `test-inspect.py:164` -- `shutil.rmtree(str(wiki / "active"), ignore_errors=True)`.
    - `test-inspect.py:193` -- `shutil.rmtree(container, ignore_errors=True)`.
    - `test-merge.py:361` -- `shutil.rmtree(str(container), ignore_errors=True)`.
    - `test-plan-assets.py:261` -- `shutil.rmtree(str(scratch), ignore_errors=True)`.
    - `test-review-discussion.py:85` -- `shutil.rmtree(root, ignore_errors=True)`.
    - `test-review-plan.py:86` -- `shutil.rmtree(root, ignore_errors=True)`.
    - `test-spawn.py:139` -- `shutil.rmtree(str(wt), ignore_errors=True)`.
    - `test-spawn.py:264` -- `shutil.rmtree(str(container), ignore_errors=True)`.
    - `test-status.py:215` -- `shutil.rmtree(container, ignore_errors=True)`.
    - `test-wiki-concurrency.py:128` -- `shutil.rmtree(container, ignore_errors=True)`.
  - `test-review-code.py:183` is special -- the file defines a module-level `_remove_tree(root: Path) -> None` helper at line `:167` that hand-rolls a junction strip + a `shutil.rmtree(root, onerror=_on_error)` call with a custom `_on_error` callback for read-only `.git` files. Replace the entire `_remove_tree` function with a thin wrapper that calls `_safe_rmtree.safe_rmtree(root, allowed_root=root, ignore_errors=True)`, OR delete `_remove_tree` outright and update every caller of `_remove_tree(...)` inside `test-review-code.py` to call `_safe_rmtree.safe_rmtree(<arg>, allowed_root=<arg>, ignore_errors=True)` directly. The custom `_on_error` read-only-handling logic is dropped because `ignore_errors=True` already swallows the underlying `PermissionError` from read-only `.git` object files. Preferred form: delete `_remove_tree` entirely (it becomes a one-liner that does not earn its name); update callers. Either form is acceptable as long as the call ends up routed through `_safe_rmtree.safe_rmtree`.
  - Add `import _safe_rmtree` at the top of each edited file, immediately after the existing `import shutil` line (if present) or in alphabetical position among the imports. Keep `import shutil` only if the file uses other `shutil` functions; the integration tests typically use `shutil.copy`, `shutil.copytree`, etc., so the import stays.
  - For each edited file, confirm zero remaining matches of `shutil\.rmtree` after the edit. None of these files will appear in `ALLOWED_FILES`.
  - The integration tests do not run as part of `run-all.py` (which only discovers `test-*.py` in `unit_tests/`) -- the migration is verified by the Card 6 gate's grep check, not by execution. Sonnet does not need to invoke the integration tests during this card.
- **Commit:** `refactor(integration-tests): route teardown rmtree through _safe_rmtree`

### Card 6: Create `test-no-direct-rmtree.py` gate

- **Context:**
  - `plugins/mill/scripts/_safe_rmtree.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/unit_tests/run-all.py`
  - `plugins/mill/unit_tests/test-worktree.py`
  - `plugins/mill/unit_tests/test-safe-rmtree.py`
  - `_mill/discussion.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-no-direct-rmtree.py`
- **Deletes:** none
- **Requirements:**
  - Module docstring (4-8 lines) explaining: the gate prevents direct `shutil.rmtree` / `os.removedirs` / `rmdir /s` callsites in `plugins/mill/` outside the explicit whitelist, the rationale (wiki-wipe regression guard per GitHub issue #100), and the whitelist mechanism.
  - File structure follows `test-worktree.py`'s pattern: `from __future__ import annotations`, imports (`re`, `sys`, `pathlib.Path`), constants, helper functions, `def main() -> int:` runner, `if __name__ == "__main__": sys.exit(main())` at bottom. Test discovery via `run-all.py` requires the `test-` prefix and a non-zero exit on failure.
  - Module-level constants:
    - `REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent` (matches `test-worktree.py:10` idiom; `plugins/mill/unit_tests/<file>.py` -> `parent` x4 = repo root).
    - `MILL_DIR = REPO_ROOT / "plugins" / "mill"` -- gate scope is `plugins/mill/` only; codeguide and other plugins are explicitly out of scope.
    - `BANNED_PATTERNS: dict[str, str]` -- maps a short name to a regex string. Entries: `"shutil.rmtree": r"shutil\.rmtree"`, `"os.removedirs": r"os\.removedirs"`, `"rmdir /s": r"rmdir\s+/s"`. Match scope is the literal text; the regex is broad (matches docstrings, comments, log strings, function references in `addCleanup(shutil.rmtree, ...)`, mock patch strings) and relies on `ALLOWED_FILES` to exempt legitimate references.
    - `ALLOWED_FILES: set[str]` -- set of repo-relative POSIX-form paths (forward slashes; `pathlib.PurePosixPath`-style strings) for files whose source legitimately contains a banned pattern. Initial contents (exactly these five entries, sorted):
      - `"plugins/mill/scripts/_junction.py"` -- docstring for `strip_all_in_worktree` references "rmdir /s" and "shutil.rmtree" to explain why the helper exists.
      - `"plugins/mill/scripts/_safe_rmtree.py"` -- the helper itself calls `shutil.rmtree(...)` and its docstring references the wrapped function by name.
      - `"plugins/mill/unit_tests/test-no-direct-rmtree.py"` -- this file's source contains the regex strings themselves; it must not match itself.
      - `"plugins/mill/unit_tests/test-safe-rmtree.py"` -- the test patches `_safe_rmtree.shutil.rmtree` and its scenario `print("PASS: ...")` lines reference "shutil.rmtree" by name.
      - `"plugins/mill/unit_tests/test-worktree.py"` -- the migrated patch strings reference `_safe_rmtree.shutil.rmtree`, plus existing assertion-error strings ("expected path to be removed by rmtree") and section-header comments mention "shutil.rmtree" by name.
  - Helper function `_iter_python_files(root: Path) -> Iterable[Path]`: yields every `*.py` under `root` recursively, sorted, excluding any path whose any component starts with `.` (skip `.scratch/`, `.git/`, etc.) and excluding `__pycache__` directories.
  - Helper function `_repo_relative_posix(p: Path) -> str`: returns `p.relative_to(REPO_ROOT).as_posix()` -- normalises to forward slashes for comparison with `ALLOWED_FILES`.
  - `def main() -> int:` body:
    - For each banned-pattern name + regex pair, compile the regex.
    - Iterate `_iter_python_files(MILL_DIR)`. For each file: skip if `_repo_relative_posix(file) in ALLOWED_FILES`. Otherwise, read text with `encoding="utf-8"` and search each compiled regex. Record findings as `(repo_relative_posix_path, pattern_name, line_number, line_text)` tuples. Use `re.compile(...).search` line by line (read file as text, split on `"\n"`, iterate `enumerate(lines, start=1)`).
    - Verify whitelist consistency: for each path in `ALLOWED_FILES`, assert `(REPO_ROOT / path).exists()` -- catches drift where a file is renamed but the whitelist isn't updated.
    - If any findings: print each as `f"FAIL: {file}:{line}: {pattern_name}: {line_text.strip()}"`, then `print(f"FAIL: {N} direct rmtree callsite(s) outside ALLOWED_FILES")` and `return 1`.
    - If no findings: `print("PASS: no direct rmtree callsites in plugins/mill/ outside ALLOWED_FILES")` and `return 0`.
    - If a whitelist file is missing on disk: `print(f"FAIL: whitelist entry not found on disk: {missing}")` and `return 1` (do not silently skip).
  - Edge cases the gate must handle: (1) files with CRLF line endings -- read as text with `encoding="utf-8"` and let `splitlines()` normalise; (2) binary files inadvertently named `.py` -- `UnicodeDecodeError` is allowed to propagate (this is a real defect to report); (3) symlinks/junctions encountered during walk -- skip them via `Path.is_symlink()` check inside `_iter_python_files`.
  - ASCII-only `print()` strings.
- **Commit:** `test(safe-rmtree): add gate banning direct shutil.rmtree in plugins/mill`

## Batch Tests

The batch `verify` runs the entire unit suite via `run-all.py`. The
gate (`test-no-direct-rmtree.py`) is discovered by `run-all.py`'s
existing `test-*.py` discovery and runs as one of the suite's
subprocesses. The suite is green only when:

1. Every existing unit test still passes (no regression from the
   migration -- `test-worktree.py` in particular must still cover
   all of `remove_safe`'s branches with the patch target now
   `_safe_rmtree.shutil.rmtree`).
2. `test-safe-rmtree.py` (from batch 1) passes -- regression guard
   for the helper itself.
3. `test-no-direct-rmtree.py` passes -- proves zero unmigrated
   callsites remain outside `ALLOWED_FILES`.

The integration tests under `plugins/mill/integration_tests/` are
NOT part of the batch verify (they are not discovered by
`run-all.py`). They are verified by Card 6's grep gate (which
inspects source text), not by execution.
