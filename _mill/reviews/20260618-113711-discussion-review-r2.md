All claims confirmed. `_implementer_common.py` imports `os`, `shutil`, `subprocess`, `Path` at module level — everything `_posix_shell_run_args` needs is already in scope. The three test files all exist. The merge-in subagent already imports from `_implementer_common` (line 42). The proposed helper exactly mirrors the existing inline logic in `_run_verify_gate` (lines 130-136).

The discussion is well-grounded against the source. Every cited line number, function name, and behavior matches. The decisions all carry rationale + rejected alternatives. Let me note one detail about the recursive walk pseudocode to confirm the warning-on-PermissionError handling is a deliberate decision and not an undecided item — it is stated clearly in §"Fix 1" line 111.

I have enough to produce the review.

MILL_REVIEW_BEGIN
# Review: Fix nested-junction teardown, Windows verify gate in merge-in, and review-plan --round threading

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-18
```

## Verdict

APPROVE
Three bugs scoped precisely; every cited line, signature, and invariant verified against source. No gaps.
MILL_REVIEW_END

For the record, the verification behind this verdict:

- Fix 1: `_junction.strip_all_in_worktree` at line 279 is confirmed as a single-level `os.scandir` (lines 309-314). The recursive-walk replacement, PermissionError-warns-not-swallows decision, junction-guard-before-is_dir ordering, and retained-but-unused `junctions_cfg` are all decided with rationale.
- Fix 2: `_run_verify_gate` (lines 130-136) contains exactly the inline bash-routing logic the proposed `_posix_shell_run_args` extracts; `_implementer_common.py` already imports `os`, `shutil`, `subprocess`, `Path`. The three `shell=True` call sites in `millpy-merge-in-subagent.py` are at lines 177, 276, 343, and the file already imports from `_implementer_common` (line 42).
- Fix 3: review-plan finalize hard-error at lines 175-177; review-discussion at line 120. `discover_round(reviews_dir, review_type, scope)` signature at `_review_common.py:336` matches the proposed calls; `resolve_path` imported in both CLIs. The round-equivalence invariant holds: `_review_plan.prepare` computes the holistic round via `discover_round(reviews_dir, "plan", "holistic")` (line 395) — identical to the finalize auto-discovery — and the round-N file is not written until finalize, so both return the same N.

All decisions carry rationale plus rejected alternatives; testing strategy names unit-level cases for all three fixes including the CLI-level finalize test (correctly noting the auto-discovery branch lives in `main()`, outside backend coverage). Scope In/Out is explicit and defensible.