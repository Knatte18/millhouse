# Batch: cleanliness-pycache-allowlist

```yaml
task: "mill-go: done-gate halt path and cleanliness-gate recovery are under-documented"
batch: "cleanliness-pycache-allowlist"
number: 6
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanliness.py
depends-on: []
```

## Batch Scope

Extends `_cleanliness.clean_ephemeral_scope_violations`'s fixed allowlist to recognize Python's `.pyc` files and `__pycache__` path components, closing #975: pygit2's `status()` reports untracked files individually (unlike plain `git status --porcelain`'s directory collapsing), so a pytest run inside a sanctioned Python exception directory leaves every individual `.pyc` file as its own scope violation, requiring manual Builder classification on every run today. Independent of every other batch — a standalone file pair (`_cleanliness.py` + its unit test), touched nowhere else in this plan.

## Cards

### Card 10: Extend `clean_ephemeral_scope_violations`'s allowlist for `.pyc`/`__pycache__`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `clean_ephemeral_scope_violations`, the `# Rule 3: fixed allowlist for other known extension-bearing build artifact types` branch currently reads:
  ```python
  else:
      is_allowlisted = (
          basename == "coverage.out"
          or basename.endswith(".test")
          or basename.endswith(".prof")
          or basename.endswith(".cover")
      )
  ```
  Extend the boolean OR-chain with two new clauses: `or basename.endswith(".pyc")` and `or "__pycache__" in violation.split("/")` (the latter checked against `violation`, the full hub-relative path — same variable the function already splits into `basename` at the top of the loop — so a `.pyc` file nested several directories deep under any `__pycache__` component is caught by path-component membership, not just a basename suffix match; a bare `.pyc` file with no `__pycache__` ancestor is still caught by the first new clause alone). Update the function's docstring "Allowlist rules applied in order" list, rule 3 line — currently "Basename matches the fixed allowlist: 'coverage.out', or suffix in {.test, .test.exe, .prof, .cover}." — to also name `.pyc` suffix and `__pycache__` path-component membership. Do not change rule 1 or rule 2's logic, or any other part of the function (removal via `os.remove` with `FileNotFoundError` swallowed already applies uniformly to every allowlisted path — no new removal code path is needed for the two new clauses).
- **Commit:** `feat(cleanliness): allowlist .pyc files and __pycache__ path components`

### Card 11: Add unit tests for the `.pyc`/`__pycache__` allowlist

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add three new numbered cases after the existing `CESV-10` case in `main()`, following the file's established `# CESV-N. clean_ephemeral_scope_violations: ...` / `tempfile.TemporaryDirectory()` + `git init` + mocked `_cleanliness.compute_scope_violations` / `try/except AssertionError` / `try/except Exception` / `PASS`/`FAIL` pattern used by `CESV-1` through `CESV-10` (see `CESV-1`'s exact structure: create the file(s) on disk under `tmp_path`, mock `_cleanliness.compute_scope_violations` to return the hub-relative violation path(s), call `clean_ephemeral_scope_violations(tmp_path, tmp_path)`, assert `removed`/`blocking` and on-disk file existence):
  - **CESV-11:** a `.pyc` file nested under a `__pycache__` directory (e.g. create `tmp_path / "foo" / "__pycache__" / "bar.cpython-311.pyc"`, mocked violation path `"foo/__pycache__/bar.cpython-311.pyc"`) is removed and reported in `removed`, matching #975's real 13-file scenario.
  - **CESV-12:** a bare `.pyc` file with no `__pycache__` ancestor (e.g. `tmp_path / "something.pyc"`, mocked violation path `"something.pyc"`) is removed and reported in `removed` — confirms the `.pyc`-suffix clause works independently of the `__pycache__`-path-component clause.
  - **CESV-13 (regression guard):** a non-pycache, non-`.pyc` Python source file (e.g. `tmp_path / "foo" / "scratch.py"`, mocked violation path `"foo/scratch.py"`) is still reported in `blocking` and NOT removed — confirms the new clauses do not over-broadly allowlist arbitrary Python files, only `.pyc` artifacts and `__pycache__` contents.
  Update the module docstring at the top of `test-cleanliness.py` (if it enumerates covered scenarios) to mention the new `.pyc`/`__pycache__` coverage.
- **Commit:** `test(cleanliness): cover .pyc/__pycache__ allowlist and non-pycache regression guard`

## Batch Tests

`verify:` runs the full `test-cleanliness.py` file (existing `CESV-1` through `CESV-10` plus this batch's new `CESV-11`/`CESV-12`/`CESV-13`) — the whole file is one cohesive unit for `_cleanliness.py`'s cleanup functions, and each case is a small tempdir + mocked-subprocess fixture (no real network I/O), so the unbounded per-file run is appropriately scoped.
