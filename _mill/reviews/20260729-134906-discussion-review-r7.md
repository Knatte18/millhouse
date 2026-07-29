MILL_REVIEW_BEGIN
# Review: Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

Verified against source, all accurate: `wiki/_client.py:585 health_check()`, `wiki/_server.py:295 _handle_health()` (currently unconditional `{FIELD_OK: True}`), `wiki/_sync.py:156 pull()` and `:180-225 commit_push()`'s `rev-parse --git-dir` validity check, `wiki/_server.py:87 on_start()`/`:469 _ensure_gitignore()`/`:506` warning-log, all six client mutation wrappers' `WikiPushError` raising (spot-checked `set_phase`), `mill-resume/SKILL.md` Phase 1 (line 29-33, zero `health_check` references today, confirming the wiki-health-check-scope / mill-resume-health-check-callsite gap history), Phase 6/7/8 (lines 109/122/130), the Error Conditions table. `mill-go/SKILL.md`'s two identical halt blocks at lines 211/216 and 599/604 confirmed byte-identical, including the unconditional "re-run mill-setup" phrasing the health-check-error-surfacing decision targets. `_paths.py` line numbers for `resolve_hub_path`/`resolve_main_worktree_root`/`resolve_container_path`/`resolve_active_hub` (159/228/289/453) all exact, and `resolve_active_hub`'s docstring confirms the two-tier `hub_relative_path` resolution underpinning cfg-reload-after-active-hub. `_review_common.py:1960 load_config`/`:306 find_active_slug` exact. `_config.py:152 resolve_repo_config_path` and its fallback chain (hub_root -> main worktree -> worktree_root) confirmed, supporting the "fallback masks the bug in the common case" claim. All five `load_config`/`project_root` call sites re-verified line-for-line against current source (`millpy-implement.py:229/236/282/287`, `millpy-fix.py:290/297/326`, `millpy-abandon.py:40-42/53/114`, `millpy-merge-in-subagent.py:337/341/345/357/360`, `millpy-validate-plan.py:38/39/44/45`) — every claimed line number and variable name matches exactly, including the differentiated fix mechanics (3 mechanical swaps vs. `merge-in-subagent`'s two-part fix vs. `validate-plan`'s inverted-mismatch fix). `_plan_validate.py:2001 run()` signature and `:1455` docstring's `project_root` "also doubles as the hub_root" wording confirmed verbatim. `WikiServer(DaemonBase)` at `wiki/_server.py:39` confirms a persistent per-process object, making the health-check-fetch-cadence TTL debounce plan feasible. `WIKI_DAEMON_INPROCESS`/`use_inprocess` in-process test harness convention confirmed present in `unit_tests/`. `integration_tests/test-worktree-sibling-resolution.py` confirms real-git-worktree integration tests are an established pattern in this repo, supporting the mill-resume relocate+scaffold test placement.

No new gaps found this round. Prior-round corrections (health-check callsite, cfg-reload generalized to 4 files, mill-resume-detection-point scoping, merge-in-subagent two-part fix, validate-plan project_root fix) all remain internally consistent and independently verified against current source, not just cross-referenced within the discussion.

## Verdict

APPROVE
All claims re-verified against source; no unresolved gaps found this round.
MILL_REVIEW_END
