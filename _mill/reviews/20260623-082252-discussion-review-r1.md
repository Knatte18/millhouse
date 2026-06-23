Confirmed: `--extra-file` is the existing precedent for adding `--prior-notes`, and the `review-code-holistic.md` template uses `<TOOL_RULE>` and `<ARTEFACT_SECTION>` — the new `<PRIOR_NONBLOCKING>` token would be added here. Note that the template currently does NOT have the token, so adding it requires `prepare()` to ALWAYS supply `prior_nonblocking` (defaulting to "(none)") or `render()` will raise KeyError. This confirms my earlier observation.

I have enough to produce the review. Let me assess the findings:

1. **#518b holistic verify enforcement contradiction** — Testing line says "holistic fixer with `verify_cmd` exercised" but design keeps `verify_cmd=None` and rejects a real holistic `verify_cmd` as out of scope. The script-side `_run_verify_gate` is bypassed for holistic, so the "may not report success on failing test" rule for holistic is purely brief/LLM-enforced, with NO structural catch — unlike #515's strong structural gate. This is a GAP: the testing strategy and the decision are inconsistent about whether holistic gets an automated catch.

2. **#518a token default / "(none)" rendering** — minor, the discussion does state round 1 renders "(none)", but doesn't explicitly state prepare() must unconditionally set the token. NOTE-level since render() raises KeyError on missing tokens.

3. **`_is_benign_windows_cleanup` signature unification** — the existing `_is_windows_lock_error(e: Exception)` takes an Exception; the proposed helper takes `output: str`. The decision says "unify ... to reuse it" but the two have different input types (Exception vs string). This is a feasibility detail worth a NOTE.

Let me produce the review.

MILL_REVIEW_BEGIN
# Review: Fix nit-enforcement gate, Windows verify false-positive, reviewer oscillation, and scope-violation handling

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-23
```

## Findings

### [GAP] #518b holistic-verify enforcement is prose-only, not structural
**Section:** Decisions #518b / Scope / Testing
**Issue:** The decision says the holistic fixer "may NOT report success while any test is failing," but holistic still passes `verify_cmd=None` (millpy-fix.py:281) so `_run_verify_gate` is bypassed — the rule is enforced only by the LLM honoring `fixer-holistic-brief.md`, with no script-side catch (unlike #515's structural gate). The Testing bullet (L116) asserts "holistic fixer with `verify_cmd` exercised does not report success on a failing verify (the existing gate path)," but no holistic `verify_cmd` exists and a real one is explicitly Rejected (L71) as out of scope. The test as worded cannot run against the holistic path.
**Fix:** State explicitly that #518b for holistic is brief-only reinforcement with no automated gate, and rewrite the holistic test bullet to assert brief content (the unsatisfiable-demand / "no success on failing verify" instruction text) rather than "the existing gate path," OR have millpy-fix's holistic branch derive and pass a concatenated batch `verify_cmd` so the gate actually fires.

### [NOTE] `<PRIOR_NONBLOCKING>` token must be unconditionally supplied
**Section:** Decisions #518a / Technical context (_review_code.py prepare)
**Issue:** `_render.render` raises KeyError on any unresolved token, and `prepare()` builds `prompt_kwargs` then renders; once the templates carry `<PRIOR_NONBLOCKING>`, round 1 will crash unless `prepare()` always sets `prior_nonblocking` (defaulting to "(none)"). The discussion says it "renders to (none)" but never states the default must be set unconditionally in prepare, not just when `--prior-notes` is present.
**Fix:** Add a one-liner: prepare always sets `prompt_kwargs["prior_nonblocking"]`, defaulting to "(none)" when `--prior-notes` is absent.

### [NOTE] Benign-cleanup helper unification crosses an input-type boundary
**Section:** Decisions #517
**Issue:** The decision says factor out `_is_benign_windows_cleanup(output: str)` and "unify the existing WinError-32 `_is_windows_lock_error` logic to reuse it," but the existing helper takes `e: Exception` (inspects `__cause__.winerror`), not a string — the two operate on different inputs, so reuse is not a drop-in substitution.
**Fix:** Clarify the unification shape: either keep `_is_windows_lock_error(e)` as a thin wrapper that stringifies/inspects the exception and delegates the string-signature match to the shared helper, or note both call a common signature-matcher.

## Verdict

GAPS_FOUND
Holistic-verify enforcement is prose-only while the test bullet assumes a non-existent gate path.
MILL_REVIEW_END
