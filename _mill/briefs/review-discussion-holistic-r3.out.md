MILL_REVIEW_BEGIN
# Review: Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Existing env-var override already solves #725
**Section:** Problem / Decision: reviewer-flag-mechanism
**Issue:** `_config.py`'s `ENV_REGISTRY` (lines 46-53) + `apply_env_overrides`, applied as the highest-precedence layer inside `load_config` (line 291), already lets `MILL_DISCUSSION_REVIEWER=<alias>` / `MILL_PLAN_REVIEWER=<alias>` override `cfg["roles"].<role>.holistic.reviewer` for one invocation, zero code changes. `prepare()` reads this same overridden value for both the envelope's model/effort/subagent_type and the rendered `reviewer_model=` token, so it already produces a correctly-attributed round with no `--actual-model` patch needed. Problem's "there is no supported way to say 'use reviewer X for this round'" and the Decision's rejected-alternatives list (only "a config-key-based override") both omit this mechanism entirely.
**Fix:** Acknowledge the existing env-var mechanism; state concretely why `--reviewer` still earns its keep (e.g. an `export`ed env var risks silently leaking into a later, unrelated invocation, unlike a flag) as a considered/rejected alternative.

### [GAP] Claimed template-render test gap is inaccurate
**Section:** Decision: reviewer-self-id-field / Testing
**Issue:** `plugins/mill/unit_tests/test-review-templates.py::test_all_templates_render` already calls `_review_common.render_prompt` (which calls `_render.render`, the function whose `KeyError` is the concern) against all five real on-disk templates, including all three this task edits (review-discussion, review-plan-batch, review-plan-holistic). This contradicts "none of the listed unit tests... exercise render_prompt against the real template" and "plan-writing must add a render-through-the-real-template test... to close that gap."
**Fix:** Correct the rationale -- this regression guard already exists and will already catch a bad `<UPPERCASE>` placeholder; at most note extending its fixtures, not present it as new required coverage.

### [GAP] Ambiguous null-reviewer bypass via --reviewer
**Section:** Decision: reviewer-flag-mechanism / Technical Context
**Issue:** Not specified whether `--reviewer` can revive a scope where the config reviewer is `null` (e.g. a hub with `roles.plan-review.holistic.reviewer: null`). "Replaces reviewer_name/spec at the same point it's currently resolved" reads as substituting before `_review_discussion.py` `prepare()`'s null-check (`if reviewer_name is None: raise ReviewError(...)`), which would silently bypass it, but that isn't stated as intentional.
**Fix:** State explicitly whether `--reviewer` only picks which non-null reviewer runs, or also bypasses a `reviewer: null` disablement; add a test for that config state.

### [GAP] Testing omits run()-specific override coverage
**Section:** Testing
**Issue:** Technical Context establishes `run()` in both backends independently re-resolves `reviewer_name`/`spec` from cfg (duplicating `prepare()`'s logic, confirmed at `_review_discussion.py` lines ~239-241 and `_review_plan.py` lines ~689-693) and needs its own `ReviewerError`->`ReviewError` conversion. The Testing section's bullets only exercise `prepare()`'s envelope/error path ("test both CLIs" for unknown alias); none require asserting `run()`'s actually-dispatched spec reflects the override or that `run()`'s own resolution site converts an unknown alias.
**Fix:** Add an explicit unit test covering `run()`'s reviewer_override handling and error conversion, mirroring the `prepare()`-specific tests already listed.

## Verdict

GAPS_FOUND
Problem framing and two Decisions rest on claims (no existing override; no render-test coverage) contradicted by current source.
MILL_REVIEW_END
