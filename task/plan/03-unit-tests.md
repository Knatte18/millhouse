# Batch: unit-tests

```yaml
task: '29 (A) — mill-merge-in: delegate konflikter og verify-feil til sub-agent'
batch: unit-tests
number: 3
cards: 1
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

Creates the unit test file `test-millpy-merge-in-subagent.py`. All external I/O (git, LLM, path resolution) is mocked; no real git repo or real LLM is needed. This batch can run in parallel with Batch 2 (skill-and-config) since they touch disjoint files. The `verify:` command runs the full unit test suite (`run-all.py`), covering both the new tests and all pre-existing tests — regression guard for any incidental impact from Batch 1.

## Cards

### Card 6: Create test-millpy-merge-in-subagent.py

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Deletes:** none
- **Requirements:** Create `test-millpy-merge-in-subagent.py` following the exact pattern of `test-millpy-implement.py`. Load the CLI via `importlib.util.spec_from_file_location("millpy_merge_in_subagent", ...)`. In `setUp`, use `tempfile.mkdtemp()` (not `.scratch/`) for the fake worktree; create `.millhouse/` with a minimal `config.local.yaml`; create `.millhouse/active.slug.md` containing `test-slug`; create a minimal wiki dir with `config.yaml` containing `merge:\n  verify_fix_rounds: 3`. Patch `_paths.resolve_git_root` → `tmp_path`, `_paths.resolve_wiki_path` → `tmp_path / "wiki"`, `_review_common.load_config` → `{"merge": {"verify_fix_rounds": 3}, "llm": {"implementer_timeout": 1800}}`, `_active.read_slug` → `"test-slug"`. Do NOT patch `subprocess.run` globally in setUp — use per-test `unittest.mock.patch` since subprocess calls differ by test.

  Implement exactly these test methods (all in one `TestMillpyMergeInSubagent` class):

  **conflicts mode:**
  - `test_1_conflicts_success`: patch `millpy_merge_in_subagent._render.render` (return_value `"rendered"`) to capture call_args. Mock `subprocess.run` to return `CompletedProcess(returncode=0, stdout="abc1234\n", stderr="")` for the git-rev-parse call inside `_forward_output`. Mock `_implementer_sonnet.run` to return `('{"status":"success","commit_sha":"abc"}\n', "fake-session")`. Call `main(["--mode", "conflicts", "--files", "a.py", "b.py"])`. Assert rc == 0, stdout JSON has `"status": "success"`. Assert `_render.render` call_args `kwargs["values"]` (or positional `args[1]`) has key `CONFLICTING_FILES` whose value contains `` `a.py` `` and `` `b.py` ``, and key `PROJECT_ROOT`.
  - `test_2_conflicts_stuck`: mock `_implementer_sonnet.run` to return `('{"status":"stuck","stuck_type":"logic","reason":"ambiguous"}\n', "fake")`. Assert rc == 0, stdout JSON has `"status": "stuck"` and `"stuck_type": "logic"`.
  - `test_3_conflicts_no_files`: call `main(["--mode", "conflicts"])`. Assert rc == 1, no JSON on stdout.
  - `test_4_conflicts_llm_error`: mock `_implementer_sonnet.run` to raise `_llm_claude.LLMError("quota")`. Assert rc == 1, stdout JSON has `"status": "stuck"` and `"stuck_type": "transient"`.

  **verify-fix mode:**
  - `test_5_verify_fix_success_no_subagent`: the verify command succeeds on the first run. Mock `subprocess.run` as a side-effect: first call (verify cmd, `shell=True`) → `CompletedProcess(returncode=0, stdout="", stderr="")`, second call (git rev-parse) → `CompletedProcess(returncode=0, stdout="abc1234\n", stderr="")`. Call `main(["--mode", "verify-fix", "--cmd", "pytest tests/", "--checkpoint", "mill-checkpoint-x"])`. Assert rc == 0, stdout JSON has `"status": "success"`. Assert `_implementer_sonnet.run` was NOT called.
  - `test_6_verify_fix_failure_subagent_success`: verify command fails. Patch `millpy_merge_in_subagent._render.render` (return_value `"rendered"`) to capture call_args. Mock `subprocess.run` side-effect: first call (verify) → returncode=1, stdout="FAILED test_foo", stderr=""; second call (git diff) → returncode=0, stdout="diff --git a/f.py..."; third call (git rev-parse in `_forward_output`) → returncode=0, stdout="abc1234\n". Mock `_implementer_sonnet.run` → `('{"status":"success","commit_sha":"abc"}\n', "fake")`. Assert rc == 0, stdout JSON `"status": "success"`. Assert `_render.render` call_args tokens contain `VERIFY_OUTPUT` with "FAILED test_foo", `VERIFY_CMD` == "pytest tests/", `VERIFY_FIX_ROUNDS` == "3".
  - `test_7_verify_fix_subagent_stuck`: verify fails, sub-agent returns stuck. Mock subprocess same as test_6 for verify+diff+rev-parse. Mock `_implementer_sonnet.run` → `('{"status":"stuck","stuck_type":"verify","reason":"still failing"}\n', "fake")`. Assert rc == 0, stdout JSON `"status": "stuck"` and `"stuck_type": "verify"`.
  - `test_8_verify_fix_missing_cmd`: call `main(["--mode", "verify-fix", "--checkpoint", "chk"])`. Assert rc == 1, no JSON on stdout.

  **shared:**
  - `test_9_missing_mode`: argparse raises `SystemExit(2)` when `--mode` is absent. Use `with self.assertRaises(SystemExit) as cm: main([])` then `self.assertEqual(cm.exception.code, 2)`. Do NOT call `_run_main` for this test — the exception must propagate.
  - `test_10_missing_slug`: patch `_active.read_slug` to raise `_active.ActiveError("no slug")`. Call `main(["--mode", "conflicts", "--files", "f.py"])`. Assert rc == 1.

  Use `io.StringIO` + `unittest.mock.patch("sys.stdout", buf)` to capture stdout. Use `addCleanup(os.chdir, original_cwd)` and `addCleanup(shutil.rmtree, ...)` for cleanup.
- **Commit:** `test(merge-in): add unit tests for millpy-merge-in-subagent.py`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` — runs the new tests plus all pre-existing unit tests. All must pass: new tests verify the CLI's conflict and verify-fix paths, and pre-existing tests guard against regressions from Batch 1's new imports.
