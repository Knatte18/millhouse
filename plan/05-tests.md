# Batch: Tests

```yaml
task: 19 (A) — mill-go + scripts infra fixes
batch: Tests
cards: 2
verify: "python plugins/mill/unit_tests/test-millpy-implement.py && python plugins/mill/unit_tests/test-cleanup.py"
depends-on:
  - Implement parser hardening
  - Cleanup guard
```

## Batch Scope

This batch adds unit tests covering the two code changes from earlier batches: the `_forward_output()` regex parser (Batch 02) and the `build_plan()` unmerged-commits guard (Batch 03). Both test files already exist and have established patterns; the implementer adds new test cases to each.

The external interface this batch delivers: both test files are self-contained executables (`python <file>`) that exit 0 on all pass, 1 on any failure. The `verify:` command in the frontmatter runs both.

Batch-local decisions:
- Tests for `_forward_output()` call the function directly on the imported module (`millpy_implement._forward_output(output)`) and capture stdout. This is simpler than going through `main()` for parser-specific scenarios.
- Tests for the cleanup guard add cases to the existing `main()` function in `test-cleanup.py`, following the existing pattern of in-process assertions with `print("PASS ...")` / `assert` / `raise AssertionError`.
- The guard tests mock `mill_cleanup._subprocess_util.run` to return controlled git log output — no real git repo needed.

## Cards

### Card 8: Add _forward_output() regex tests to test-millpy-implement.py

- **Reads:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/scripts/millpy-implement.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new `TestForwardOutput` test class to the existing `test-millpy-implement.py` file. Use `unittest.TestCase`. Each test method calls `millpy_implement._forward_output(output)` directly, capturing stdout via `unittest.mock.patch("sys.stdout", io.StringIO())`.

  Required test scenarios (add as separate test methods named `test_fo_<N>_<description>`):

  1. **Bare JSON on last line** — input has valid flat JSON with `"status"` key as the last non-empty line → the exact JSON string is printed, exit 0.
  2. **JSON in ```json fence** — input is ` ```json\n{"status":"success","commit_sha":"abc"}\n``` ` → the JSON is extracted and printed, exit 0.
  3. **JSON in fence with trailing blank lines** — same as above but with blank lines after the closing fence → still extracts correctly.
  4. **Multiple JSON-like lines, last wins** — input has two lines each containing a `{"status":...}` pattern → the last one is printed.
  5. **No JSON anywhere** — input has no `{...}` pattern → stuck/logic sentinel printed: `{"status": "stuck", "stuck_type": "logic", "reason": "no structured report"}`, exit 0.
  6. **Malformed JSON in fence, valid JSON earlier** — input has `{"status":"broken"` (unclosed brace) last, and `{"status":"success","commit_sha":"x"}` earlier → the earlier valid one is printed (the regex `[^{}]*` won't match unclosed braces; `json.loads` validates the match).

  The new class can be placed after the existing `TestMillpyImplement` class. The `if __name__ == "__main__": unittest.main()` at the end of the file already covers the new class.

- **Commit:** `test(millpy-implement): add _forward_output() regex extraction tests`

### Card 9: Add cleanup guard tests to test-cleanup.py

- **Reads:**
  - `plugins/mill/unit_tests/test-cleanup.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add four new test cases inside the `main()` function in `test-cleanup.py`, before the final `print("All build_plan unit tests passed.")` line. Follow the exact existing pattern: `with tempfile.TemporaryDirectory() as tmp:` block, call `build_plan(...)`, assert on the result, `print("PASS ...")`.

  Required test scenarios:

  1. **phase=done, unmerged commits** — git log returns non-empty stdout (e.g. `"abc1234 some commit\n"`) → the slug is in `to_report` (message includes "unmerged commits") and NOT in `to_remove_done`.
  2. **phase=done, fully merged** — git log returns empty stdout → the slug IS in `to_remove_done`, NOT in `to_report`.
  3. **phase=done, read_parent_branch returns None** — `status.md` has no `parent:` key → slug goes to `to_remove_done` (safe default, guard skipped).
  4. **phase=done, no branch in record** — `active.slug.md` has no `branch:` field → slug goes to `to_remove_done` (guard skipped, `record.branch` is None).

  For scenarios 1 and 2: patch `mill_cleanup._subprocess_util.run` using `unittest.mock.patch` (import `unittest.mock` at the top of `test-cleanup.py` if not already present). The mock should return a `subprocess.CompletedProcess`-like object with `returncode=0`, `stdout=<controlled value>`, `stderr=""`. Use `MagicMock` with attribute assignment or `subprocess.CompletedProcess(args=[], returncode=0, stdout=..., stderr="")`.

  For scenarios 3 and 4: no patching of `_subprocess_util.run` is needed — the guard short-circuits before the git call when `parent_branch` or `record.branch` is None.

  Ensure each test scenario sets up a valid active marker (`_write_active_marker(wt, slug, branch)`) and a `status.md` via `_make_status_md("done", parent="main")` (or without a parent key for scenario 3). For scenario 4, write a minimal active marker without a branch field instead of using `_write_active_marker`.

- **Commit:** `test(cleanup): add build_plan() unmerged-commits guard tests`

## Batch Tests

Run both test files directly:
```
python plugins/mill/unit_tests/test-millpy-implement.py && python plugins/mill/unit_tests/test-cleanup.py
```
Both must exit 0.
