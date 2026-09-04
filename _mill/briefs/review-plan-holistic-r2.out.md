MILL_REVIEW_BEGIN
# Review: Review prompt/output file listings resolve plan-relative paths to absolute before display, instead of keeping them relative — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: plan/
date: 2026-09-04
```

## Findings

None. Verified against source across all three batches:

- All four `_review_plan.py` assembly sites (`_review_one_batch`; the two `prepare()` branches at the batch-mode and holistic blocks; `run()`'s holistic block) and both `build_reattached_section` resume sites are located exactly where the plan says, with `project_root`/`git_root`/`wiki_root` all in local scope at each — confirmed by reading `_review_plan.py` lines 134-660 and 750-1160.
- `_review_code.py`'s `_build_artefact_section` has exactly the three bulking calls Card 11 warns about (`bulk_files_with_diff` + `bulk_files(plan_and_ancestors)` on the diff-scoped branch, `bulk_files(all_bulked)` on the else branch), its single `prepare()` call site, and its single `build_reattached_section` site in `run()` — all match the plan's descriptions verbatim, including bullet punctuation differences between sites.
- `_review_common.py`'s current `build_manifest_section`, `bulk_files`, `bulk_files_with_diff`, `build_reattached_section`, `build_deletes_section` match the "today's absolute output" baseline the plan describes, and existing back-compat tests for each already exist in `test-review-common.py`, supporting the byte-identical-when-`roots=None`-Decision.
- The `run_tool_use()`-takes-no-`cwd` platform claim underpinning the "resolve-against-stated-root" Decision is verified directly against `_llm_claude.py`: `run_tool_use` calls `_invoke(...)` without a `cwd` kwarg, unlike `run_implementer` which passes one explicitly, and `_invoke` defaults `cwd=None`.
- `millpy-merge-in-subagent.py`'s `--files` argument is rendered verbatim into `CONFLICTING_FILES` with no root-joining, confirming Card 14's "already relative" pin is warranted, and the existing `` `a.py` ``/`` `b.py` `` assertions Card 14 extends are present in `test-millpy-merge-in-subagent.py`.
- `test-review-code-flow.py`'s test 23 (`#686`) and test 14c (`start_sha`-bearing, asserts `--- DIFF:` present) match Cards 13's descriptions exactly, including the `new_path`/`old_path` FILE-delimiter assertions Card 13 must convert to relative form.
- Batch Index DAG is acyclic, all three `file:` entries exist, `depends-on` has no forward refs; global step numbering (1-14) is sequential with no gaps; `## All Files Touched` is the exact union of every batch's `Edits:`; no card declares a non-empty `Moves:`, so the absent `## Rename mechanic` section is correctly not a finding; no call site of the four display helpers exists outside `_review_plan.py`/`_review_code.py`, so batch 2 + batch 3 cover the full call-site scope with nothing left unassigned.

## Verdict

APPROVE
Plan claims verified against current source; sites, scopes, and platform-behavior premises all check out.
MILL_REVIEW_END
