# Batch: plan-review-templates

```yaml
task: 'Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch'
batch: plan-review-templates
number: 3
cards: 3
verify: null
depends-on: []
```

## Batch Scope

Add two new reviewer-brief criteria bullets — the All-Files-Touched-exclusion rule (#717) and the platform-behavior-claim-verification rule (#714) — to both `review-plan-holistic.md` and `review-plan-batch.md`, since both templates bulk the full overview (including `## All Files Touched`) into the reviewer's prompt and are equally exposed to the false-NIT failure mode #717 reported. Extend `test-review-templates.py`'s existing kept/deleted-prose assertion pattern to prove both new bullets land in both templates' raw source. Independent of Batch 1/2 (`_review_plan.py` counting fix) and Batch 4 (`_plan_validate.py` validator) — no shared files, no ordering dependency.

## Cards

_One `### Card N` per card, numbered globally across all batches._

### Card 14: `review-plan-holistic.md` — add two new criteria bullets

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/review-plan-holistic.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Criteria (apply to the plan as a whole)` section, immediately after the existing `- **Global step numbering** — unique, sequential, no gaps across batches.` bullet (the last bullet in the list), append these two new bullets verbatim:

  ```
  - **All Files Touched scope** — the overview's `## All Files Touched` section lists the union of `Edits:`/`Creates:`/Move-target paths across all batches; `Deletes:` tokens and Move-source paths are excluded by convention. A Deletes-only or Move-source-only path missing from that list is correct, not a finding.
  - **Platform-behavior-claim verification** — BLOCKING if a plan or discussion claim describes Claude Code's own platform/harness behavior (e.g. agent auto-discovery, plugin manifest semantics) and a manifest or doc file that could confirm or refute the claim is present in your context, bulked or Read-able, but the claim was accepted without checking that file. Tool-use-mode reviewers may Read `plugin.json`/platform docs directly even when not bulked.
  ```

  Do not modify any existing bullet or any other section of the file.
- **Commit:** `docs(review-plan-holistic): add All-Files-Touched-scope and platform-claim-verification criteria`

### Card 15: `review-plan-batch.md` — add the same two new criteria bullets

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/review-plan-batch.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Criteria (apply briefly)` section, immediately after the existing `- **Context completeness** — BLOCKING if `Requirements:` mentions a function, class, or constant from a file not listed in `Context:` or `Edits:`. The implementer may only read files in `Context:`; a missing entry means cold-start exploration.` bullet (the last bullet in the list, immediately before the `**Reviewer note:**` paragraph), append the identical two bullets added to `review-plan-holistic.md` in Card 14, verbatim (same text, same order):

  ```
  - **All Files Touched scope** — the overview's `## All Files Touched` section lists the union of `Edits:`/`Creates:`/Move-target paths across all batches; `Deletes:` tokens and Move-source paths are excluded by convention. A Deletes-only or Move-source-only path missing from that list is correct, not a finding.
  - **Platform-behavior-claim verification** — BLOCKING if a plan or discussion claim describes Claude Code's own platform/harness behavior (e.g. agent auto-discovery, plugin manifest semantics) and a manifest or doc file that could confirm or refute the claim is present in your context, bulked or Read-able, but the claim was accepted without checking that file. Tool-use-mode reviewers may Read `plugin.json`/platform docs directly even when not bulked.
  ```

  Do not modify any existing bullet, the `**Reviewer note:**` paragraph, or any other section of the file.
- **Commit:** `docs(review-plan-batch): add All-Files-Touched-scope and platform-claim-verification criteria`

### Card 16: `test-review-templates.py` — assert both new bullets are present in both templates

- **Context:**
  - `plugins/mill/templates/review-plan-holistic.md`
  - `plugins/mill/templates/review-plan-batch.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-templates.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new test function `test_plan_criteria_bullets_present() -> None`, following the exact structure of the existing `test_kept_prose_stays_kept()` function (loop over `["review-plan-holistic", "review-plan-batch"]`, call `_read_template_source(name)`, assert-and-message per phrase). Assert that each of `_read_template_source(name)` for both `"review-plan-holistic"` and `"review-plan-batch"` contains the exact substring `"the overview's `## All Files Touched` section lists the union of"` and the exact substring `"Platform-behavior-claim verification"`. Print `"PASS test_plan_criteria_bullets_present"` on success. Add `test_plan_criteria_bullets_present` to the `tests` list inside `main()` (the list currently reads `[test_all_templates_render, test_deleted_prose_stays_deleted, test_kept_prose_stays_kept, test_no_output_file_token]`); append the new function name after `test_kept_prose_stays_kept` in that list, preserving the existing `try`/`except AssertionError`/`except Exception` failure-collection loop unchanged.
- **Commit:** `test(review-templates): assert new plan-review criteria bullets present`

## Batch Tests

`verify:` runs `test-review-templates.py`, which already renders all five templates end-to-end (`test_all_templates_render`) and now additionally asserts the two new criteria bullets from Cards 14/15 are present verbatim in both edited templates' raw source (Card 16), plus the pre-existing kept/deleted-prose checks confirming no unrelated content regressed.
