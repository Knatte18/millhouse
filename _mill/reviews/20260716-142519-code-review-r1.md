MILL_REVIEW_BEGIN
# Review: Miscellaneous small tooling and doc/template accuracy gaps — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-16
```

All five batches verified against their cards and against each other.

- Batch 1 (`_reviewers.py` tier_rank/fixer_weaker_than_reviewer_warning, `millpy-fix.py` wiring, `mill-config.yaml` comment, `test-reviewers.py`/`test-millpy-fix.py` coverage): helper placement, local `import _agent_dispatch` (avoids the documented cycle), tuple-rank semantics, docstring Public API updates, and the stderr-only/no-control-flow-change wiring all match the plan exactly. New tests (`test_tier_rank_*`, `test_fixer_weaker_than_reviewer_warning_*`, `test_fixer_tier_warning_fires_when_reviewer_stronger`, `test_fixer_tier_warning_silent_by_default`) are present and wired into `main()`'s explicit test list / `unittest.main()` discovery respectively.
- Batch 2 (`_cleanliness.py` `revert_out_of_scope_drift` `git_root` rebasing, `mill-go/SKILL.md` call-site + signature update, `test-cleanliness.py` ROOD-5/ROOD-6): default `git_root=None` preserves the three existing 3-arg call sites; `owned_paths` and porcelain-line rebasing both implemented before the in-scope check, matching the regression rationale in the batch scope. ROOD-5/ROOD-6 assert the hub-relative checkout path and the owned-file non-revert exactly as specified.
- Batch 3 (`golang-build/SKILL.md`): `$GOPATH/bin` fallback detection snippet added before the report-and-stop bullets, gated on both checks failing, with an explicit stated approach (invoke via full path) — matches card 9.
- Batch 4 (`plan-overview.md`): "All Files Touched" italic paragraph's final sentence now correctly names `_plan_validate.py`'s `all-files-touched-mismatch` check as consumer; no mill-go or parallel-overlap claim remains. Confirmed `all-files-touched-mismatch` is the real check name in `_plan_validate.py`.
- Batch 5 (`mill-plan/SKILL.md`): guardrail sentence inserted verbatim, in the single required location (after step 3, before 4a), covering all of 4a/4b/4c/4d per the plan's placement rationale.

No cross-batch contract issues (all five batches are independently file-disjoint per the plan's own Shared Decision, and no batch's edits touch another's files). No out-of-plan files present — the 11 edited files exactly match the overview's "All Files Touched" list. The `hub_prefix`-rebasing logic is duplicated inline between `compute_scope_violations` and `revert_out_of_scope_drift` (same file), but this is an explicit plan directive (card 6: "a local block, not necessarily a new shared helper function"), not implementer drift, so it is not flagged as duplication.

## Verdict

APPROVE
All five batches match their plan cards; cross-batch consistency and test coverage are sound.
MILL_REVIEW_END
