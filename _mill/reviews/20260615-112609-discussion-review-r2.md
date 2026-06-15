I have verified the key claims. The `prepare` function (line 298) uses `resolve_path` for plan_dir and loads `root` from the overview (line 308) — confirming that the `--stage prepare` validator wiring described in #465 decision can reuse this same pattern.

I've verified enough to evaluate the discussion. All technical-context line numbers, function signatures, and resolution orderings match the source. The discussion is internally consistent and the three decisions are sound. Let me check one subtle point in the #465 decision regarding the SKILL.md line 104 claim, which the discussion does not explicitly mention updating (it focuses on line 133).

The discussion's #465 says "Update mill-plan SKILL's agent-mode branch to detect this envelope" and "makes the SKILL.md:133 'BOTH modes' claim true." But line 104 ("The CLI auto-runs `_plan_validate` before invoking the LLM") is in Step 1.5 and is generically worded — once prepare runs the validator, line 104 stays true. So no gap there.

Let me check whether there's any concurrency/ordering concern with the prepare envelope shape vs. the validator-failure envelope, since `--stage prepare` success currently returns a `{"stage": "prepare", "brief_path": ...}` envelope while validator-failure would return `{"errors": [...], "summary": ...}`. The SKILL agent-mode branch must distinguish these. The discussion addresses byte-identical shape with full-stage but let me confirm the agent-mode dispatch consumer logic isn't a gap. This is sufficiently covered by the decision text. Now I'll produce the review.

MILL_REVIEW_BEGIN
# Review: Fix millpy-review-plan validator gaps and resolve_ref_paths path-doubling

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-15
```

## Findings

### [NOTE] SKILL.md:104 also asserts auto-run, not just :133
**Section:** Decisions / #465
**Issue:** The decision targets only the SKILL.md:133 "BOTH modes" claim, but line 104 ("The CLI auto-runs `_plan_validate` before invoking the LLM") is the Step 1.5 wording the agent-mode branch dispatches into; once prepare runs the validator this stays true, so no change is needed — worth a one-line note so the plan author does not "fix" it redundantly.
**Fix:** Add a sentence noting line 104 remains accurate as-is and only :133 + the agent-mode envelope-handling step need edits.

### [NOTE] Prepare success vs. failure envelope discrimination
**Section:** Constraints / #465
**Issue:** Success prepare emits `{"stage":"prepare","brief_path":...}` while validator-failure emits `{"errors":[...],"summary":...}`; the SKILL agent-mode parser must branch on key presence, not exit code alone (both paths are JSON on stdout).
**Fix:** State the discriminator explicitly (presence of `errors` key) in the #465 wiring note so the SKILL step is unambiguous.

## Verdict

APPROVE
All technical claims verified against source; decisions are grounded and complete, two minor notes only.
MILL_REVIEW_END