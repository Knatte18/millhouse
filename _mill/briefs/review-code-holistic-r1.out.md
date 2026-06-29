I now have everything I need. Here is the review:

MILL_REVIEW_BEGIN
# Review: Add first-class Moves/Renames field to plan cards for rename-heavy batches — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-29
```

## Findings

### [BLOCKING] `_review_plan.py` does not suppress Move targets in `resolve_ref_paths`

**Location:** `C:\Code\millhouse\wts\mill-plan-rename-moves\plugins\mill\scripts\_review_plan.py:156-159`, `:355-358`, `:447-450`, `:788-791`

**Issue:** All four `resolve_ref_paths` calls in `_review_plan.py` pass only `creates_union` and `deletes_union`. The shared decision `move-endpoint-accounting` (which explicitly says "Applies to: validator-move-checks, review-backends") requires Move targets to be suppressed in path checks just as Creates tokens are. When a downstream batch's `Context:` or `Edits:` references a Move target (a file that does not exist on disk at plan-review time, e.g. Batch B has `Edits: new/path.py` after Batch A declares `Moves: old/path.py -> new/path.py`), `resolve_ref_paths` raises `ReviewError`; `_review_one_batch` catches it and returns `verdict: ERROR`, which aggregates to REQUEST_CHANGES. Plan review becomes unusable for the primary use case this feature targets. The validator correctly suppresses Move targets via `moves_targets` in `_check_non_existent_path` (Card 8), and the validator test `test_non_existent_path_move_target_suppressed` covers the scenario, but the corresponding fix is absent from all plan-review code paths and there is no test in `test-review-plan-flow.py` covering a downstream batch whose `Edits:`/`Context:` contains a Move target.

**Fix:** In `_review_plan.py`, compute `_, moves_targets_union = compute_moves_union(plan_dir)` (already computed as `moves_sources_union, _ = ...` — add the targets binding), then merge `moves_targets_union` into `creates_union` (or pass it as an additional suppression set) before each of the four `resolve_ref_paths` calls. Add a `test-review-plan-flow.py` case asserting that plan review for a downstream batch with `Edits: <move-target>` does not return ERROR verdict.

### [NIT] `_RE_MECHANIC_HEADING` defined as a local variable inside function body

**Location:** `C:\Code\millhouse\wts\mill-plan-rename-moves\plugins\mill\scripts\_plan_validate.py:577`

**Issue:** `_RE_MECHANIC_HEADING = re.compile(...)` is defined inside `_check_move_mechanic_missing`, while every other regex constant in the module (`_RE_REFS_HEADER`, `_RE_MOVES_HEADER`, `_RE_MOVE_PAIR`, `_RE_REFS_SUB`, `_RE_LINE_RANGE`) is defined at module level. The docstring comment "Compiled once for efficiency when validating many batch files" is misleading — the variable is re-assigned on every function invocation; actual recompilation is avoided only by Python's internal re-cache, not by this placement.

**Fix:** Move the regex to module level alongside the other `_RE_*` constants and remove the misleading comment.

## Verdict

REQUEST_CHANGES
`resolve_ref_paths` in `_review_plan.py` does not suppress Move targets, breaking plan review for any plan that chains Moves with downstream edits.
MILL_REVIEW_END
