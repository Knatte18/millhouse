MILL_REVIEW_BEGIN
# Review: _plan_validate.py: further context-completeness, fence/indent-drift, and tag-exclusion gaps — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-21
```

## Findings

No findings.

Verified against source (`plugins/mill/scripts/_plan_validate.py`):
- Card 1's `_check_move_target_collision` signature/call-site anchors (`root: str | None,` before `*,`; the `if existing:` line at the target-exists branch; `run()`'s call at the end of `run()`) match current source exactly; the new `moves_sources` param/arg threading is well-formed.
- Card 2's `_card_own_reference_set` anchor (`tokens.add(pair_m.group(1))` inside the Moves:-pair walk) and docstring quote match current source verbatim.
- Card 3's `_check_context_completeness`/`run()` insertion points (`if creates_declaring_card_map is None:` block, `search_key, qualifier = shape_result` line, `moves_sources, moves_targets = compute_moves_union(plan_dir)` line, and the call-site's `creates_declaring_card_map=...,` line) all match current source at the described locations.
- Card 4's insertion point (`if file_path.suffix not in _SYMBOL_SEARCH_EXTENSIONS: continue`) and helper placement (before `_resolve_symbol_files`) match source.
- Card 5's `qualifies()`/single-segment/dotted-branch anchors match source verbatim.
- Card 6's `cs_member_re` current pattern quote matches source verbatim; the `new`-exclusion via negative-lookahead correctly blocks matches through a `throw new X(...)`/`= new X()` construction expression.
- Card 7's `_check_requirements_quote_indent_drift` refactor (clean/strip/add pass anchors, `matched`/absence-of-flag-in-add-pass observation, `_first_nonblank_line_indent` placement) all match current source structurally; the reset/skip-chaining semantics correctly limit the new paired-fence check to a single immediately-preceding matched anchor.
- Card 8's SKILL.md row quotes (`verify-excludes-edited-tagged-test`, `requirements-quote-indent-drift`, including "In both cases..." ending sentence) match the current file verbatim.

Batch sequencing rationale (cards 1/3 non-adjacent call sites; cards 4/6 non-adjacent spots in `_resolve_symbol_files`) checks out against actual line order. All Files Touched, verify-batch-mismatch, verify-not-isolated, card numbering, and Batch Index DAG are all internally consistent. No Moves: in this plan, so Rename-mechanic/no-full-rewrite criteria don't apply.

## Verdict

APPROVE
Plan's mechanism claims all verify against current source; no structural or decision-fidelity gaps found.
MILL_REVIEW_END
