MILL_REVIEW_BEGIN
# Review: mill-go: baseline-stage timeout/cold-build cost and finalize dirty-tree false positive

```yaml
duration_s: 129.5
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (per environment metadata; self-assessed)
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Verdict

Cross-checked every line reference, precedent claim, and technical-context assertion against source; all accurate.

Verification performed this round: `_run_baseline_stage` (millpy-implement.py:216-452, insertion point at line ~389-391), `_DEPENDENCY_DIR_CANDIDATES` (_verify_baseline.py:64), `_in_scope_dirty_stuck` (_implementer_common.py:417-478, owned_paths/dirt at 463/465), the `ROUND: "1"` / `emit_prepare(..., 1, ...)` hardcode (millpy-implement.py:865/901, exact), cfg-loading and `--stage baseline` call site (millpy-implement.py:523/645), `_run_module_wide_verify_algorithm`'s 3-run/control-check shape and `compute_batch_baselines`' 2-run shape (both confirmed matching "twice"/"up to three" claims), Case A's `compute_baseline` standalone cold-build-once argument, zero `millpy-bg` occurrences in mill-go-base/SKILL.md, the "0.5"/"0.55"/"0.6" section content and 600000ms timeouts (SKILL.md:374,497-591), the cache-form-exception for "0.6" preserved correctly, the `millpy-bg`/cwd-guard precedent in mill-plan/SKILL.md and mill-start/SKILL.md (confirmed present at every cited call site), the "no log-polling" Agent-mode contract (SKILL.md:333), the `pipeline:` template section as a plausible home for the new key, absence of CONSTRAINTS.md, and the existing test-implementer-common.py Case 57 fixture (line 3316, exact).

No fabricated or stale claims found. Decisions have rationale and rejected alternatives; scope in/out is explicit and non-overlapping; failure modes (prepare-cmd non-fatal, shared-checkout-failure, parent-branch-resolution-failure) are each addressed; testing strategy is unit-level and TDD-scoped with explicit order-sensitive and regression assertions for both bugs.
MILL_REVIEW_END
