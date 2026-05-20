# Review: Replace git subprocess calls with pygit2

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-20
```

## Findings

### [GAP] Testing section wrong exception for `discover_workdir`
**Section:** Testing → `test-pygit2-util.py`
**Issue:** Line 187 says `discover_workdir` "raises SystemExit on non-repo path", but the API spec (line 85) and exception type contract section (line 157) both state all `_pygit2_util` helpers raise `GitOpsError`, never `SystemExit`. A plan writer will write `pytest.raises(SystemExit)` and the implementation will fail the test.
**Fix:** Change the testing bullet to `raises GitOpsError on non-repo path`.

### [NOTE] `task_data()` refactor leaves two alternatives open
**Section:** Technical context → `_marker.task_data()` double call
**Issue:** Discussion presents two refactor paths ("call `current_branch(git_root)` directly" or "call `open_repo(git_root)` once and pass the repo in") without choosing between them.
**Fix:** Pick one (the simpler `current_branch(git_root)` direct call) so the plan writer isn't left to decide.

## Verdict

GAPS_FOUND
One contradiction in the testing section: `discover_workdir` error type is `GitOpsError` per spec but `SystemExit` per test bullet.