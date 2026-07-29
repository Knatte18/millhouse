MILL_REVIEW_BEGIN
# Review: Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] mill-resume never calls health_check() -- #730's own scenario unfixed
**Section:** Decision `wiki-health-check-scope`; Technical context (mill-resume phases)
**Issue:** Rationale claims health_check() is "already... called... from mill-resume," but `plugins/mill/skills/mill-resume/SKILL.md` has zero references to `health_check`/`_client.health_check` (verified via grep) -- Phase 2's candidate list uses `list_tasks_brief` (`OP_LIST_TASKS_BRIEF`), a different op that never touches `_handle_health`'s new fetch/ff-merge logic. The literal #730 repro ("loomyard resume on a fresh machine") is a mill-resume Phase 2 listing, which this fix location does not reach.
**Fix:** Add scope to insert an explicit `health_check()` call into mill-resume (e.g. Phase 1 or immediately before Phase 2's `list_tasks_brief`), or correct the rationale and explain how #730's mill-resume scenario is actually addressed.

### [GAP] health_check()'s bare bool return can't carry the promised "clear error"
**Section:** Decision `health-check-failure-semantics`; Scope > `wiki/_client.py`'s `health_check()`
**Issue:** `wiki/_client.py:585 health_check() -> bool` returns only True/False; the one real dispatch gate, `mill-go/SKILL.md:206-216` and `:594-604`, prints a fixed generic string ("wiki daemon health check failed") on any False, then falls through to "HALT: no config source reachable -- re-run mill-setup if mill-config.yaml is missing" -- a config-remedy message, for what could be a diverged/missing-repo wiki failure. No scope item touches this call site.
**Fix:** Either scope an update to mill-go/SKILL.md's health_check-failure branch to surface the daemon's actual error text (not the mill-setup fallback), or clarify that "surfaces a clear error" is daemon-log-only, not user-facing.

### [GAP] millpy-merge-in-subagent.py: project_root computed twice, cfg loaded once
**Section:** Decision `load-config-fix-mechanics`
**Issue:** Verified against source: `project_root` (line 337, targeted by this decision) is reassigned again at line 357 via `_paths.resolve_active_hub(container_path, slug, cfg=cfg, ...)` -- a slug+cfg-driven resolution, distinct from the cwd-based `resolve_hub_path()` the decision prescribes for line 337. `cfg` (line 345) is loaded exactly once, before this second reassignment, and is never reloaded from the corrected `mill_dir` (line 360) that all later work (verify cwd, conflict/finalize dispatch) actually uses.
**Fix:** Decision should state whether `resolve_hub_path()` (bootstrap) and `resolve_active_hub()` (final) are guaranteed to agree for this script's invocation context, and whether `cfg` needs reloading after the line-357 correction, or why the file needs both resolutions at all.

## Verdict

GAPS_FOUND
health-check call-site coverage (mill-resume, mill-go's error surfacing) and merge-in-subagent's double project_root resolution are unaddressed.
MILL_REVIEW_END
