MILL_REVIEW_BEGIN
# Review: mill-go-base: orchestration robustness gaps

```yaml
duration_s: 157.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-09-18
```

## Verdict

APPROVE. All seven independent fixes verified against current source: line numbers, function signatures, error strings, and control-flow claims all match; each Decision carries rationale and rejected alternatives, and scope/testing coverage is concrete.

Spot-checked against source and confirmed exact:
- `_status.phase_entry_timestamp` (line 820-872, `occurrence: int = 1`), `set_blocked`/`append_phase`/`set_module_verify_baseline` mechanics, `_BATCH_ALLOWED_KEYS`/`_BATCH_STATES` — all match #1005/#1013/#1031 claims.
- `set_batch_field` raising `ValueError: Batch {name!r} not present in ## Batches` when `## Batches` is absent, and `millpy-implement.py`'s per-batch loop (line 447-457) catching it per-batch and discarding wasted verify-replay work — confirms the `--module-wide-only` rationale for #1031 exactly.
- `holistic-review.md` line 51 (`occurrence=H`) and lines 167-169 (dispatch → compute `converged` with no inline capture/finalize reminder) — confirms #1005 and #997's stated gaps are real in current text.
- `handoff.md` step 5 (line 165-168) / step 6 (line 169-173), `mill-self-report/SKILL.md` line 36 (`git rev-parse --show-toplevel` from cwd), and `conversation/SKILL.md`'s verbatim "Worktree isolation" `cd`-ban — confirms #990's rejection of the issue's own suggested `cd` fix and the existence-check-and-skip design.
- `mill-plan/SKILL.md` line 623-628 ordering (approved:true precedes `phase: planned`) and `resume.md` having zero `blocked` mentions — both confirmed as stated.

No BLOCKING or NIT findings.
MILL_REVIEW_END
