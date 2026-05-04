I have enough information to write the review.

# Review: script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: discussion.md
date: 2026-05-04
```

## Verdict

APPROVE — Round-1 GAP (terminal/vscode discovery) fully resolved; all technical claims verified against source; no remaining undecided items.

**Source verification summary:**
- `_paths.py:303` — confirmed reads `git_toplevel / ".millhouse"` (bug real)
- `_config.py:23,42` — confirmed `git_root` parameter and path (bug real)
- `_spawn_core.py:175-184` — confirmed direct read without stub-awareness (bug real)
- `millpy-claim.py:127,168`, `millpy-color.py:80,94`, `millpy-fetch-issues.py:62`, `millpy-spawn.py:155,190,206,214,220`, `millpy-worktree.py:94` — all line numbers accurate
- `_gitignore.py` — `GLOB_ENTRIES` confirmed as the correct home for `**/plugins/*/uv.lock`
- `test-gitignore-phase.py` — file exists at `plugins/mill/unit_tests/test-gitignore-phase.py`
- `millpy-cleanup.py` — confirmed uses `discover_active_worktrees` (line 73) and has secondary direct read at `wt_path / ".millhouse"` (line 102); covered by scope's "same two-step protocol" instruction