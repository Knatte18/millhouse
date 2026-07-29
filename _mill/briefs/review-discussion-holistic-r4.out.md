MILL_REVIEW_BEGIN
# Review: Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: /home/knatte/Code/millhouse/wts/mill-review-dispatch-attribution-gaps/_mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] --reviewer Claude-only rejection: undefined scope for run()
**Section:** Decision `reviewer-flag-validation`; Testing "run()-specific override coverage"
**Issue:** The cluster/non-Claude rejection's rationale is that Agent-mode dispatch is Claude-only (prepare()'s `_agent_dispatch.model_to_tier` envelope call, verified at `millpy-review-discussion.py:140`/`millpy-review-plan.py:188`), but `run()`'s direct-dispatch path never calls `model_to_tier` and `_reviewer_single.run()` already dispatches non-Claude single-provider reviewers (e.g. `g25flash`/`g25pro`, verified in `mill-agents.yaml` + `_reviewer_single.py`'s provider-agnostic `importlib.import_module` path) via ordinary config today; the Testing section's dedicated run()-coverage paragraph requires only kwarg-threading + ReviewerError conversion for `run()`, never mentioning this rejection.
**Fix:** State whether `--reviewer <non-Claude alias> --stage full` must succeed (matching today's config-based capability) or fail like prepare(), and why.

### [GAP] Large-prompt-switch skip Decision text scoped to prepare() only
**Section:** Decision `reviewer-flag-large-prompt-interaction`
**Issue:** The decision's own parenthetical scopes the skip to "(both discussion and plan-holistic prepare())", but `run()` independently calls `maybe_switch_spec_for_large_prompt` too (verified: `_review_discussion.py` lines 242-244, `_review_plan.py` lines 897-899) and neither this decision nor the Testing section's run()-coverage paragraph confirms `run()` also skips it — so `--reviewer X --stage full` on an oversized prompt could still be silently swapped back to `large_prompt.reviewer`, defeating the override in exactly the scenario most likely to need it.
**Fix:** Confirm `run()`'s large-prompt auto-switch call is also skipped when `reviewer_override` is set, or state why `run()` is intentionally excluded.

## Verdict

GAPS_FOUND
Two undecided prepare()-vs-run() scoping questions (Claude-only rejection; large-prompt-switch skip) need explicit resolution.
MILL_REVIEW_END
