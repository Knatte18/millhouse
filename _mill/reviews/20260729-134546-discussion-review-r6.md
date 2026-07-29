MILL_REVIEW_BEGIN
# Review: Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] cfg-reload fix scoped only to merge-in-subagent, but same pattern exists in 3 other sites
**Section:** load-config-fix-mechanics / merge-in-subagent-cfg-reload
**Issue:** Verified against source: `millpy-implement.py` (cfg loaded line 236 from bootstrap `project_root`=`resolve_hub_path()` at line 229; `project_root` then reassigned via `resolve_active_hub()` at line 282, but `cfg` is read downstream unreloaded at lines 287/325/327/328/337/632). `millpy-fix.py` has the identical shape (cfg loaded line 297, `project_root` reassigned via `resolve_active_hub()` line 326, `cfg` read unreloaded at lines 340/342/343/359/378/628). `millpy-abandon.py` too (cfg loaded line 42 from `hub_dir`=`resolve_hub_path()`; `active_hub` computed via `resolve_active_hub()` line 53; `cfg` read unreloaded at line 114 for branch resolution). This is the exact same "the two resolvers aren't guaranteed to agree in a hub-in-subdirectory layout" risk that merge-in-subagent-cfg-reload explicitly diagnoses and fixes — but that decision, and load-config-fix-mechanics's "3 of the 4 sites need only a call-site argument swap" framing, only address `millpy-merge-in-subagent.py`.
**Fix:** Extend the cfg-reload requirement (or explain why it's unnecessary, with source evidence) to `millpy-implement.py`, `millpy-fix.py`, and `millpy-abandon.py` — each recomputes a more-precise hub root via `resolve_active_hub()` after the bootstrap `load_config` call and uses the stale `cfg` for real hub-config-controlled values (`plan_dir`, `self_fix_rounds`, reviewer/implementer model, timeout, branch resolution) afterward.

### [NOTE] mill-resume Error Conditions table not updated for new Phase 1 branch
**Section:** Scope — mill-resume Phase 1 halt-condition change (mill-resume-detection-point)
**Issue:** `mill-resume/SKILL.md`'s Error Conditions table (lines 163-171) documents the current unconditional "missing `.millhouse/config.local.yaml`" / "missing `.wiki`" → "stop, run mill-setup" rows; Scope doesn't mention updating this table to reflect the new `_mill/status.md`-gated branch.
**Fix:** Add a note in Scope that the Error Conditions table rows for these two conditions get updated alongside the Phase 1 logic change.

## Verdict

GAPS_FOUND
One GAP: cfg-reload fix for the resolve_hub_path/resolve_active_hub divergence risk covers only 1 of 4 affected sites.
MILL_REVIEW_END
