MILL_REVIEW_BEGIN
# Review: mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-09
```

Spot-checked every quantitative claim against source: `mill-go/SKILL.md` step 4(a)/(b)/(c) line ranges (242-293, 258-267, 283-293), all 12 tree-guard call sites (638, 675, 710, 775, 780, 1026, 1038, 1079, 1088, 1093, 1126, 1133) and their unguarded-call form, `_treeguard.check_and_restore`/`_status.append_recovery_log` real signatures, `mill-plan/SKILL.md` Entry table (lines 39-48, including the exact `approved: true` halt row at line 46) and its zero-argument-parsing state, `mill-setup/SKILL.md`'s Phase 0 precedent, `mill-plan/SKILL.md` line 473 (`"planned"` phase write) and line 242 (`reviews_dir` derivation site), `_review_plan.py`'s three `reviews_dir` resolution sites (369, 696 inside `run()`, and `millpy-review-plan.py`:223) plus confirmation `finalize()`/`run()` take no subdir override today, `_parent_branch.py`'s `FileNotFoundError`→`None` behavior, `mill-merge/SKILL.md`'s Entry-Step-4 unconditional `resolve()` call (line 77) and the Steps-Step-4-cleanup-before-Steps-Step-5-sub-step-6-`append_phase` crash sequence (lines 217 vs. 308-312), `_status.append_phase`'s `_require_path` guard confirming the crash, `implementer-brief.md`'s four cited line ranges, and `_implementer_common.py`'s three cited line numbers. All matched exactly — no fabricated or stale claims found.

All seven Decisions carry rationale + rejected alternatives; scope in/out is unambiguous and each Decision's mechanism is independently traceable to real source; Testing section correctly scopes unit-test needs (new `_status.append_inferred_success_log` modeled on the existing, already-unit-tested `append_recovery_log` in `test-status.py`) versus prose-only verification for the SKILL.md-only changes. No undecided items, no TBDs, no scope ambiguity found.

## Verdict

APPROVE
Every checked claim verified against source; decisions, scope, and testing are complete and consistent.
MILL_REVIEW_END
