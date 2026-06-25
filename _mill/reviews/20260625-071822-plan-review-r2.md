MILL_REVIEW_BEGIN
# Review: Fix spawn lifecycle integrity, agent-mode async assumption, merge-in conflicts, and pre-existing failure validation — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-25
```

## Findings

### [NIT] Card 9 miscounts `_run_verify_gate` call sites
**Location:** Batch 3 / Card 9
**Issue:** Card says "five existing `_run_verify_gate` ... call sites ... (`_forward_output` at ~567, ~691, ~746, ~802, plus `finalize_from_output`)"; `finalize_from_output` has no direct gate call — it delegates to `_forward_output`, so there are exactly four real sites.
**Fix:** Drop `finalize_from_output` from the call-site enumeration; the single-helper refactor still maps cleanly onto the four `_forward_output` sites.

### [NIT] Card 16 may need no code change beyond the test
**Location:** Batch 4 / Card 16
**Issue:** The conflicts-mode success path goes through `_forward_output`'s parsed-success branch (`_implementer_common.py:632 print(json.dumps(parsed))`), which already emits the whole parsed dict verbatim — `discarded` survives without reshaping.
**Fix:** None required; the card's conditional phrasing ("if the forwarding path reshapes ...") already covers this, and the preservation test remains the load-bearing deliverable. Flagging so the implementer does not invent a needless threading change.

### [NIT] Card 4 rollback does not restore multi-mode groomed sources
**Location:** Batch 1 / Card 4
**Issue:** In multi mode the merge+claim runs at `millpy-spawn.py:134` (before the card's "from the wiki claim" span); `wiki.set_phase(slug, None)` on failure clears the merged slug but cannot restore the source tasks already absorbed by `multi_select_groom_then_claim`.
**Fix:** Acceptable as-scoped — the rollback boundary is explicit and the Card 7 reconcile backstop handles orphaned `active` markers; note for the implementer that multi-mode source restoration is intentionally out of scope.

## Verdict

APPROVE
Plan is source-grounded, DAG-clean, and complete; findings are advisory NITs only.
MILL_REVIEW_END
