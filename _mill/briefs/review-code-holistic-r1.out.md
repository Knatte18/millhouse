MILL_REVIEW_BEGIN
# Review: Improve diagnosability of plan-validate errors and finalize verify-replay failures — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-02
```

## Findings

None. Verified end-to-end against all 7 batches:

- Batch 1/2: `_plan_validate.py`'s `_check_context_completeness` adds the `line` field (stripped, verbatim, no line-number computation per the `gap1-line-field-not-line-number` Decision); docstring and `mill-plan/SKILL.md`'s fixer table updated. `test-plan-validate.py` covers both the new field and the odd-backtick-count false-positive mechanism, matching `discussion.md`'s corrected single-line theory exactly.
- Batch 3: `_status.py`'s `_BATCH_ALLOWED_KEYS`, `set_batch_field`/`set_batch_fields` type hints, and `_serialise_batches`'s `order` list + new leading `isinstance(value, list)` branch (before the existing `str`/else chain) all changed together as required — no silent-drop-on-write gap. Round-trip test covers non-empty and empty-list cases, including the "present, not dropped" distinction.
- Batch 4: `_extract_failure_signatures` (uncapped) and `_normalize_failure_signature` (3 sequential regex subs) extracted/added correctly; the `[:20]` cap moved to the truncation call site, byte-for-byte preserving existing behavior. `_run_verify_gate`'s non-zero-exit stuck dict gains `signatures` from the full untruncated output; the exception path correctly has no such key. `_run_verify_gates`'s subset-diff waiver (normalize both sides, non-empty-subset-only) matches the fail-safe-to-strict rule. `batch_verify_baseline` threaded through `finalize_from_output`/`_forward_output` to all four `_run_verify_gates` call sites identically. Full matrix test coverage (a)-(e) present.
- Batch 5: `_checkout_parent_branch`, `_link_dependency_dirs` (de-closured signature), `_run_module_wide_verify_algorithm` (verbatim extraction, `_run_verify_in` now returns `tuple[int, str]`) all correctly extracted; `compute_baseline` is now a thin wrapper preserving its public contract. `compute_batch_baselines` performs the union-of-two-runs (no third control run) computation exactly as specified, with independent per-name lists. Unit tests cover refactor safety, basic multi-command, union corroboration, and mixed-cwd dependency linking.
- Batch 6: `_run_baseline_stage` restructured with Case A (no per-batch work, standalone module-wide) and Case B (shared checkout, isolated per-batch try/except, shared-setup failure marks every needed batch + module-wide conditionally errored) exactly per the Shared Decisions on checkout sharing and failure isolation. Batch enumeration uses direct frontmatter reading (not `iter_batch_verifies`), correctly avoiding DAG-wide-replay suppression. `--stage finalize`/`--stage full` both thread `batch_verify_baseline` from `status.md`. `mill-go/SKILL.md` documents the two-JSON-line contract. Test coverage (a)-(e) from Card 24 all present and verified against the implementation's actual behavior (idempotency, failure isolation, both shared-checkout-failure sub-cases, direct-enumeration-despite-later-Deletes).
- Batch 7: `test-baseline-waiver.py` is a real-git, 3-step integration test (capture → non-waived new failure → waived pre-existing-only) following the established fixture conventions (wiki TinyDB seeding, hub+worktree, `PYTHONPATH` pinned to worktree scripts, scratch preserved on failure).

No out-of-plan files, no cross-batch contract mismatches, no duplicated helpers, no mutable-default/import-side-effect/path-separator pitfalls observed. `status.md` shows all 7 batches in `approved` state consistent with this holistic review being triggered.

## Verdict

APPROVE
All 7 batches fully realize their cards; cross-batch contracts, shared decisions, and test coverage are consistent and complete.
MILL_REVIEW_END
