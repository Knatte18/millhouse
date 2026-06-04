# Batch: implementer-stuck-fields

```yaml
task: Fix millpy-bg EXIT marker and implementer reliability
batch: implementer-stuck-fields
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py
depends-on: []
```

## Batch Scope

Two related changes to `millpy-implement.py` and one to `millpy-fix.py`:
(1) add `commits_made` count to the stuck JSON emitted on `LLMError` timeout so mill-go can
distinguish a clean timeout-after-commits from a true fresh failure; (2) guard the "mill-go:
start batch" git commit in `millpy-implement.py` against re-fire duplication by checking the
last commit message before staging. `millpy-fix.py` gets the same `commits_made` injection
with a `None`-guard for its optional `start_sha`. New test cases in `test-millpy-implement.py`
cover all three behaviours.

## Cards

### Card 3: Add commits_made to stuck JSON on LLMError in millpy-implement.py

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `main()`, in the `except _llm_claude.LLMError as e:` block (currently `print(json.dumps({"status": "stuck", "stuck_type": "transient", "reason": str(e)}))`):
    - Before the `print`, compute `commits_made`: run `_subprocess_util.run(["git", "rev-list", "--count", f"{start_sha}..HEAD"], cwd=project_root)`. If returncode is 0, parse `int(result.stdout.strip())`. Otherwise use 0. `start_sha` is already in scope.
    - Change the `print` to include `"commits_made": commits_made` in the dict: `{"status": "stuck", "stuck_type": "transient", "reason": str(e), "commits_made": commits_made}`.
  - The `return 1` after the print is unchanged.
- **Commit:** `fix(millpy-implement): add commits_made to stuck JSON on LLMError timeout`

### Card 4: Skip duplicate start-batch commit on re-fire in millpy-implement.py

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `main()`, immediately before the `git add` call (the block at `result = _subprocess_util.run(["git", "add", status_path.relative_to(project_root).as_posix(), ...], cwd=project_root)`):
    - Run `last_log = _subprocess_util.run(["git", "log", "-1", "--pretty=%s"], cwd=project_root)`.
    - If `last_log.returncode == 0` AND `last_log.stdout.strip() == f"mill-go: start batch {args.batch_name}"`:
      - Skip the entire `git add` + `git commit` + `git push origin branch` block (all three subprocess calls).
      - Do NOT skip `_status.set_batch_fields`, `_cleanliness.capture_snapshot`, or any preceding code.
      - Continue execution at the `template_path = ...` line (the implementer brief rendering).
    - If `last_log.returncode != 0` or message differs: execute the block normally.
  - The `start_sha` variable (captured earlier via `git rev-parse HEAD`) remains valid on re-fire because HEAD did not change (the first fire crashed before any new commits).
- **Commit:** `fix(millpy-implement): skip duplicate start-batch commit on re-fire`

### Card 5: Add commits_made to stuck JSON on LLMError in millpy-fix.py

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_llm_claude.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `main()`, in the `except _llm_claude.LLMError as e:` block (lines 298-300: `print(json.dumps({"status": "stuck", "stuck_type": stuck_type, "reason": str(e)}))`):
    - Before the `print`, compute `commits_made`:
      - If `start_sha is None`: `commits_made = 0` (no git call).
      - Else: run `_subprocess_util.run(["git", "rev-list", "--count", f"{start_sha}..HEAD"], cwd=project_root)`. Parse int on success, default 0 on failure.
    - Change the `print` to include `"commits_made": commits_made` in the dict alongside the existing `"status"`, `"stuck_type"`, and `"reason"` keys.
  - `project_root = Path.cwd()` is already set at the top of `main()` in `millpy-fix.py`.
- **Commit:** `fix(millpy-fix): add commits_made to stuck JSON on LLMError timeout`

### Card 6: Add commits_made and skip-commit tests to test-millpy-implement.py

- **Context:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_implementer_claude.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Study the existing test fixture/mock setup in the file (how `_subprocess_util.run`, `_implementer_claude.run`, `_status.*`, and `_cleanliness.*` are mocked) before adding cases.
  - Add test `test_commits_made_nonzero_on_llm_error`: mock `_implementer_claude.run` to raise `_llm_claude.LLMError("timeout")`. Mock the git `rev-list --count` call to return `CompletedProcess(args=..., returncode=0, stdout="3\n", stderr="")`. Capture stdout. Assert the JSON output contains `"commits_made": 3` and `"stuck_type": "transient"`.
  - Add test `test_commits_made_zero_on_llm_error_no_commits`: same as above but `rev-list --count` returns `"0\n"`. Assert `"commits_made": 0`.
  - Add test `test_commits_made_zero_on_rev_list_failure`: `rev-list --count` returns returncode=1. Assert `"commits_made": 0`.
  - Add test `test_skip_start_commit_on_refire`: mock `git log -1 --pretty=%s` to return the batch-name message. Assert `git_commit` (or the subprocess call for `git commit`) is NOT invoked. Assert the implementer still launches (i.e., `_implementer_claude.run` IS called).
  - Add test `test_no_skip_start_commit_on_fresh_fire`: mock `git log -1 --pretty=%s` to return a different message. Assert `git_commit` IS invoked once.
  - Use the existing mock infrastructure in the file (look at the `_make_default_run_side_effect` or equivalent helper pattern to route subprocess call mocks by argv prefix).
- **Commit:** `test(millpy-implement): add commits_made and skip-commit test cases`

## Batch Tests

Verify runs `test-millpy-implement.py` which covers both the new `commits_made` field and
the skip-commit guard. The file already mocks all external subprocess calls so no real git or
LLM invocations occur. Verify is scoped to this single file via `--only`.
