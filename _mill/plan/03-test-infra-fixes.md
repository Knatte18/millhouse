# Batch: test-infra-fixes

```yaml
task: '64 (A) -- Small infra fixes batch 9'
batch: test-infra-fixes
number: 3
cards: 3
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [2]
```

## Batch Scope

Three test-infrastructure fixes that depend on batch 2 being complete. Card 9 adds a
`layout` keyword to `_make_task_worktree` so callers that need container-form path
layout (required for real `resolve_wiki_path` calls) can opt into it without breaking
the ~10 existing tests that use prefix-form. Card 10 fixes `test-review-common.py`:
adds missing FAIL labels to silent `errors += 1` sites, fixes the "missing config ->
ReviewError" test that silently passes due to CLAUDE_PLUGIN_ROOT being set in dev, and
adds delimiter-assertion tests for the `bulk_files` END FILE / END DIFF change from
batch 2. Card 11 adds `rounds=0` APPROVE-stub tests to the three review-flow test files,
covering the `_review_code`, `_review_discussion`, and `_review_plan` changes from batch 2.

## Cards

### Card 9: Add `layout` keyword to `_make_task_worktree` in `_test_helpers.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Find `_make_task_worktree` in `_test_helpers.py`. Add a keyword parameter
  `layout: Literal["prefix", "container"] = "prefix"` (add `Literal` to the `typing`
  import if not already present).

  When `layout == "container"`: set `worktree_path = tmp / "wts" / slug` (create the
  intermediate `wts/` directory as needed).
  When `layout == "prefix"` (default): keep `worktree_path = tmp / "worktree"` (no change
  to existing behaviour).

  The wiki path and all other fixture scaffolding remain unchanged regardless of layout.
  No existing callers need to be modified.
- **Commit:** `feat(test-helpers): add layout keyword to _make_task_worktree`

### Card 10: Fix `test-review-common.py` — FAIL labels, missing-config mock, delimiter tests

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Three changes to `test-review-common.py`:

  **(a) FAIL labels.** Scan every `errors += 1` site where the immediately-preceding
  non-blank line does not contain `print(f"FAIL:`. For each such site, insert a
  `print(f"FAIL: <short test name>: <error detail>", file=sys.stderr)` on the line
  immediately before `errors += 1`. Use the surrounding test context (function name,
  variable names) to write a concise and identifying label. Do not rename or restructure
  any test logic — only add the missing print.

  **(b) Fix "missing config -> ReviewError" test.** Locate the test at around line 533-543:
  ```python
  # load_config: missing config -> ReviewError
  ...
  load_config(tmpdir_path, mill)
  errors += 1
  ```
  Wrap the `load_config(tmpdir_path, mill)` call with:
  ```python
  with unittest.mock.patch(
      "_review_common.resolve_plugin_template_path",
      return_value=Path("/nonexistent/mill-config.yaml"),
  ):
      load_config(tmpdir_path, mill)
  ```
  This ensures the plugin-template fallback is disabled, so the ReviewError path is
  reached even when `CLAUDE_PLUGIN_ROOT` is set in the dev environment. Import
  `unittest.mock` if not already imported.

  **(c) Delimiter tests.** Add new test cases that exercise the `bulk_files` and
  `bulk_files_with_diff` close delimiters added in batch 2:

  ```python
  # bulk_files: END FILE delimiter present
  with tempfile.TemporaryDirectory() as tmpdir:
      p1 = Path(tmpdir) / "a.py"
      p2 = Path(tmpdir) / "b.py"
      p1.write_text("content-a", encoding="utf-8")
      p2.write_text("content-b", encoding="utf-8")
      result = bulk_files([p1, p2])
      assert f"--- END FILE: {p1} ---" in result, f"END FILE missing for p1: {result!r}"
      assert f"--- END FILE: {p2} ---" in result, f"END FILE missing for p2: {result!r}"
      assert result.index(f"--- FILE: {p1}") < result.index(f"--- END FILE: {p1}"), \
          "opener must precede closer for p1"
  print("PASS: bulk_files END FILE delimiters present and ordered")
  ```

  Add a similar test for `bulk_files_with_diff` verifying that FILE entries get
  `--- END FILE: ---` and that (when `start_sha` is `None` or diff is disabled) the
  full-file branch also gets `--- END FILE: ---`. Import `bulk_files` and
  `bulk_files_with_diff` from `_review_common` at the top of the test file if not
  already imported.

  Wrap each new test block in try/except, appending to `failures`, consistent with
  the existing test style.
- **Commit:** `test(review-common): add FAIL labels, fix missing-config mock, add delimiter tests`

### Card 11: Add `rounds=0` APPROVE-stub tests to the three review-flow test files

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add one new test to each file, exercising the rounds=0 early-return path added in
  batch 2. All three tests follow the same pattern: construct a minimal valid config
  with `rounds: 0` for the relevant scope, call `run(...)`, and assert the returned
  `ReviewResult` has `verdict="APPROVE"`, `round=0`, `blocking_count=0`, and no
  `ReviewError` is raised.

  **`test-review-code-flow.py`** — add a test labeled `(rounds=0 holistic)`:
  Build a cfg with `cfg["roles"]["code-review"]["holistic"]["rounds"] = 0`. Call
  `_review_code.run(cfg, slug=..., mill_dir=..., wiki_root=..., project_root=...,
  batch_name=None)` using the existing test fixture helper. Assert `r.verdict == "APPROVE"`,
  `r.round == 0`, `r.blocking_count == 0`.

  **`test-review-discussion-flow.py`** — add a test labeled `(rounds=0)`:
  Build a cfg with `cfg["roles"]["discussion-review"]["holistic"]["rounds"] = 0`. Call
  `_review_discussion.run(cfg, slug=..., mill_dir=..., project_root=..., wiki_root=...)`.
  Assert `r.verdict == "APPROVE"`, `r.round == 0`, `r.blocking_count == 0`.

  **`test-review-plan-flow.py`** — add a test labeled `(rounds=0 holistic via kwarg)`:
  Build a cfg with `cfg["roles"]["plan-review"]["holistic"]["reviewer"] = "test_stub"`,
  `cfg["roles"]["plan-review"]["holistic"]["rounds"] = 3` (non-zero so holistic_spec is
  NOT nulled out by the existing config guard), and
  `cfg["roles"]["plan-review"]["batch"]["reviewer"] = None` (so batch_spec = None, batch
  path is skipped). Call `_review_plan.run(cfg, slug=..., mill_dir=..., wiki_root=...,
  project_root=..., max_rounds=0)`. The kwarg sets `holistic_max_rounds=0`; the guard
  added in Card 8 fires, returns an APPROVE stub without calling the LLM.
  Assert `r.verdict == "APPROVE"` and `r.blocking_count == 0`.

  Follow the existing fixture setup in each test file (worktree + wiki + plan scaffold
  as appropriate). Use the existing stub-reviewer mock pattern so no real LLM is called.
- **Commit:** `test(review-flows): add rounds=0 -> APPROVE stub tests for all three review types`

## Batch Tests

`python plugins/mill/unit_tests/run-all.py` runs the full suite. This batch fixes
pre-existing silent failures in `test-review-common.py` and adds new passing tests;
all tests must exit 0 with no regressions.
