I have verified all the discussion's claims against source. The discussion is highly accurate and well-grounded. I found one unaddressed instance of the same documentation defect plus one minor citation imprecision.

MILL_REVIEW_BEGIN
# Review: Fix plan validator Moves-target gap, code-review backtick parser, and mill-start encoding crash

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-30
```

## Findings

### [GAP] Validator error strings also omit Move targets
**Section:** Scope (In/Out) / Decision: moves-target-docs-not-validator
**Issue:** The #584/#585 fix updates only `plan-overview.md:76` and `mill-plan/SKILL.md:133`, but `_check_all_files_touched_mismatch`'s own runtime error messages (`_plan_validate.py:1192-1193` "but not in any card's Edits: or Creates:" and `:1203-1204` "path '{p}' in card Edits:/Creates: but missing") carry the same Moves-targets-omitting wording -- and that is the message the orchestrator actually reads when a missing Move target fires the `cards_set - overview_set` branch. The module docstring (`:29-30`) already correctly says "Edits:/Creates:/Moves: targets", making these two strings the lone stragglers.
**Fix:** Decide and state whether the fix also corrects those two error-message strings to name Move targets (a docs-in-code change, not validator logic); current scope "Out: no validator change" is ambiguous about message text and would leave the orchestrator greping Edits:/Creates: for a path that lives in Moves:.

### [NOTE] Rationale cites a test that doesn't exercise the fixed path
**Section:** Decision: backtick-leading-token-only (Rationale)
**Issue:** The cited Moves-exclusion regression comment (`test-review-common.py:3263-3266`) describes the `reads-not-backtick-path` validator rule, not `parse_batch_refs` -- which is blind to Moves headers via field dispatch, so that test never runs a multi-backtick sub-bullet through the Context/Edits path being fixed. The one-path-per-sub-bullet conclusion is still independently supported by the "multi-line bullet form" test (`:834-847`).
**Fix:** Anchor the design-intent claim and the new regression test on `:834` rather than the Moves-exclusion test to avoid pointing the plan at the wrong existing anchor.

## Verdict

GAPS_FOUND
Same Moves-targets doc defect persists in the validator's own error messages; scope must decide whether to fix them.
MILL_REVIEW_END