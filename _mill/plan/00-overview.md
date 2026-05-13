# Plan: (A) -- Central safe-rmtree helper + ban direct rmtree

```yaml
task: (A) -- Central safe-rmtree helper + ban direct rmtree
slug: safe-rmtree
approved: false
started: '20260513-075214'
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: safe-rmtree-helper
    file: 01-safe-rmtree-helper.md
    depends-on: []
    verify: PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/test-safe-rmtree.py" && PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/run-all.py"
  - number: 2
    name: migrations-and-gate
    file: 02-migrations-and-gate.md
    depends-on: [1]
    verify: PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/run-all.py"
```

## Shared Decisions

### Decision: helper module signature and exception type

- **Decision:** The helper exposes one public function, `safe_rmtree(path: Path, *, allowed_root: Path, ignore_errors: bool = False) -> None`. Refusal uses `SystemExit("[safe-rmtree] <reason>: <path>")` (matches `_paths` / `_wiki` convention -- library helpers raise `SystemExit` for unrecoverable operator errors). No new exception class is added.
- **Rationale:** Discussion Decisions/"API shape" and Decisions/"Refusal blacklist". `SystemExit` is the established refusal channel in `_paths.resolve_git_root` and `_paths.resolve_main_worktree_root`.
- **Applies to:** all batches

### Decision: blacklist resolution wraps `_paths` failures

- **Decision:** The helper computes its blacklist by calling `_paths.resolve_container_path(allowed_root)`. The call is wrapped in `try: ... except (Exception, SystemExit):` (NOT a bare `except Exception:`). When the call fails or returns a path that does not contain a `wts/` segment matching the millhouse layout, the blacklist is empty and only the `allowed_root` containment check applies. The two-class `except` is load-bearing because `_paths.resolve_main_worktree_root` raises `SystemExit` on non-git paths (e.g. `tempfile.mkdtemp()` directories).
- **Rationale:** Discussion Technical Context/"Exception-type pitfall"; verified against `_paths.py:158-163` and `:228`.
- **Applies to:** all batches

### Decision: junction detection mirrors `_junction.remove`'s existing fallback

- **Decision:** Reparse-point detection lifts the Py-version-aware pattern from `_junction.remove` (`plugins/mill/scripts/_junction.py:170-178`) into a private helper `_is_reparse_point(p: Path) -> bool` inside `_safe_rmtree`. Detection: `os.path.isjunction(p)` when available (Py 3.12+), else `os.lstat(p).st_file_attributes & 0x400` (Py 3.10/3.11). The helper is guarded by `os.name == "nt"`; on POSIX it returns `False`.
- **Rationale:** Discussion Decisions/"Reparse-point detection" and Constraints/"Python 3.10+ support". Avoids duplicating logic; matches the pattern already proven in `_junction.py`.
- **Applies to:** batch 1

### Decision: scandir walks per-entry; never call `entry.is_dir()` without `follow_symlinks=False`

- **Decision:** The pre-rmtree walk uses `os.scandir(path)` and inspects each `DirEntry`. Test order: (1) `entry.is_symlink()` -- removes via `_junction.remove(Path(entry.path))` and skip; (2) on Windows, `_is_reparse_point(entry.path)` -- same removal + skip; (3) otherwise, `entry.is_dir(follow_symlinks=False)` -- recurse. `os.scandir` itself has no `follow_symlinks` parameter; the flag belongs on the per-entry methods. `entry.is_dir()` without the flag would chase a junction and reintroduce the bug.
- **Rationale:** Discussion Decisions/"Reparse-point detection" updated text after Review round 1 NOTE.
- **Applies to:** batch 1

### Decision: tests use `tempfile.TemporaryDirectory()`; no real LLM/git/wiki

- **Decision:** All new and modified unit tests follow the project pattern: `tempfile.TemporaryDirectory()` for filesystem fixtures, the in-file `main()` runner, `assert` + `print("PASS: ...")`. No pytest; no real `git` invocations beyond what existing tests already use; no real wiki clone. Windows-specific junction tests gate on `os.name == "nt"` and `print("SKIP: <reason>")` on POSIX. POSIX symlink tests run on all platforms (symlinks work on Windows too with appropriate permissions; the test gates symlink creation on `os.name != "nt"` to avoid the Windows dev-mode requirement).
- **Rationale:** Project-wide convention (`test-worktree.py`, `test-wiki.py`, etc.); the runner `plugins/mill/unit_tests/run-all.py` discovers `test-*.py` and shells out.
- **Applies to:** all batches

### Decision: ASCII-only stdout/stderr in helper output

- **Decision:** All `print()` strings in `_safe_rmtree.py` and `test-safe-rmtree.py` use ASCII only. Em-dash -> ` -- `, arrow -> ` -> `. Docstrings and comments are exempt per CLAUDE.md `## Conventions worth carrying`.
- **Rationale:** CLAUDE.md hard rule; Windows cp1252 terminals crash on non-ASCII stdout/stderr.
- **Applies to:** all batches

### Decision: no `if __name__ == "__main__":` block in `_safe_rmtree.py`

- **Decision:** The helper is a non-CLI module under `plugins/mill/scripts/` and contains only production code -- no smoke-test `__main__` block. The test file at `plugins/mill/unit_tests/test-safe-rmtree.py` is the sole runnable.
- **Rationale:** CLAUDE.md `## Repo layout pointers`: "Helpers hold only production code; no `if __name__ == '__main__':` smoke-test blocks."
- **Applies to:** batch 1

### Decision: per-card commits via the `git-commit` skill

- **Decision:** Each card's `Commit:` line is the message the implementer passes to the `git-commit` skill. The implementer never invokes `git commit` directly. The `git-commit` skill runs lint and `codeguide-update` per commit.
- **Rationale:** mill-go convention.
- **Applies to:** all batches

## All Files Touched

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
- `plugins/mill/scripts/_safe_rmtree.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-no-direct-rmtree.py`
- `plugins/mill/unit_tests/test-safe-rmtree.py`
- `plugins/mill/unit_tests/test-worktree.py`
