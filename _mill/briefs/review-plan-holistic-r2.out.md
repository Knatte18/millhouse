MILL_REVIEW_BEGIN
# Review: Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [BLOCKING] Cards 3/4 omit explicit `spec` assignment in override branch
**Location:** batch discussion-review-cli, Card 3 (`prepare()`) and Card 4 (`run()`)
**Issue:** The `reviewer_override is not None` branch says "resolve it via `resolve_reviewer_override(...)`; set `reviewer_name = reviewer_override`" but never says to assign the return value to `spec`. `prepare()` immediately does `mode = "tool-use" if spec.get("tooluse") else "bulk"` (line 88) and `run()` calls `_reviewer_single.run(spec, prompt_text)` — both need `spec` defined in this branch or it's a `NameError`. Contrast with Cards 6/7 (`_review_plan.py`), which explicitly state `holistic_spec = <the resolved spec>` for the identical situation.
**Fix:** Add `spec = <the resolved spec>` (or equivalent explicit assignment) to Card 3 and Card 4's override-branch requirements, matching Card 6/7's phrasing.

### [BLOCKING] Card 7 / overview Decision 2 misdescribes plan-review's rounds:0 override precedent
**Location:** 00-overview.md `## Shared Decisions` (`--reviewer bypasses a reviewer: null disablement...`), batch plan-review-cli Card 7
**Issue:** The Decision claims "Forcing a round on a rounds: 0 scope still requires `--max-rounds` in addition to `--reviewer`," implying that combo works today (the rationale cites "`--max-rounds 1` already overrides `rounds: 0`" as precedent). For `_review_plan.py::run()`, the gate that sets `holistic_spec = None` (`if holistic_name is None or cfg["roles"]["plan-review"]["holistic"]["rounds"] == 0`) reads the *raw* cfg value, not the max_rounds-overridden `holistic_max_rounds` variable — confirmed by existing Test 22 in `test-review-plan-flow.py`, which only exercises forcing max_rounds *down* to 0 (nonzero cfg rounds + `max_rounds=0` kwarg), never forcing a genuine cfg `rounds: 0` *up*. Card 7 explicitly preserves this raw-cfg check untouched by `reviewer_override`, so `--reviewer X --max-rounds N` on a `rounds: 0` holistic scope still resolves `holistic_spec = None` and silently skips the holistic review — the stated escape hatch does not actually work for this backend.
**Fix:** Either correct the Decision's rationale to note this is a `_review_discussion.py`-only precedent (not true for `_review_plan.py::run()`), or have Card 7 make the step-3 rounds check use the effective `holistic_max_rounds` value so the claimed escape hatch actually functions.

### [BLOCKING] Card 12 Requirements reference `_review_common.py` functions not in Context
**Location:** batch reviewer-self-id-templates, Card 12 (`review-output.schema.md`)
**Issue:** Card 12 has `Context: none`, `Edits: review-output.schema.md` only, but its Requirements ask for a note "distinguishing `reviewer_self_id` ... from `reviewer_model` ... `parse_verdict()` ... `--actual-model`/`apply_actual_model_override()` can rewrite after the fact." Both `parse_verdict()` and `apply_actual_model_override()` are defined in `plugins/mill/scripts/_review_common.py`, which is absent from Context/Edits.
**Fix:** Add `plugins/mill/scripts/_review_common.py` to Card 12's `Context:` list.

## Verdict

REQUEST_CHANGES
Two Context/spec-assignment gaps plus a factually inaccurate rounds:0-override claim in Shared Decisions need fixing.
MILL_REVIEW_END
