MILL_REVIEW_BEGIN
# Review: Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

Independently re-verified against source: `_config.py` (ENV_REGISTRY lines 46-51, `apply_env_overrides` call at load_config line 291), `_review_discussion.py` (`prepare()` 44-127, reviewer resolution 82-87, `run()` 199-271, reviewer re-resolution 239-241, large-prompt call 242-244), `_review_plan.py` (`prepare()` 321-553, holistic branch 462-553, `run()` 617+, batch resolution 682-683, holistic large-prompt call 897-899), `_reviewers.py` (`resolve()` 369-407, `test_stub` branch 382-383, unknown-name raise 385-387, `tier_rank`'s `_agent_dispatch` import at 500), `_agent_dispatch.py` (`model_to_tier` at 95, raises `ValueError`), `_review_common.py` (`ReviewError` at 101, `maybe_switch_spec_for_large_prompt` 1420-1461 with cluster check 1442-1446, `apply_actual_model_override` regex anchored to `reviewer_model:` only, `finalize_scope`/`write_review_file` field-agnostic), `_render.py` (token regex line 35, `KeyError` raise 103-105), `review-output.schema.md` (field table 44-49, worked example 9-17), `test-review-templates.py` (`test_all_templates_render` 69-81, docstring 1-8), `_reviewer_single.py` (cluster raise at line 43, provider-agnostic `importlib` dispatch), `millpy-review-discussion.py` (no catch-all `except Exception` in prepare/full stages), `millpy-review-plan.py` (`except Exception` catch-all present in prepare/full stages, absent in finalize), and both `mill-config.yaml` files (`plan-review.batch.reviewer: null`/`rounds: 0`, `fallback_reviewer` under `code-review.holistic` in both hub-root and template), plus the three review templates' yaml-block field ordering. Every citation checked matches the cited line(s) exactly; no fabricated or stale claims found.

No new gaps found this round. One minor, non-blocking observation below.

## Findings

### [NOTE] `--reviewer` bypass covers `reviewer: null` but not `rounds: 0`
**Section:** Decisions § reviewer-flag-bypasses-null-disablement
**Issue:** The decision bypasses only a `reviewer: null` disablement (mirroring `--max-rounds` vs. `rounds: 0`); if a scope has a configured reviewer but `rounds: 0`, `--reviewer` alone won't force a round — `--max-rounds` must also be passed, and this composability isn't stated.
**Fix:** One sentence noting `--reviewer` + `--max-rounds` together bypass both disablements would remove the ambiguity, though not blocking since no current config shape hits this case.

## Verdict

APPROVE
Fifth-round re-verification of all source citations finds no discrepancies and no unresolved gaps.
MILL_REVIEW_END
