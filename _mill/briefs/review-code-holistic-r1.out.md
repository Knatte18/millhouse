MILL_REVIEW_BEGIN
# Review: _verify_baseline.py transient worktrees can be orphaned when the task worktree is force-removed mid-computation — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-09
```

## Findings

### [NIT] Docstring `Sequence:` numbering deviates from Card 1's literal step-by-step instruction
**Location:** `plugins/mill/scripts/_worktree.py:231-249`
**Issue:** Card 1 asked for item 4 to be edited in place to describe prune as unconditional, a new item 5 inserted, and the old item 5 renumbered to item 6; the actual docstring instead drops the prune clause entirely from item 4, merges the new-item-5 re-raise text with the old item 5's content into a single item 5, and adds prune's description as a brand-new item 6.
**Fix:** No functional impact — all required information (unconditional prune, re-raise-before-prune ordering) is present and accurate; purely a prose-organization deviation from the plan's literal phrasing, not required to change.

## Verdict

APPROVE
Restructure and real-git test match the plan and Shared Decisions; only a cosmetic docstring-numbering deviation found.
MILL_REVIEW_END
