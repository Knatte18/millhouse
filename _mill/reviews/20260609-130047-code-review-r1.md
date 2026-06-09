Now I have all the information I need to produce the review. Let me analyze everything systematically.

**Plan vs Implementation:**

1. Card 1: `SUBAGENT_REVIEWER = "mill:mill-reviewer"` and `SUBAGENT_IMPLEMENTER = "mill:mill-implementer"` - both set correctly in `_agent_dispatch.py` lines 35-36. The `write_brief` docstring example was changed from `"mill-implementer"` to `"implement"` per the requirement. Done correctly.

2. Card 2: Both `emit_prepare` (line 117) and `emit_prepare_no_dispatch` (line 154) use `_agent_dispatch.SUBAGENT_IMPLEMENTER` - done correctly.

3. Card 3: In `test-agent-dispatch.py` line 133-134, both assertions check `"mill:mill-reviewer"` and `"mill:mill-implementer"`. In `test-implementer-common.py`, Case 12 at line 418 checks `"mill:mill-implementer"`, Case 14 at line 483 checks `"mill:mill-implementer"`. All done correctly.

4. Card 4: `mill-go/SKILL.md` line 112 now reads `"mill:mill-implementer"` or `"mill:mill-reviewer"`. Done correctly.

**Shared Decisions compliance:** Both shared decisions are correctly applied.

**All Files Touched:** All 5 files listed in the overview are accounted for in the batch.

**Out-of-plan files:** All files present in the brief are listed in the plan. No surprise files.

**Test coverage:** The plan requires a `subagent_type` assertion in Case 14. Looking at test-implementer-common.py line 483, it IS present: `assert data["subagent_type"] == "mill:mill-implementer"`. This fulfills the Card 3 requirement exactly.

**Cross-cutting concerns:** The `_agent_dispatch` import in `_implementer_common.py` is at line 3, already present - no duplicate import added.

**Codebase consistency:** ASCII-only print/log output - the new constants use colons in the form `mill:mill-implementer` which is pure ASCII. No issues.

**Language pitfalls:** No mutable defaults, no import side-effects introduced.

Everything checks out cleanly. The implementation is complete, correct, and fully aligned with the plan.

MILL_REVIEW_BEGIN
# Review: Fix agent-dispatch prepare stage to emit namespaced subagent_type -- holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-09
```

## Verdict

APPROVE
All four cards implemented correctly; constants, call sites, tests, and docs are consistent.
MILL_REVIEW_END