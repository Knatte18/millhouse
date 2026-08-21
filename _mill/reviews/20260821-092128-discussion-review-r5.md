MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: nested-layout config resolution, stale locks, and rollback-target bugs

```yaml
duration_s: 242.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

Cross-checked all six Decisions against source: `mill-merge/SKILL.md` (Step 5 push-failure branches, Step 8/Teardown sequencing, Rollback section, `origin/<parent_branch>` reset already present), `mill-merge-in/SKILL.md` (Entry step 2 liveness, Step 4 verify cwd resolution, Step 5 codeguide invocation), `_parent_branch.py` (`check_liveness` signature/behavior, docstring warning), `_config.py` (`load_config` layer-3/layer-4 line numbers, `warn_unknown_keys`/`deprecated_keys` precedent), `_review_common.py` (`load_config` L2726/L2757/L2772-84, `resolve_path` L452-492/L484, `_core_load_config` import alias), `millpy-review-plan.py` (call site L178, `git_root` in scope at L175), `mill-plan/SKILL.md` L39 and `mill-merge/SKILL.md` L25 (`_config.load_config` call convention), `_implementer_common._run_verify_gate`'s `effective_cwd` fallback order, `codeguide/scripts/resolve.py` (upward-only `_inline_walk`, no `--cwd` flag) and `resolve_scope.py` (`_get_toplevel`/absolute-path emission, confirming cwd-independence), and `test-config.py::test_load_config_local_override_wins`. Every specific claim (line numbers, function signatures, call-site argument order, existing "already fixed" assertions) checked out exactly as stated — no fabricated or stale claims found.

All seven source issues (#904, #900, #899, #880, #879, #863, #862) are mapped to a Decision. Each Decision has rationale, a scoped alternative-rejection, and (where relevant) an explicit interaction check against sibling decisions/routes (e.g. codeguide cwd-pin vs. `resolve_scope.py`'s documented "from the repo root" instruction; early lock-release vs. the `merged`-route and branch-protection-fallback's own Step 8 timing). No undecided items, no TBDs, testing strategy named per touched module with unit-test/integration-test split correctly matched to unit-testable vs. instruction-only changes.

## Verdict

APPROVE
All Decisions are grounded, source claims verify exactly, and no scope/consistency/design gaps found.
MILL_REVIEW_END
