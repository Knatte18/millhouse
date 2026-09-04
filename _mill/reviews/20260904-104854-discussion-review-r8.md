MILL_REVIEW_BEGIN
# Review: millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps

```yaml
duration_s: 242.0
verdict: APPROVE
reviewer_model: sonnet
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

Cross-checked every cited line number/signature against source: `_implementer_common.py` (`_in_scope_dirty_stuck` L417, `_run_verify_gates` L1042, corroboration-waiver L1179-1190, `finalize_from_output` L1618, `_forward_output` L1768, the four `_run_verify_gates` call sites L1865/2091/2201/2311, `_in_scope_dirty_stuck` call L1975 — confirmed the single call site), `_subprocess_util.git_commit` (L219-236, `name`/`email` mandatory kwargs confirmed), `millpy-fix.py` finalize branch (L415-457, confirmed no `batch_verify_baseline`/`module_verify_baseline`/`module_wide_verify_cmd`/`git_name`/`git_email` currently forwarded, confirmed `git_name`/`git_email` resolved at L301-308), `millpy-implement.py` (finalize branch L710-753, module-wide-verify derivation L660-664, git-identity resolution L564-571, prepare three-way branch L764-870 including the existing `set_batch_fields` call at L827-831), `_status.py` (`_BATCH_ALLOWED_KEYS` L512-521 confirmed missing `self_resolve_remint_at`, `read_full` L746-788, `phase_entry_timestamp` L818-870 confirmed the exact split/strip parsing pattern cited, `append_phase` confirmed to mutate both `phase:` and the timeline), `millpy-bg.py` `_worker_main` (L34-89, confirmed the `with`-block/`finally`-block handle-closure race the heartbeat-join placement is designed around), and `mill-go-base/SKILL.md`/`holistic-review.md` (confirmed `self-resolved-verify-logic` fires at two independent call sites but the holistic occurrence can never coincide with a `state == "running"` batch, so the `_prepare_reuse_entry` gate's `state == "running"` precondition already excludes the ambiguity by construction; confirmed `self-resolved-dead-parent` never precedes a fresh re-fire, matching the trigger-set exclusion rationale).

No fabricated claims found; no line-number or signature mismatches; no undecided TBDs; each `### Decision:` carries rationale and rejected alternatives; the two prior-round self-corrections (dead-parent exclusion, `append_phase`→batch-field switch, `read_phases`→`read_full`) are internally consistent with current source. Testing section names concrete unit-test files/TDD candidates per fix and stays within stated in-memory/tempfile conventions. Constraints section's "no CONSTRAINTS.md" claim confirmed (file absent repo-wide). Scope boundaries (task_dir/parent_branch wiring deferred, `_in_scope_dirty_stuck`'s `_mill/briefs/` exclusion untouched, orchestrator escalation policy untouched, no new CLI flag) are each independently justified and do not conflict with the four in-scope fixes.

## Verdict

APPROVE
Every checked claim verified against source; decisions have rationale and rejected alternatives; no gaps found.
MILL_REVIEW_END
