# Batch: unit-tests

```yaml
task: haiku-4-5 implementer reliability (hang + path mangle)
batch: unit-tests
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py test-implementer-common.py test-millpy-implement.py
depends-on: [1, 2]
```

## Batch Scope

Adds unit tests for all code added in batches 1 and 2: `compute_scope_violations` (test-cleanliness.py), scope-violations field in `_forward_output` (test-implementer-common.py), and the brief-size guard in `millpy-implement.py` (test-millpy-implement.py). All existing test cases in the three files must still pass after these additions.

## Cards

### Card 8: Add compute_scope_violations tests to test-cleanliness.py

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/unit_tests/test-cleanliness.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add `compute_scope_violations` to the import line at the top of `test-cleanliness.py`:
  ```python
  from _cleanliness import capture_snapshot, compute_new_dirt, compute_scope_violations
  ```

  Add 4 new test cases to `main()` after the existing cases, using `unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", ...)` to control the returned lines. Follow the existing `print("PASS: ...")` / `failures.append("FAIL: ...")` pattern with try/except around each case.

  **Case CV-1: clean worktree returns []**
  Mock returns `[]`. Assert `compute_scope_violations(Path(tmp)) == []`.
  Print: `"PASS: compute_scope_violations: clean worktree -> []"`

  **Case CV-2: untracked file at root returned**
  Mock returns `["?? plugins_mill_scripts_foo.py"]`. Assert result equals `["plugins_mill_scripts_foo.py"]`.
  Print: `"PASS: compute_scope_violations: untracked at root -> path returned"`

  **Case CV-3: untracked file under _mill/ filtered out**
  Mock returns `["?? _mill/some-scratch.txt"]`. Assert result equals `[]`.
  Print: `"PASS: compute_scope_violations: untracked under _mill/ -> filtered"`

  **Case CV-4: untracked file in subdirectory outside _mill/ returned**
  Mock returns `["?? plugins/mill/scripts/new_file.py"]`. Assert result equals `["plugins/mill/scripts/new_file.py"]`.
  Print: `"PASS: compute_scope_violations: untracked in subdir -> path returned"`

  Each case uses `with tempfile.TemporaryDirectory() as tmp:` for the worktree path argument (the mock ignores the actual path). All 4 cases use `with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=[...]) as _:`. The `failures` list and final error check follow the existing file's pattern.
- **Commit:** `test(_cleanliness): add compute_scope_violations test cases`

### Card 9: Add scope-violations tests to test-implementer-common.py

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add `_cleanliness` to the imports block at the top of the file if not already imported:
  ```python
  import _cleanliness
  ```

  Add 3 new test cases to `main()` after the existing 6 cases (cases 1-5). Each case patches `_cleanliness.compute_scope_violations` using `unittest.mock.patch.object(_cleanliness, "compute_scope_violations", return_value=...)`.

  The helper `_capture_stdout` already exists in the file and can be reused. Because `compute_scope_violations` is called from `_forward_output` inside `_implementer_common`, patch `_implementer_common._cleanliness.compute_scope_violations` (or patch the module attribute directly, consistent with the `_subprocess_util` patching pattern already in the file).

  **Case 6: stuck/logic output + violations -> scope_violations in JSON**
  Setup: real git repo fixture (use `_setup_fixture` helper from the file); pass `start_sha` and `snapshot_path` so the inferred-success check runs; do NOT advance HEAD. Patch `_implementer_common._cleanliness.compute_scope_violations` to return `["plugins_mill_scripts_foo.py"]`. Call `_forward_output("garbage", project_root, start_sha=base_sha, snapshot_path=snapshot_path)`. Assert `data["status"] == "stuck"`, `data["stuck_type"] == "logic"`, `data["scope_violations"] == ["plugins_mill_scripts_foo.py"]`.
  Print: `"PASS: stuck/logic + violations -> scope_violations in JSON"`

  **Case 7: inferred-success scenario + violations -> status downgraded to stuck/logic**
  Setup: real git repo fixture; advance HEAD with an empty commit; clean tracked working tree. Patch `_implementer_common._cleanliness.compute_scope_violations` to return `["bad_file.py"]`. Call `_forward_output("garbage", project_root, start_sha=base_sha, snapshot_path=snapshot_path)`. Assert `data["status"] == "stuck"`, `data["stuck_type"] == "logic"`, `data.get("inferred") is True`, `data["scope_violations"] == ["bad_file.py"]`.
  Print: `"PASS: inferred-success + violations -> stuck/logic with scope_violations"`

  **Case 8: no violations -> output unchanged**
  Setup: same as case 7 (inferred-success scenario). Patch `_implementer_common._cleanliness.compute_scope_violations` to return `[]`. Assert `data["status"] == "success"`, `data.get("inferred") is True`, `"scope_violations" not in data`.
  Print: `"PASS: inferred-success + no violations -> success unchanged"`

  Follow the existing try/except/errors pattern for failure counting.
- **Commit:** `test(_implementer_common): add scope_violations test cases`

### Card 10: Add brief-size guard tests to test-millpy-implement.py

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add 2 new test methods to `TestMillpyImplement` class (after the existing methods):

  **test_11_brief_size_guard_fires:**
  Override `self.mock_load_config.return_value` to include `"max_implementer_prompt_chars": 10` in the `"llm"` key. Patch `millpy_implement._render.render` to return a string of 20 characters (`"x" * 20`). Call `self._run_main(["test-batch"])`. Assert:
  - `rc == 0`
  - `data["status"] == "stuck"`
  - `data["stuck_type"] == "transient"`
  - `"max_implementer_prompt_chars"` is a substring of `data["reason"]`
  - `self.mock_implementer_run` was NOT called (use `mock_run.assert_not_called()` or similar)
  
  Use `unittest.mock.patch.object(millpy_implement._render, "render", return_value="x" * 20)` as a context manager inside the test method. Access `_implementer_claude.run` via `unittest.mock.patch.object(millpy_implement._implementer_claude, "run")`.

  **test_12_brief_size_guard_disabled:**
  Override `self.mock_load_config.return_value` to include `"max_implementer_prompt_chars": 0` in the `"llm"` key (the disabled default). Patch `millpy_implement._render.render` to return a string of 20 characters. Assert `_implementer_claude.run` IS called (the guard did not fire).

  The `mock_load_config.return_value` in setUp has `"llm": {"implementer_timeout": 1800}` — both new tests override this return value locally for their duration (use `self.mock_load_config.return_value = {...}` inside the test method body, scoped to that test).

  All existing `TestMillpyImplement` and `TestForwardOutput` test methods must still pass.
- **Commit:** `test(millpy-implement): add brief-size guard test cases`

## Batch Tests

Verify runs `test-cleanliness.py`, `test-implementer-common.py`, and `test-millpy-implement.py` in full. All 9 existing cleanliness cases + 4 new cases, all 6 existing implementer-common cases + 3 new cases, all 16 existing millpy-implement cases + 2 new cases must pass.
