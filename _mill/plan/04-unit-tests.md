# Batch: Unit tests: fix-finalize and review-finalize

```yaml
task: Fix agent-pipeline reliability gaps in finalize/success contract
batch: "'Unit tests: fix-finalize and review-finalize'"
number: 4
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-fix-finalize.py test-review-finalize.py
depends-on: [1, 2]
```

## Batch Scope

This batch adds two new unit test files covering the finalize-path changes from Batches 1 and 2. `test-fix-finalize.py` verifies that `millpy-fix.py` finalize correctly wires `--start-sha` and `--session-id` into `finalize_from_output`. `test-review-finalize.py` verifies that `millpy-review-{code,plan,discussion}.py` finalize no longer calls `prepare()` and accepts `--round`. All tests use `unittest.mock.patch` to bypass config loading, git setup, and plan DAG parsing. Inferred-success behavior is tested via `finalize_from_output` directly (real git fixture) in `test-fix-finalize.py` since that requires actual git state.

## Cards

### Card 8: New test-fix-finalize.py

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-fix-finalize.py`
- **Edits:** none
- **Deletes:** none
- **Requirements:**
  - File structure: `from __future__ import annotations`, `import sys, json, io, contextlib, tempfile, subprocess, importlib.util, unittest.mock` at top. Add the scripts dir to `sys.path` using the same pattern as `test-implementer-common.py`: `HUB = Path(__file__).resolve().parent.parent.parent.parent; sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))`. Import `millpy-fix` using `importlib.util.spec_from_file_location("millpy_fix", HUB / "plugins/mill/scripts/millpy-fix.py")` (hyphenated filename requires importlib). Import `finalize_from_output` from `_implementer_common` directly for the real-git tests.
  - **Shared mock helper:** Create a `_setup_fix_mocks(mock_manager)` helper (or use `unittest.mock.patch` inline) that patches the following in `millpy_fix`'s namespace: `millpy_fix._review_common.load_config` returns a minimal config dict with `paths.reviews_dir = "_mill/reviews/"`, `roles.fixer.model = "haiku"`, `roles.implementer.self_fix_rounds = 2`; `millpy_fix._marker.slug_from_branch` returns `"test-slug"`; `millpy_fix._status.read_full` returns `{"yaml": {"task": "Test", "branch": "test-branch"}, "timeline": []}`; `millpy_fix._status.read_branch` returns `"test-branch"`; `millpy_fix._reviewers.load` and `millpy_fix._reviewers.resolve` return a spec dict `{"model": "claude-haiku-4-5-20251001"}`; `millpy_fix._plan_dag.extract_batch_index` returns `[]`; `millpy_fix._subprocess_util.run` returns a mock with `returncode=0, stdout="", stderr=""` for git config calls.
  - **Test 1 -- arg passthrough with start_sha and session_id:** Using the shared mocks plus patching `millpy_fix.finalize_from_output` with a `MagicMock`, write a temp agent-output file, call `millpy_fix.main(["--scope", "holistic", "--review-file", str(review_file), "--round", "1", "--stage", "finalize", "--agent-output", str(agent_output_file), "--start-sha", "abc123", "--session-id", "sid-xyz"])`. Verify `finalize_from_output` was called once and the keyword args include `start_sha="abc123"` and `session_id="sid-xyz"`.
  - **Test 2 -- no start_sha: start_sha=None passed:** Same setup but omit `--start-sha`. Verify `finalize_from_output` called with `start_sha=None`.
  - **Test 3 -- inferred success end-to-end (real git fixture):** Use `tempfile.TemporaryDirectory()` and the `_setup_fixture` pattern from `test-implementer-common.py` to create a real git repo. Make a new commit after capturing `start_sha`. Write an agent-output file containing only prose (no JSON status). Call `finalize_from_output(agent_output_path, project_root, start_sha=start_sha, session_id="sid-abc")` directly (NOT via the CLI). Capture stdout. Verify the output JSON has `status: "success"`, `inferred: true`, and `session_id: "sid-abc"`.
  - **Test 4 -- no start_sha disables inferred success:** Same real git fixture. No new commit (HEAD == start_sha). Call `finalize_from_output(agent_output_path, project_root, start_sha=None, session_id=None)`. Verify stdout JSON has `status: "stuck"`.
  - `main()` function: `errors = 0; ... return errors`. Print PASS/FAIL per test using `print(f"[PASS] ..." if ok else f"[FAIL] ...")`. Return non-zero if any test failed. Use `sys.exit(main())`.
  - Do NOT use `unittest.TestCase` — follow the same free-function pattern as `test-implementer-common.py`.
  - Use `.scratch/` inside a temp dir for any ephemeral fixture files needed by git tests (no `/tmp/` or `$env:TEMP`). The git fixture can use `tempfile.TemporaryDirectory()` as in `test-implementer-common.py` (that is fine for unit tests).
- **Commit:** `test(pipeline): add test-fix-finalize.py for millpy-fix finalize arg wiring`

### Card 9: New test-review-finalize.py

- **Context:**
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-review-finalize.py`
- **Edits:** none
- **Deletes:** none
- **Requirements:**
  - File structure: same import pattern as Card 8. Import all three CLI modules via `importlib.util.spec_from_file_location`. Names: `millpy_review_code`, `millpy_review_plan`, `millpy_review_discussion`.
  - **Test 1 -- review-code finalize does NOT call prepare():** Patch `millpy_review_code._review_code.prepare` to `raise AssertionError("prepare() must not be called in finalize stage")`. Patch other setup calls to return minimal mocks (config, slug, reviewers). Call `millpy_review_code.main(["--stage", "finalize", "--round", "1", "--agent-output", str(output_file)])` with a temp output file. Verify the call completes without raising `AssertionError`. (It may fail with a different error — e.g., `finalize()` failing on bad mock data — but that is acceptable as long as `prepare()` was not called.)
  - **Test 2 -- review-code finalize: --round required:** Call `millpy_review_code.main(["--stage", "finalize", "--agent-output", str(output_file)])` without `--round`. Verify return code is 1 (error) and `prepare()` is still not called.
  - **Test 3 -- review-plan finalize does NOT call prepare():** Same pattern: patch `millpy_review_plan._review_plan.prepare` to raise, verify no raise on `main(["--stage", "finalize", "--round", "1", "--agent-output", str(output_file)])`.
  - **Test 4 -- review-discussion finalize does NOT call prepare():** Patch `millpy_review_discussion._review_discussion.prepare` to raise, verify no raise on `main(["--stage", "finalize", "--round", "1", "--agent-output", str(output_file)])`.
  - For all three CLI tests, patch the common setup calls (config loading, slug detection, reviewers) to return minimal stubs so the test can reach the finalize branch before any further errors.
  - Follow the same free-function main()-returns-int pattern as `test-implementer-common.py`. Each test is a named sub-function that catches exceptions and returns a boolean.
  - Do NOT test the full review pipeline (that is covered by the existing flow tests).
- **Commit:** `test(pipeline): add test-review-finalize.py for review CLI finalize arg wiring`

## Batch Tests

`verify:` runs the two new test files via `run-all.py --only`. The files are created by this batch, so verify only applies after implementation. Tests are focused on CLI arg wiring and do not invoke any LLM. The shared mock pattern ensures no real config, git, or review backend calls happen in the arg-wiring tests.
