I have verified all the discussion's source citations. They are accurate: the `parse_batch_refs` j-loop (lines 539-541), the template line 76 wording, the SKILL fix-table row 133, the validator at 1144-1182, the mill-start snippet at 72-87, and the existing tests. One cross-cutting issue surfaced that the discussion does not address.

MILL_REVIEW_BEGIN
# Review: Fix plan validator Moves-target gap, code-review backtick parser, and mill-start encoding crash

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-30
```

## Findings

### [GAP] #580 fix ignores overlapping reads-not-backtick-path validator
**Section:** Problem #2 / Scope (parse_batch_refs)
**Issue:** Plan-validate Check 6 `_check_ref_not_backtick_path` (_plan_validate.py:1056-1082, 1095-1099) already rejects any Context/Edits/Creates/Deletes sub-bullet with >1 backtick span or prose alongside the path -- exactly the #580 repro form. Code review (_review_code.py:268) reads the same `_mill/plan/` batch files that passed this check, so the phantom-token form should never reach holistic review. The discussion never reconciles this: if the form was rejected at plan time, the real escape is a validator bypass/auto-fix gap, and hardening parse_batch_refs masks the symptom; if it wasn't, Check 6 has a hole that also needs fixing.
**Fix:** State in the discussion how the #580 plan reached code review despite Check 6 (skip-check, imperfect auto-fix, or a validator gap), and decide whether the validator path also needs addressing or parse_batch_refs hardening is deliberately defense-in-depth.

### [NOTE] New regression test should pin validate-time coverage too
**Section:** Testing (parse_batch_refs TDD)
**Issue:** The planned unit test only pins parse_batch_refs behavior; it does not assert the same sub-bullet is caught by `reads-not-backtick-path`, leaving the two overlapping parsers untied.
**Fix:** Add an assertion (or note) that the repro sub-bullet is also flagged by `_check_ref_not_backtick_path`, documenting the layered defense.

## Verdict

GAPS_FOUND
The #580 fix omits how the phantom form bypassed the existing reads-not-backtick-path validator.
MILL_REVIEW_END