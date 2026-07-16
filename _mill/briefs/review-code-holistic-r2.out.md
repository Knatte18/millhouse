MILL_REVIEW_BEGIN
# Review: Batch verify/baseline/completeness gates produce false positives or time out — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-16
```

## Findings

No findings. Verified end-to-end across all six batches:

- Batch 01: `card_ids` extraction in `millpy-implement.py` (non-contiguous headings, e.g. `{7, 8}`); `_batch_completeness_stuck`/`_reclassify_verify_failure` signatures and the shared `_cards_incomplete_reason` helper match the spec exactly (already_complete short-circuit, absent/malformed cards_done fallback, int coercion, set-difference reason string). All four call sites in `_implementer_common.py` correctly thread `card_ids`/`cards_done`/`already_complete`, with `already_complete` passed to `_batch_completeness_stuck` only. No stale `card_count=` kwargs remain (confirmed via grep + `test-millpy-implement.py`'s explicit `assertNotIn("card_count", captured_kwargs)`).
- Batch 02: `_go_build_tag_retiering_stuck` correctly implements the added/removed/value-only transition classification, GOOS/GOARCH exclusion, and per-directory dedup; wired into all four `_forward_output`/`finalize_from_output` paths, positioned after the verify gate and before the no-content-commit/completeness checks in every case (confirmed by test case 66g exercising the no-snapshot inference path per Card 9's cross-path coverage requirement).
- Batch 03: `_check_verify_unrelated_test_files` placed alongside the `_check_verify_*` family, reuses existing `_parse_edits_only`/`_parse_creates_only`/`parse_moves`/`resolve_existing_paths` helpers (no duplication), fail-safe on `parent_branch=None` and any subprocess/parse failure. `millpy-review-plan.py` resolves `parent_branch` at both call sites with the same try/except shape as `millpy-implement.py`. `mill-plan/SKILL.md`'s fix table gained the matching row.
- Batch 04: `_done_gate.run_preflight` mirrors the Handoff-time inline block's invocation shape and 2000-char truncation exactly, never raises (catches `Exception`, broader than the prior round's "OSError-only" finding — that concern is now resolved). New `pipeline.done_gate_baseline_preflight` key added identically to both `mill-config.yaml` and the template, defaulting `false`. SKILL.md's new `0.55` block correctly gates on both flag and `done_gate`, runs once per task, and never blocks Prepare on a `blocked` result.
- Batch 05: Timeout guidance generalized to both `millpy-fix.py --stage finalize` and `millpy-implement.py --stage finalize`, plus new notes on both the Handoff-time "0. Pre-done gate" block and the new "0.55" block, all with matching 600000ms rationale text.
- Batch 06: `tmp_path` uses `uuid.uuid4().hex[:12]`, docstring/comment updated, unit test asserts the `verify-baseline-[0-9a-f]{12}` pattern without disturbing the existing `core.longpaths` test.

Cross-batch contracts hold: batch 02's dependency on batch 01 (shared `_implementer_common.py` edit region) and batch 05's dependency on batch 04 (shared SKILL.md section) are both reflected correctly in the code — no missing or out-of-order wiring. All files referenced across every batch's `Context:`/`Edits:`/`Creates:` lists are present in the provided source; no surprise files. Shared Decisions (never-raise, ASCII-only logging, per-file test-style conventions) are honored in every new function and test file inspected.

## Verdict

APPROVE
All six batches integrate correctly; no plan deviations, duplication, or contract mismatches found.
MILL_REVIEW_END
