# Review: Fix prose skill: staleness rule and missing loads

```yaml
verdict: APPROVE
reviewer_model: orchestrator
reviewed_file: _mill/discussion.md
date: 2026-09-22
```

## Findings

### [NIT:decision] Convention test's "wrong order" scenario has no stated disposition
**Demoted-from:** BLOCKING
**Section:** Testing — "The load-directive convention test"
**Issue:** The scenario list ends with "a file naming both but in the wrong order," unlike the other three scenarios it does not say whether this passes or fails. Neither the `convention-test` nor `convention-test-discrimination` Decision defines an order check — both are phrased purely as "does a load directive name `mill:conversation` without also naming `mill:prose`," which a wrong-order file already satisfies.
**Suggested fix:** State explicitly whether the test enforces "`mill:prose` before `mill:conversation`" ordering or only co-presence, and update the Decision text (not just the Testing scenario list) to match.

## Verdict

APPROVE
One BLOCKING: the convention test's order-checking behavior is asserted as a scenario but never decided.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
