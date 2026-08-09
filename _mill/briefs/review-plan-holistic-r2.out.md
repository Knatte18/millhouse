MILL_REVIEW_BEGIN
# Review: mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2) — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5, per system prompt)
reviewed_file: plan/
date: 2026-08-09
```

## Findings

### [NIT] Card 3 misidentifies bullet position in harness-tool-contracts.md
**Location:** batch 1 / Card 3 **Issue:** Requirements says the quoted sentence ("Delivers exactly ONE combined-result...") is the "third bullet" of the `## Agent tool` section; it is actually the second bullet (bullet 1 is "Returns immediately...", bullet 3 is "A background agent IS a detached worker..."). **Fix:** Reword to "the second bullet" or drop the ordinal and rely on the literal quoted text, which is otherwise unique and locatable.

### [NIT] Renamed trigger terminology leaves "Agent-mode properties" bullets stale
**Location:** batch 1 / Cards 1-2 **Issue:** Cards 1-2 rename step 4(b)/(c)'s trigger from "stopped/interrupted" to "non-clean terminal `<status>`"-based, but Card 2 explicitly excludes the "Agent-mode properties" bullet list (mill-go/SKILL.md lines ~350-357), which still describes the same mechanism using only the old "stopped/interrupted" language — leaving the properties summary narrower than the widened trigger it now summarizes. **Fix:** Consider a follow-up card (can stay out of this plan) noting the properties bullets describe a subset of the now-widened `(a)`/`(b)`/`(c)` triggers, so a future reader isn't misled into thinking the liveness probe is stop/interrupt-only.

## Verdict

APPROVE
Every batch is source-grounded (exact line/text matches verified), DAG/file-touched lists are consistent, and both findings are cosmetic.
MILL_REVIEW_END
