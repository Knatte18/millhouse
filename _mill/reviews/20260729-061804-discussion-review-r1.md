MILL_REVIEW_BEGIN
# Review: Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] `--reviewer` validation doesn't handle the `test_stub` special case
**Section:** Decision: reviewer-flag-validation
**Issue:** `_reviewers.resolve()` special-cases `name == "test_stub"` to return `{"type": "single", "provider": "test_stub", "tooluse": False}` — no `model` key at all (`_reviewers.py:382-383`). Calling `_agent_dispatch.model_to_tier(spec.get("model"))` on this spec raises `AttributeError` (or `KeyError` on `spec["model"]`), not the `ValueError` the decision names as the thing "this task must catch" — so `--reviewer test_stub` escapes the new check as a raw traceback instead of the intended clean `ReviewError`/`print_error_envelope`, undermining the exact contract this validation exists to guarantee.
**Fix:** State explicitly how validation treats a resolved spec with a missing/None `model` key (fold into the same rejection as an unrecognized family, or explicitly exempt `test_stub`).

### [GAP] `reviewer_self_id:` template placeholder risks a hard rendering crash
**Section:** Technical context (template edits); Decision: reviewer-self-id-field
**Issue:** `_render.render()` hard-fails with `KeyError` on any unresolved `<UPPERCASE_TOKEN>` (`_TOKEN_RE = <([A-Z][A-Z0-9_]*)>`, `_render.py:35,104-105`). The discussion says no `_review_common.py`/`render_prompt` kwarg change is needed for this field, but never states the new yaml-block example line must use a lowercase, non-token placeholder (like the adjacent `reviewed_file: <artefact reference>`) rather than an uppercase one styled after `reviewer_model: <REVIEWER_MODEL>`. The latter breaks rendering for every discussion/plan-holistic prepare call. The listed unit tests (`apply_actual_model_override`/`write_review_file` round-trip) build raw_text by hand and never call `render_prompt` on the real template, so they would not catch this.
**Fix:** Specify the literal placeholder text for the new line up front (non-uppercase, matching `reviewed_file`/`date` style), removing the ambiguity.

### [NOTE] `fallback_reviewer` misattributed to `roles.code-review.batch`
**Section:** Scope — Out
**Issue:** The discussion cites the existing `fallback_reviewer` key as living under `roles.code-review.batch`. Both `plugins/mill/templates/mill-config.yaml:159-164` and the hub-root `mill-config.yaml:44-53` nest it under `roles.code-review.holistic` instead — `batch` there only has `rounds`/`reviewer`.
**Fix:** Correct the subsection name; doesn't change the "not touched" decision itself.

### [NOTE] `reviewer-self-id-scope` Decision has no `Rejected:` line
**Section:** Decisions — reviewer-self-id-scope
**Issue:** Every other `### Decision:` block in this discussion states at least one rejected alternative; this one has only Decision + Rationale (the substance — extending to code review — is captured in Scope > Out instead, so no information is actually missing).
**Fix:** Add a `Rejected: extend reviewer_self_id to code-review templates too` line for structural consistency with the doc's own convention.

## Verdict

GAPS_FOUND
Two source-verified feasibility gaps (test_stub validation crash, template token-collision crash risk) need resolution first.
MILL_REVIEW_END
