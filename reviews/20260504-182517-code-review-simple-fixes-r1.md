# Review: script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo — simple-fixes

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: simple-fixes
date: 2026-05-04
```

## Findings

### [NIT] test_hub_paths_use_cwd_not_git_root omits settings path assertion
**Location:** `plugins/mill/unit_tests/test-millpy-claim.py` (test_hub_paths_use_cwd_not_git_root)
**Issue:** The plan requires the `cwd != git_root` test to assert both the settings file and `mill_dir` are rooted at the hub path. The test verifies `write_active_marker.args[0]` and `write_initial_status.worktree_path`, but `Path.read_text` is stubbed to return `"# Home\n"` which lacks the hub-green pattern, so `_update_hub_vscode_title` returns early — the settings path is never exercised.
**Fix:** Either add the hub-green settings content to the mock so `_vscode.write_settings` fires, then assert `write_settings.call_args.kwargs["target"] == hub_path / ".vscode" / "settings.json"`, or add a separate small test that sets `read_text` to return the green content in the `cwd != git_root` fixture.

## Verdict

APPROVE
One test gap in the cwd-split scenario; all code changes are correct and other test assertions are solid.