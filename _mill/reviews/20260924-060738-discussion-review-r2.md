MILL_REVIEW_BEGIN
# Review: Auto-name task sessions <slug>:<phase>

```yaml
duration_s: 27.1
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: /home/knatte/Code/millhouse/wts/session-naming/_mill/discussion.md
date: 2026-09-24
```

## Findings

### [NIT:design] Hub-vs-task detection in millpy-session-tasks.py unspecified
**Section:** Stale config after spawn **Issue:** `_marker.slug_from_branch(git_root, wiki_path, cfg)` needs wiki_path and raises MarkerError on a non-task branch (e.g. hub on main); the discussion does not say how the script decides hub vs task worktree or handles that error. **Fix:** Plan should state the detection rule (catch MarkerError, or check branch prefix) and the failure output.

### [NIT:scope] Child config.local.yaml not covered
**Section:** Config shape **Issue:** spawn renders from the parent's merged config; a child's own config.local.yaml overrides only take effect after running the re-render CLI, which is implied but not stated. **Fix:** One sentence noting this in the plan or mill-spawn docs.

### [NIT:scope] Test coverage for SHORTCUT_SCRIPTS addition
**Section:** Testing **Issue:** Adding `millpy-session-tasks` to `_shortcuts.SHORTCUT_SCRIPTS` (verified list at `_shortcuts.py:30`) may affect existing shortcut tests/counts; not listed. **Fix:** Plan should include checking the shortcut tests.

## Verdict

APPROVE
Decisions are made with rationale and rejected alternatives; remaining gaps are minor plan-level details.
MILL_REVIEW_END
