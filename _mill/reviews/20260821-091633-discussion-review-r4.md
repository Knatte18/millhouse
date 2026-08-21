MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: nested-layout config resolution, stale locks, and rollback-target bugs

```yaml
duration_s: 217.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5)
reviewed_file: /home/knatte/Code/millhouse/wts/mill-merge-nested-layout-and-lock-bugs/_mill/discussion.md
date: 2026-08-21
```

## Findings

### [BLOCKING:design] stub-misuse warning fires on legitimate flat-layout overrides
**Section:** Decisions / config-local-yaml-caller-alignment **Issue:** The new `_config.load_config` stub-misuse warning ("any top-level key other than `hub_relative_path`" in the layer-3 file → warn) is unconditional — not gated on `hub_root != worktree_root`. Confirmed via source read of `_config.py` (~L294-301) and `plugins/mill/unit_tests/test-config.py`'s `test_load_config_local_override_wins` (writes `spawn:\n  branch_prefix: local\n` to `wt_root / ".millhouse" / "config.local.yaml"` with `wt_root` passed as both `hub_root` and `worktree_root`, i.e. flat/in-place layout) that the layer-3 path is the *real*, legitimately-multi-key local-override file whenever `hub_root == worktree_root` — the common non-nested case — not a bootstrap stub. **Fix:** Gate the warning to fire only when `worktree_root != hub_root` (or otherwise scope it to the nested-hub bootstrap-stub case mill-spawn actually writes, per `millpy-spawn.py` L273-280), or the fix will spam `[config] warning:` on stderr for essentially every ordinary hub's `spawn:`/`roles:`/`git:` config.local.yaml override.

### [NIT:consistency] stale "3-of-4" wording survives in Q&A log
**Section:** Q&A log, config-load_config entry **Issue:** The Q&A log answer still says "matching the 3-of-4-entry-points-already-do-this convention," but the Decision's own "Enumeration correction" and Rationale explicitly walk this back to "2 confirmed callers... not '3 of 4' as originally claimed here." **Fix:** Update the Q&A log line to match the corrected 2-caller count so a plan writer skimming only the Q&A log doesn't pick up the disproven figure.

## Verdict

REQUEST_CHANGES
One BLOCKING: the stub-misuse warning needs a nested-layout gate to avoid false-positive noise on ordinary config.local.yaml overrides.
MILL_REVIEW_END
