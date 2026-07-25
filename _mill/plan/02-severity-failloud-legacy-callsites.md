# Batch: severity-failloud-legacy-callsites

```yaml
task: mill-plan review severity counting and validation schema gaps
batch: severity-failloud-legacy-callsites
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-common.py
depends-on: [1]
```

## Batch Scope

`_review_plan.py`'s subprocess/psmux-dispatch `run()` function does NOT go through `finalize_scope()` (batch 1's fix) — it has its own duplicated inline `blocking_count = parse_blocking_count(raw_or_file_text, severity="BLOCKING")` at 5 separate call sites, all sharing the identical one-line shape (confirmed by direct inspection during planning: the fix is the same one-line addition at every site regardless of the surrounding NEED_CONTEXT retry branching). This batch applies `count_unrecognized_severity_findings` (from batch 1) at all 5 sites and adds one discrete regression test; the other 4 sites are covered by code-identity with the tested site, since the applied fix is verified identical across all 5 (not merely assumed).

## Cards

### Card 4: Apply the fail-loud helper at the 3 linear call sites in `_review_plan.py`'s `run()`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Import `count_unrecognized_severity_findings` from `_review_common` in `_review_plan.py`'s existing `from _review_common import (...)` block (alongside the existing `parse_blocking_count` import). At each of these 3 call sites, immediately after the existing `blocking_count = parse_blocking_count(raw, severity="BLOCKING")` line, add `blocking_count += count_unrecognized_severity_findings(raw, blocking_severity="BLOCKING", nit_severity="NIT")`:
  1. Line 284 (per-batch review, inside the function containing the per-batch NEED_CONTEXT retry logic — the `raw` variable here holds the batch reviewer's raw output).
  2. Line 947 (holistic NEED_CONTEXT after a successful re-attach retry — `raw` here holds the retried reviewer's raw output).
  3. Line 982 (holistic normal path, no NEED_CONTEXT — `raw` here holds the reviewer's raw output).
  In every case the addition is the identical one-line pattern operating on the local variable already in scope at that point (`raw`); do not rename or restructure any surrounding control flow.
- **Commit:** `feat(review): apply fail-loud severity counting to plan-review linear call sites`

### Card 5: Apply the fail-loud helper at the 2 remaining call sites (disk-resume, holistic NEED_CONTEXT no-resolve)

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** At each of these 2 remaining call sites, immediately after the existing `parse_blocking_count(..., severity="BLOCKING")` line, add the same one-line fail-loud addition as Card 4 (`count_unrecognized_severity_findings(..., blocking_severity="BLOCKING", nit_severity="NIT")` added into the local `blocking_count`/`_parsed_blocking` variable):
  1. Line 734 (mid-round disk-resume reload — the local variable here is `_parsed_blocking`, reading from `_file_text` rather than `raw`; add `_parsed_blocking += count_unrecognized_severity_findings(_file_text, blocking_severity="BLOCKING", nit_severity="NIT")`).
  2. Line 965 (holistic NEED_CONTEXT, no re-attachable paths — `raw` holds the original (non-retried) reviewer's raw output; identical shape to Card 4's additions).
  This completes all 5 call sites. `count_unrecognized_severity_findings` is already imported by Card 4 in this same batch.
- **Commit:** `feat(review): apply fail-loud severity counting to remaining plan-review call sites`

### Card 6: Add a regression test proving the synchronous dispatch path is fail-loud

- **Context:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new test to `test-review-plan-flow.py`'s `main()`, modeled directly on the existing "Test 14 — aggregate blocking_count" block (batch fixture via `_make_plan_fixture`, `stub.seed([...])`, `plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)`). Seed a per-batch reviewer response containing ONLY a `### [MAJOR]` finding heading (no `### [BLOCKING]` heading at all) plus a `verdict: REQUEST_CHANGES` yaml block, e.g.:
  ```python
  major_only = (
      "# Review\n\n"
      "### [MAJOR] compile break\n\n- b\n\n"
      "```yaml\nverdict: REQUEST_CHANGES\n```\n"
  )
  ```
  followed by an `APPROVE_TEXT` holistic response. Call `plan_run(...)` and assert `r.blocking_count == 1` (proving the per-batch call site at line 284, exercised by this fixture's per-batch dispatch, is fail-loud in the synchronous/subprocess dispatch path -- the path most divergent from batch 1's `finalize_scope()` fix). Follow this file's existing PASS/FAIL print convention and `errors` counter (ASCII-only per project `CLAUDE.md`).
- **Commit:** `test(review): regression-cover fail-loud counting in synchronous plan-review dispatch`

## Batch Tests

`verify:` runs both `test-review-plan-flow.py` (this batch's own new test, plus its full existing suite as a regression guard on the 5 edited call sites) and `test-review-common.py` (re-run as a cross-cutting guard on the `count_unrecognized_severity_findings` helper this batch imports and calls, since batch 1 already covers that helper's own behavior in depth — this re-run is cheap, both files are already `--only`-scoped rather than the unbounded suite).
