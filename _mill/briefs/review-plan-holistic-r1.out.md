MILL_REVIEW_BEGIN
# Review: Agent-mode dispatch: envelope fields and session/runtime state are unreliable — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-16
```

## Findings

### [NIT] MILL_SUBAGENT_TOOLS literal isn't alphabetically sorted
**Location:** Batch 6 / Card 18
**Issue:** The card calls the constant "the alphabetically-sorted union" but gives the literal `["Bash", "Read", "Edit", "Write", "Grep", "Glob", "Skill"]`, which is not sorted (sorted would be `Bash, Edit, Glob, Grep, Read, Skill, Write`); test case (d) then compares it against the two agent files' parsed `tools:`.
**Fix:** Either drop the "alphabetically-sorted" wording (content is the correct 7-tool union) or pin test (d) to a set comparison so ordering is irrelevant.

### [NIT] Shared Decision prose undercounts the module-wide verify set
**Location:** 00-overview.md / "Decision: verify command shape and scope"
**Issue:** The rationale says "the union of all eight test files" and its parenthetical omits `test-millpy-fix.py`, but the actual overview `verify:` (line 10) correctly lists nine files including `test-millpy-fix.py` (edited by Card 6).
**Fix:** Update the prose to "nine" and add `test-millpy-fix.py` to the parenthetical list; the executable command is already correct.

## Verdict

APPROVE
Line references, identifiers, and DAG all verify; only two cosmetic doc NITs.
MILL_REVIEW_END
