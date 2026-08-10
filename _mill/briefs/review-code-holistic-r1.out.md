MILL_REVIEW_BEGIN
# Review: _plan_validate.py: path-reference heuristic false positives (round 3) + run() docstring drift — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-10
```

## Findings

None. All five cards verified end-to-end against source:

- Card 1: `_PROHIBITION_MARKERS` extended with exactly the four required substrings
  (`"never change"`, `"not change"`, `"never modify"`, `"not modify"`), existing entries and comment
  untouched, no `"edit"` scope creep (`_plan_validate.py:1366-1376`).
- Card 2: `_CITATION_MARKERS` tuple added verbatim with matching comment style
  (`_plan_validate.py:1378-1387`); `moves_sources` parameter inserted immediately before
  `moves_targets` in `_check_context_completeness`'s signature (`:1475-1476`) and in the `Args:`
  docstring (`:1517-1518`); docstring's exemption list rewritten to "Three exemptions" with the
  non-path-shaped-token note relocated out of the numbered list (`:1492-1507`); citation-marker
  exemption block and `moves_sources` own-refs exemption both added in the per-token loop
  (`:1551-1553`, `:1578-1579`); call site in `run()` passes `moves_sources` positionally before
  `moves_targets` (`:2739-2741`), consuming the previously-discarded local from `:2706`.
- Card 3: error message field list qualified to `Moves:-source` (`:1590-1594`); SKILL.md fix-table
  row's first clause updated to the same suffix while the already-correct later clause is untouched,
  avoiding a `Moves:-source-source` double-suffix (`SKILL.md:320`).
- Card 4: module docstring's `run(...)` summary already lists `max_cards_per_batch`,
  `max_batch_context_tokens`, `parent_branch` matching the real signature (`:8-10`, `:2644-2654`).
- Card 5: all six required test functions present, correctly named, in the specified insertion point
  and `main()` registration order (`test-plan-validate.py:2209-2448`, `:6287-6292`), using the
  pre-existing `_make_overview`/`_make_batch_file`/`_write_plan` fixtures with no signature drift.

Cross-batch contract (moves_sources plumbing from card 2 into the call site) is consistent; no
out-of-plan files present; no duplicated helpers; shared decisions (marker-substring architecture,
plan-wide moves_sources exemption) applied consistently.

## Verdict

APPROVE
All five cards verified against source; parameter order, message text, docstring, and tests match the plan exactly.
MILL_REVIEW_END
