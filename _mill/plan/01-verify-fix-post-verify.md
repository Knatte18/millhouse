# Batch: verify-fix-post-verify

```yaml
task: Accumulated bug fixes
batch: verify-fix-post-verify
number: 1
cards: 4
verify: "plugins/mill/.venv/Scripts/python.exe plugins/mill/unit_tests/test-millpy-merge-in-subagent.py"
depends-on: []
```

## Batch Scope

Fix bug 1 (verify-fix-no-report) by re-running the verify command inside `_run_verify_fix` after the sub-agent returns, and update the unit tests so the new `subprocess.run` call count is covered. After this batch, a successful sub-agent run that emits no JSON sentinel will still report `status: success` instead of `stuck/logic/no structured report`. No new dependencies, no external interface, no follow-up batch consumes anything produced here.

## Cards

### Card 1: re-run verify after sub-agent in `_run_verify_fix`

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_implementer_claude.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_run_verify_fix`, after the `_implementer_claude.run(...)` call returns `output` and before the existing `return _forward_output(output, project_root)`, insert a post-sub-agent re-verification step:
  - Call `subprocess.run(args.cmd, shell=True, capture_output=True, text=True, cwd=project_root)` (mirroring the initial verify call shape on lines 213-219).
  - If the returncode is `0`: resolve HEAD via `_subprocess_util.run(["git", "rev-parse", "HEAD"], cwd=project_root)`, take `.stdout.strip()` if returncode `== 0` else `""`, then `print(json.dumps({"status": "success", "commit_sha": sha}))` and `return 0`.
  - If the returncode is non-zero: fall through to the existing `return _forward_output(output, project_root)` line (do not delete it; only the success short-circuit is new).
  - Do not change `_run_conflicts`. Do not move the `LLMError`-handler — the post-verify step runs after the `try`/`except` block has succeeded. Do not add new imports (`subprocess`, `json`, `_subprocess_util` are already imported).
  - Stdout from the new success path must be ASCII only.
- **Commit:** `fix(merge-in-subagent): re-verify after sub-agent in verify-fix mode`

### Card 2: update `test_6` for post-verify success path

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Modify `test_6_verify_fix_failure_subagent_success` (currently at lines 195-238):
  - Replace the `subprocess.run` patch from `return_value=<single fail>` to `side_effect=[<fail>, <success>]` where `<fail>` is `subprocess.CompletedProcess(args=[], returncode=1, stdout="FAILED test_foo", stderr="")` and `<success>` is `subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")`.
  - Keep the `_subprocess_util.run` side_effect list as `[git-diff-result, git-rev-parse-result]` — same length, but the second entry is now consumed by the post-verify success path's `git rev-parse HEAD` call instead of by `_forward_output`. Update the inline `# call ...` comment above the patches to describe the new call ordering (initial verify, post-verify, git diff for prompt, git rev-parse for post-verify success).
  - Simplify the `_implementer_claude.run` mock `return_value` to `("", "fake-session")` (empty output, no JSON) — after the fix, post-verify short-circuits before `_forward_output`, so the previous `'{"status":"success","commit_sha":"abc"}\n'` return value is discarded. Leaving it in would mask the actual code path under test.
  - Keep the existing assertions (`rc == 0`, `data["status"] == "success"`, and the `mock_render.call_args` checks for `VERIFY_OUTPUT`/`VERIFY_CMD`/`VERIFY_FIX_ROUNDS`) unchanged — these still hold under the new path because the sub-agent is still dispatched (the initial verify still fails, so the prompt is still built and `_render.render` is still called).
- **Commit:** `test(merge-in-subagent): update test_6 for post-verify success`

### Card 3: update `test_7` for post-verify still-failing path

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Modify `test_7_verify_fix_subagent_stuck` (currently at lines 240-276):
  - Replace the `subprocess.run` patch from `return_value=<single fail>` to `side_effect=[<fail>, <fail>]` (two identical `CompletedProcess(returncode=1, ...)` entries — first is the initial verify, second is the post-verify which still fails so the code falls through to `_forward_output`). The `subprocess.run` patch is the one being upgraded from a `return_value` (length-1 implicit) to a `side_effect` list of length 2.
  - Keep `_subprocess_util.run` side_effect = `[<git diff>, <git rev-parse>]` unchanged at its existing 2-entry list — this patch already uses `side_effect`; only its semantics shift, not its size. When the post-verify fails, `_forward_output` is reached and (because the sub-agent emitted a stuck JSON sentinel) it calls `_subprocess_util.run` for `git rev-parse HEAD` to attach `commit_sha` to the stuck verdict.
  - Update the inline `# call ...` comment above the patches to describe the new call ordering (initial verify, post-verify, git diff, git rev-parse for `_forward_output`).
  - Keep the existing assertions (`rc == 0`, `data["status"] == "stuck"`, `data["stuck_type"] == "verify"`) unchanged.
- **Commit:** `test(merge-in-subagent): update test_7 for post-verify still-failing`

### Card 4: add `test_11` for no-JSON sub-agent + post-verify success

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Append a new test method `test_11_verify_fix_failure_subagent_no_json_post_verify_success` to the `TestMillpyMergeInSubagent` class, placed after `test_8_verify_fix_missing_cmd` and before the `# ---- shared ----` divider:
  - Docstring: `"verify-fix mode: verify fails, sub-agent emits no JSON, post-verify passes -> success."`
  - Patch `millpy_merge_in_subagent.subprocess.run` with `side_effect=[<fail>, <success>]` (same shapes as Card 2).
  - Patch `millpy_merge_in_subagent._subprocess_util.run` with `side_effect=[<git diff>, <git rev-parse>]` where both are `CompletedProcess(returncode=0, ...)` — the first for the prompt-building diff, the second for the post-verify success path's HEAD lookup.
  - Patch `millpy_merge_in_subagent._implementer_claude.run` with `return_value=("", "fake")` — empty, non-JSON output. This is the exact case bug 1 documents.
  - Patch `millpy_merge_in_subagent._render.render` with `return_value="rendered"` (a literal context manager is fine; mirrors test_6's pattern).
  - Invoke `self._run_main(["--mode", "verify-fix", "--cmd", "pytest tests/", "--checkpoint", "chk"])`.
  - Assert: `rc == 0`, `json.loads(out.strip())["status"] == "success"`.
- **Commit:** `test(merge-in-subagent): add test_11 for no-JSON + post-verify success`

## Batch Tests

The batch's `verify:` runs `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py` end-to-end (all 10 existing tests + new `test_11`). The suite covers:

- `test_5`: initial verify passes, no sub-agent.
- `test_6` (updated): initial verify fails, sub-agent emits success-JSON, post-verify passes — exercises the new success short-circuit.
- `test_7` (updated): initial verify fails, sub-agent emits stuck-JSON, post-verify still fails — exercises the fall-through to `_forward_output`.
- `test_11` (new): initial verify fails, sub-agent emits no JSON, post-verify passes — exercises the exact bug-1 reproduction (previously stuck/logic, now success).
- Conflicts-mode tests (`test_1`-`test_4`) and shared tests (`test_8`-`test_10`) must continue to pass unchanged.

Run via the batch `verify:` command. No additional manual smoke needed: the bug is fully captured by `test_11`.
