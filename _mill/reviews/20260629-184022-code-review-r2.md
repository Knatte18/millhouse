Now I have sufficient context to compile the holistic review. Let me write the final output.

MILL_REVIEW_BEGIN
# Review: Add first-class Moves/Renames field to plan cards for rename-heavy batches — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-29
```

## Findings

### [NIT] `prepare()` uses `creates_union` for ancestor scan; `_review_one_batch` uses `combined_creates`
**Location:** `C:\Code\millhouse\wts\mill-plan-rename-moves\plugins\mill\scripts\_review_plan.py:373-374` and `:468-469`
**Issue:** In `prepare()` per-batch (line 374) and holistic (line 469) the `ancestors_on_disk` list comprehension filters against `creates_union`, but `_review_one_batch()` (line 172) and `run()` holistic (line 814) filter against `combined_creates = creates_union | moves_targets`. The two execution paths (agent-mode `prepare` vs. legacy `run`) diverge in what they scan as ancestor creates, even though both correctly use `combined_creates` for the `resolve_ref_paths` suppression call. Practical impact is zero because move targets do not exist at plan-review time and `resolve_existing_paths` silently drops non-existent paths.
**Fix:** In both `prepare()` ancestor-scan sites, replace `creates_union` with `combined_creates` (already in scope at those points) to keep both paths consistent.

### [NIT] `_check_move_target_collision` accepts `creates_union` but never reads it
**Location:** `C:\Code\millhouse\wts\mill-plan-rename-moves\plugins\mill\scripts\_plan_validate.py:450-460`
**Issue:** The function signature accepts a `creates_union: set[str]` parameter (matching the plan spec), but the function recomputes per-batch creates internally via `_parse_creates_only` and the parameter is never referenced in the body. The dead parameter is documented in the docstring but adds noise to the call site.
**Fix:** Either remove the parameter and have callers omit it, or assert/consume it defensibly as a cross-check against the internally computed union. Leaving it as a pure dead parameter is low priority but should be addressed to keep signatures clean.

## Verdict

APPROVE
Implementation is correct and complete; two NITs with zero functional impact.
MILL_REVIEW_END
