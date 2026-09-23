MILL_REVIEW_BEGIN
# Review: mill-plan/verify/implement pipeline: misc small bugs, round 3 — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-23
```

## Findings

None. All three batches were verified against their plan cards and cross-checked against each other.

- **Batch 1 (plan-validate-dotnet-scoping):** `_dotnet_test_segment_is_unscoped` (`plugins/mill/scripts/_plan_validate.py:3998-4040`), `_RE_DOTNET_TEST_INVOCATION`, `_DOTNET_TEST_VALUE_OPTIONS`, `_DOTNET_SOLUTION_SUFFIXES` (`:3971-3995`) match the card's spec exactly — value-option set, solution suffixes, shlex/str.split fallback, flag-skip-next-token logic, and the `--filter` short-circuit all verified line-by-line. `_check_verify_full_suite`'s per-segment loop (`:4119-4131`), the `done_gate` exemption's unchanged precedence (`:4090-4091`, before all four sub-checks), the updated function docstring (`:4051-4054`) and module-docstring check-list entry (naming all four runners) are all present. `test-plan-validate.py` contains exactly the required 5 dirty + 3 clean new dotnet cases plus the renamed/flipped `test_check_verify_full_suite_dotnet_test_project_target_is_ok`, all registered in `main()`'s `tests` list (`:14061-14070`); no leftover reference to the old test name. Card 2's `_subprocess_util.py` docstring changes (module docstring, Public API list, `run()` docstring) are docstring-only — `run()`'s body is byte-unchanged, matching the "already-fixed" Shared Decision.
- **Batch 2 (status-path-coercion):** `_as_path` (`plugins/mill/scripts/_status.py:60-87`) matches the spec. `grep -n "_require_path"` returns nothing. Every public function whose first parameter is `status_path` — including `resume_batch`, which had no prior `_require_path` call — now opens with `status_path = _as_path(status_path, "<fn>")` and carries a `Path | str` annotation. `test-status.py` has the required coercion tests: `append_phase`/`update_field`/`set_blocked`/`read_status` via `str(path)`, a `_FakePathLike` case, and `TypeError`-with-function-name assertions for `None`/`123`.
- **Batch 3 (verify-guidance-docs):** `mill-plan/SKILL.md`'s new "Extended timeout" paragraph is inserted at the correct point (after the self-run-validator paragraph, before the code block) with the exact required text; steps 4b/4c/4d each carry the specified back-reference clause with no rationale repeated; the "Verify command shape" non-Python example now reads `go test ./internal/foo/...` / `dotnet test My.Tests.csproj`, while the Done-gate reminder's unscoped examples are correctly left untouched. All six `mill-implementer*.md` files carry byte-identical appended guidance after the no-`sed` rule, frontmatter untouched; `plugin.json` already lists all six (no edit needed, matches Context-only designation). `test_implementer_agents_background_verify_guidance` is registered immediately after `test_implementer_xhigh_agent_definition` as specified.
- **Cross-batch:** `00-overview.md`'s Batch Index `verify:` entries match each batch file's own frontmatter; the three batches' file sets are disjoint and their union exactly equals `All Files Touched` plus each batch's declared `Context:`-only files (`_plan_dag.py`, `mill-go-base/SKILL.md`, `plugin.json`) — no out-of-plan surprise files in the 21-file manifest. No duplicated helper logic across batches.

## Verdict

APPROVE
All three batches match their plan cards exactly; no cross-batch or integration issues found.
MILL_REVIEW_END
