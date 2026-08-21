MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: nested-layout config resolution, stale locks, and rollback-target bugs

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5, self-assessed)
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Findings

### [BLOCKING:design] config-local-yaml-caller-alignment fix misses `resolve_path`'s own `load_config` reload
**Section:** Decisions / config-local-yaml-caller-alignment (#900)
**Issue:** The fix patches only `millpy-review-plan.py`'s top-level `load_config(project_root, mill_dir)` call (line 178) to add `git_root=git_root`. But that same script's `run`/`prepare`/`finalize` flow (`_review_plan.py:421-422, 801-802`, and `millpy-review-plan.py:207,270,314`) repeatedly calls `_review_common.resolve_path(...)`, which internally does its own `cfg = load_config(hub_dir, hub_dir / ".millhouse")` (`_review_common.py:484`) — hub-anchored, never touched by this decision. `resolve_path`'s `cfg` feeds `_paths.resolve_active_hub`'s `cfg.get("hub_relative_path", ".")` lookup (confirmed via source read, `_paths.py:474`) — the exact value that diverges between hub- and git-root-anchored config loads in a nested-hub layout. So `plan_dir`/`reviews_dir` resolution inside the very script #900 reports can still resolve against the wrong hub after this "fix" lands.
**Fix:** Either thread `git_root` through `resolve_path` too (with the same additive, opt-in pattern), or add an explicit Decision note explaining why `resolve_path`'s internal reload is safe to leave hub-anchored despite feeding the same `hub_relative_path` divergence this task exists to close.

**Additional grounding — enumeration is undercounted:** the "~9 other call sites" list (Technical context, `_review_common.py` bullet) omits at least three more real `_review_common.load_config` callers confirmed via source read: `millpy-review-code.py:159`, `millpy-validate-plan.py:48`, `millpy-review-discussion.py:143` (all import `load_config` from `_review_common` and call the 2-positional form) — plus the `resolve_path` internal call above. This doesn't change the decision's "leave unaudited callers alone" scope call, but it does mean the "confirmed via source read" confidence framing (already corrected once this round for a prior "3 of 4" overclaim) is still short of the mark.

## Verdict

REQUEST_CHANGES
The #900 fix leaves a same-script, same-run config-reload path (`resolve_path`) untouched despite it feeding the identical divergent value.
MILL_REVIEW_END
