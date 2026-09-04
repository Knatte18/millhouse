MILL_REVIEW_BEGIN
# Review: Review prompt/output file listings resolve plan-relative paths to absolute before display, instead of keeping them relative — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently verifiable)
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:scope] `_build_artefact_section`'s two `bulk_files` call sites, only one named
**Location:** Batch 3, Card 11 (`_review_code.py::_build_artefact_section`)
**Issue:** In bulk mode the function has two mutually-exclusive `bulk_files` calls -- `bulk_files(plan_and_ancestors)` on the `start_sha is not None` branch (diff-scoping active) and `bulk_files(all_bulked)` on the `else` branch -- but Card 11's Requirements say "pass `roots=roots` to ... the `bulk_files(...)` call" in the singular, naming only one occurrence. `start_sha` comes from `status.md`'s per-batch entry and is present for essentially every real per-batch code review after the first commit, so the diff-scoped branch (`bulk_files(plan_and_ancestors)`) is the common production path, not an edge case.
**Fix:** Reword Card 11 to explicitly name both `bulk_files` call sites (the diff-scoped-branch call and the else-branch call) so neither is left on the default `roots=None`.

### [BLOCKING:scope] Card 13's new assertions don't cover the diff-scoped branch
**Location:** Batch 3, Card 13 (`test-review-code-flow.py`)
**Issue:** The existing test 23 fixture that Card 13 repairs (the `Moves:` suppression case, `#686`) does not set a `start_sha`, so it exercises only `_build_artefact_section`'s `else` branch (`bulk_files(all_bulked)`). Card 13's new "no `str(project_root)`" / `## Path roots` assertions are likewise not scoped to a start_sha-bearing fixture. If the sibling gap above (missed `roots=` on the diff-scoped `bulk_files(plan_and_ancestors)` call) ships, no test in this batch would catch it, since the existing start_sha-bearing fixtures (test14c/14d) assert on `DIFF`/`FILE` delimiter presence, not on absolute-path absence.
**Fix:** Add (or extend an existing start_sha-bearing fixture with) a "no `str(project_root)`" assertion so the diff-scoped branch is exercised by the new regression coverage, not just the plain branch.

### [NIT:scope] `DisplayRoots.render` test list omits the wiki-vs-project_root priority case
**Location:** Batch 1, Card 1 (`_review_common.py::DisplayRoots.render`, `test-review-common.py`)
**Issue:** The rendering rule is unambiguous (wiki_root checked first, unconditionally, before the longest-match step), but Card 1's enumerated test list has no case where a path sits under both `wiki_root` and a deeper `project_root`, which is the one scenario that actually proves rule 1 short-circuits rule 2 rather than merely coexisting with it.
**Fix:** Add one `DisplayRoots.render` test case with a path under both a `wiki_root` and a nested `project_root`, asserting the `wiki/` form wins.

## Verdict

REQUEST_CHANGES
Card 11/13 under-specify `_build_artefact_section`'s two `bulk_files` sites, risking an absolute-path leak on the common start_sha path.
MILL_REVIEW_END
