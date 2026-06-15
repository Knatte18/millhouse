MILL_REVIEW_BEGIN
# Review: Fix millpy-implement.py finalize to accept (or not require) --session-id/--start-sha — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-15
```

## Findings

### [NIT] Card numbering starts at 2, no Card 1
**Location:** Batch 1 / Cards
**Issue:** The batch declares `cards: 2` but the two cards are numbered "Card 2" and "Card 3" -- there is no Card 1, leaving a gap against the global-step-numbering convention (unique, sequential, no gaps).
**Fix:** Renumber to Card 1 (TDD test) and Card 2 (argparse change), and update the cross-references in Batch Scope ("Card 2 is a TDD card... Card 3 makes it pass").

### [NIT] Card 2 names `_status.set_batch_field` but `_status` not in Context
**Location:** Batch 1 / Card 2
**Issue:** Requirements call `millpy_implement._status.set_batch_field`, but `_status.py` is absent from Card 2's `Context:`; strictly this is a context-completeness gap.
**Fix:** Acceptable as-is because the identical call pattern is already present at `test-millpy-implement.py:202` (the Edits file, implicitly readable), so no cold-start exploration is needed; optionally add `_status.py` to Context for explicitness.

## Verdict

APPROVE
Plan faithfully implements the accept-but-ignore decision; only cosmetic numbering and context nits remain.
MILL_REVIEW_END
