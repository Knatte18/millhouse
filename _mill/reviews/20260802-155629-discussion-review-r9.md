MILL_REVIEW_BEGIN
# Review: Improve diagnosability of plan-validate errors and finalize verify-replay failures

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact minor version unknown)
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] No named extraction for compute_baseline's "algorithm-only piece"
**Section:** Decisions — `gap2-shared-transient-checkout`, `gap2-checkout-teardown-extraction`
**Issue:** `gap2-checkout-teardown-extraction` says `compute_baseline` stays a monolith (checkout -> `_link_dependency_dirs` -> its existing 3-run/control-check algorithm -> teardown) with an UNCHANGED public signature; but `gap2-shared-transient-checkout` and the matching Technical-context bullet require `_run_baseline_stage` to invoke "`compute_baseline`'s now-separated algorithm-only piece"/"both algorithm pieces" directly against an *already*-shared checkout, without re-running checkout/teardown — no decision names, signs, or extracts that "algorithm-only piece" as its own function.
**Fix:** Either add a fourth extracted helper (e.g. `_run_baseline_algorithm(cmd, effective_path, project_root) -> str`) that both `compute_baseline` and `_run_baseline_stage` call, or give `compute_baseline` an explicit "skip checkout, use this path" parameter — and say so, since the current text's "signature UNCHANGED" directly contradicts "algorithm-only piece is called directly."

### [GAP] `_link_dependency_dirs` claimed "reuse as-is"/"UNCHANGED" contradicts its current conditional body
**Section:** Decisions — `gap2-checkout-teardown-extraction`; Technical context, `_verify_baseline.py` bullet
**Issue:** Both cite `_verify_baseline.py:184-193` as "already generic enough to reuse as-is" / "UNCHANGED" for `_link_dependency_dirs(project_root, target_path)`. Actual source at those lines branches internally on `cwd_override_relative`/`tmp_path` (`compute_baseline`'s own closure variables: `(tmp_path / cwd_override_relative / name) if cwd_override_relative is not None else (tmp_path / name)`), not a single pre-resolved `target_path` parameter — the conditional must be collapsed to `target_path / name` for the new signature to work.
**Fix:** Correct the claim to say the loop's branching is removed/simplified when extracted (caller pre-resolves `target_path`), not "unchanged"/"as-is" — a plan writer copying this line range verbatim would retain dead references to `tmp_path`/`cwd_override_relative` that no longer exist in the new function's scope.

## Verdict

GAPS_FOUND
Two internal inconsistencies in the shared-checkout refactor's function boundaries need resolving before plan writing.
MILL_REVIEW_END
