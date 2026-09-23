MILL_REVIEW_BEGIN
# Review: mill-go/mill-merge-in orchestration robustness gaps, round 2 — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-23
```

## Findings

(none)

Verified end-to-end across all five batches:

- Batch 1 (`_implementer_common.py`/`_verify_baseline.py`): `_extract_failure_signatures`'s new `returncode` kwarg and synthetic `NONZERO_EXIT:` line match Card 1 exactly, including the untouched `fail_lines = _extract_failure_signatures(omitted)[:20]` call site and the threaded `returncode=rc` in `_verify_baseline._signatures_for_pair`. `_fixer_logic_ancestor_override` (Card 2) is gated correctly in `_forward_output` on `card_ids is None and start_sha is not None`; confirmed `millpy-fix.py`'s `finalize_from_output` call passes `start_sha=args.start_sha` with no `card_ids`, and `millpy-merge-in-subagent.py`'s `conflicts` mode hardcodes `start_sha=None` while `verify-fix` mode never calls `_forward_output`/`finalize_from_output` at all — the override is provably fixer-only. `parse_card_commit_messages` (Card 3) mirrors `parse_commit_none_card_ids`'s exact splitting loop in `_plan_dag.py`, and `millpy-implement.py` threads `card_commit_messages` into both the `--stage finalize` and `--stage full` call sites. Card 4's progress line (`print(f"[baseline] computing on-demand baseline for {batch_name or 'batch'}...")`) is verbatim in `_run_verify_gates`.
- Batch 2 (doc-only): `mill-merge-in/SKILL.md` step 4's rewritten paragraph names `batches`/`order`/`file_by_name` in the exact shape `iter_batch_verifies` itself uses. `mill-go-base/SKILL.md` carries the new "TaskOutput not a callable tool" sentence immediately after all four "or the probe call itself errors" clauses (steps 3(b), 3(c), and both 5.5 probes).
- Batch 3: `_check_verify_untested_tag_in_touched_package` in `_plan_validate.py` matches Card 7's algorithm (touched-package collection via `Edits:`/`Creates:`, per-package `_test.go` tag scan, `_RE_GO_TEST_INVOCATION`/`_RE_SHELL_OPERATOR` segmenting, ancestor-directory `./{parent}/...` coverage walk, `batch: None` findings), is registered in `run()`, and `mill-plan/SKILL.md`'s fix table gained the matching row.
- Batch 4: `_collect_task_intent`'s widened regex includes `Moves:` (Card 8); `merge-in-conflict-brief.md` gained step 6a in the correct position. `conflicts_model` resolution in `main()` (Card 9) matches the plan's branch verbatim, `mill-config.yaml` template comments/key match, and the roadmap-dedup sentence is appended to step 4. `_generous_terminal_env()` (Card 10) is applied to all three named `verify-fix` `subprocess.run` call sites and no others.
- Batch 5: `renumber_after_collision` (Card 11) is byte-identical to the plan's supplied implementation, placed after `compute_next_card_number`, and added to the module docstring listing. `mill-go-base/SKILL.md`'s Stuck-escalation paragraph (Card 12) wires the `PlanDAGError` regex extraction, retry, and fall-through-to-blocked path exactly as specified.

Test coverage: all batch-test-described cases are present and correctly targeted (`test-implementer-common.py` cases 84a-e, 85a-b, 86; `test-verify-baseline.py`'s `_case_o_returncode_synthesizes_signature_for_non_test_failure` including the accepted-limitation sub-case; `test-plan-validate.py`'s `test_verify_untested_tag_in_touched_package_*` and `test_renumber_after_collision_*`; `test-millpy-merge-in-subagent.py`'s `conflicts_model`/`Moves:`/`_generous_terminal_env` cases; `test-config.py`'s `conflicts_model` present/absent-safe cases). No global-utility duplication, no out-of-plan files, no cross-batch contract violations, no Shared Decision deviations, no mutable-default/import-side-effect/Windows-path-sep/CRLF pitfalls observed.

## Verdict

APPROVE
Implementation matches the plan precisely across all five batches with full corresponding test coverage; no findings.
MILL_REVIEW_END
