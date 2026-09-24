# Batch: review-common-and-templates

```yaml
task: Remove batch review (plan-review.batch / code-review.batch)
batch: review-common-and-templates
number: 4
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-class-taxonomy.py test-review-templates.py test-review-output-contract.py test-review-summary.py
depends-on: [3]
```

## Batch Scope

Removes the per-batch machinery from the shared review layer now that batches 1–3 removed every caller: `RE_BATCH`, `detect_resume_round`, the per-batch branches of `discover_round` / `write_review_file` / `resolve_blocking_classes`, and `bulk_files_with_diff`.
Deletes the two per-batch review templates after inlining their severity/verdict rules into the holistic templates, and updates the review-output schema.
`millpy-review-summary.py` keeps its own `_RE_BATCH` parser so historical reviews dirs still summarise.

## Cards

### Card 11: Remove per-batch helpers from _review_common.py

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_discussion.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/_review_common.py`:
  - Delete the `RE_BATCH` constant and its comment; reword the `RE_SIMPLE` comment so it no longer says "(non-batch)".
  - Delete `detect_resume_round`.
  - `discover_round(reviews_dir, review_type, scope)`: keep the signature.
    Raise `ValueError(f"discover_round: unsupported scope {scope!r}; only 'holistic' is supported")` when `scope != "holistic"`, then count `RE_SIMPLE` matches with the given `review_type`.
    Delete the `RE_BATCH` branch.
    A leftover per-batch-named file in `reviews_dir` is ignored.
    Rewrite the docstring accordingly.
  - `write_review_file`: keep the `scope` keyword; raise `ValueError` when `scope` is neither `None` nor `"holistic"`, and always write `<ts>-<type>-review-r<N>.md`.
    Delete the "Plan per-batch" filename rule from the docstring.
  - `resolve_blocking_classes(cfg, review_type, scope)`: keep the signature; always read the `"holistic"` scope key (delete the `scope_key = ... else "batch"` expression).
    The docstring states the `scope` argument is accepted for call-site compatibility and ignored.
  - Delete `bulk_files_with_diff` and any private helper whose only caller it was (check each with a search of the file).
  - `finalize_scope` docstring: drop "or batch name" from the `scope` description.
  - Module docstring's Public API list: remove the `RE_BATCH`, `detect_resume_round()` and `bulk_files_with_diff()` lines.
  - Before deleting each symbol, search `plugins/mill/scripts` for remaining references; batches 1–3 removed them from `_review_plan.py`, `_review_code.py`, `_prior_blocking.py` and `_nit_gate.py`.
    If a reference remains outside this file, stop and report it rather than editing another script.
- **Commit:** `refactor(review-common): remove per-batch review helpers`

### Card 12: Update review-common tests

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
  - `plugins/mill/unit_tests/test-review-class-taxonomy.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/unit_tests/test-review-common.py`:
  - Delete the `detect_resume_round` tests, the `RE_BATCH` tests, the per-batch `discover_round` tests, the per-batch `write_review_file` filename tests, the `"batch"`-key `resolve_blocking_classes` tests, and every `bulk_files_with_diff` test, plus their imports.
  - Add: `discover_round(reviews_dir, "code", "holistic")` counts `RE_SIMPLE` files and ignores a leftover `<ts>-code-review-01-alpha-r5.md` in the same directory (with one `<ts>-code-review-r2.md` present it returns 3).
  - Add: `discover_round(reviews_dir, "plan", "01-setup")` raises `ValueError`.
  - Add: `write_review_file(..., scope="01-setup")` raises `ValueError`; `scope=None` and `scope="holistic"` both write `<ts>-<type>-review-r<N>.md`.
  - Add: `resolve_blocking_classes` returns the `roles.<role>.holistic.blocking_classes` value for both `scope=None` and `scope="holistic"` when a cfg carries that key.

  In `plugins/mill/unit_tests/test-review-class-taxonomy.py`, delete the two `resolve_blocking_classes({}, ..., "01-setup")` rows from the default-fallback table.
- **Commit:** `test(review-common): cover holistic-only round discovery and filenames`

### Card 13: Inline severity/verdict rules and delete per-batch review templates

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/templates/review-plan-holistic.md`
  - `plugins/mill/templates/review-code-holistic.md`
  - `plugins/mill/templates/review-output.schema.md`
  - `plugins/mill/unit_tests/test-review-templates.py`
  - `plugins/mill/unit_tests/test-review-output-contract.py`
- **Creates:** none
- **Deletes:**
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-code-batch.md`
- **Moves:** none
- **Requirements:**
  In `plugins/mill/templates/review-plan-holistic.md`, replace the line `Severity / verdict rules match review-plan-batch.md.` with the block below (the "Severity vocabulary is closed" and class-axis paragraphs that follow it already exist and stay):

  ```
  Severity:
  - `BLOCKING` — must fix before the plan is approved.
  - `NIT` — record but do not block.

  Verdict:
  - `APPROVE` — zero BLOCKINGs.
  - `REQUEST_CHANGES` — one or more BLOCKINGs.
  - `NEED_CONTEXT` — missing source files; orchestrator will re-fire.
  ```

  In `plugins/mill/templates/review-code-holistic.md`, replace the line `Severity / verdict rules match review-code-batch.md.` with the same block, except the BLOCKING bullet reads `must fix before the task is approved.` and the NEED_CONTEXT bullet reads `one or more missing source files; orchestrator will re-fire.`

  Delete `plugins/mill/templates/review-plan-batch.md` and `plugins/mill/templates/review-code-batch.md`.

  In `plugins/mill/templates/review-output.schema.md`: delete the "Plan per-batch" row of the canonical-filenames table and the `<batch-name>` bullet under "Where:"; change the `reviewed_file` description to "path to the artefact reviewed (discussion file or `plan/`)"; remove any per-batch filename from the "Examples:" list that follows.

  In `plugins/mill/unit_tests/test-review-templates.py` and `plugins/mill/unit_tests/test-review-output-contract.py`: remove `review-plan-batch` / `review-code-batch` from every template-name list and token map (and the comment about batch variants needing `batch_name`).
  In `test-review-templates.py`, add a test that renders each holistic template and asserts the rendered text contains the `Severity:` block's `BLOCKING` / `NIT` bullets and the `Verdict:` block's `APPROVE` / `REQUEST_CHANGES` / `NEED_CONTEXT` bullets, and that the template source no longer contains `review-plan-batch.md` or `review-code-batch.md`.
- **Commit:** `refactor(templates): inline severity rules and delete per-batch review templates`

### Card 14: Mark per-batch parsing in millpy-review-summary.py as historical

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-summary.py`
  - `plugins/mill/unit_tests/test-review-summary.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/millpy-review-summary.py`, keep `_RE_BATCH` and its use unchanged.
  Rewrite the comment above `_RE_BATCH`: it no longer mirrors `_review_common.RE_BATCH` (deleted by card 11) and per-batch reviews are not "written for every mill-go batch"; say it parses per-batch review files written by tasks that ran before per-batch review was removed, so their reviews dirs still summarise.

  In `plugins/mill/unit_tests/test-review-summary.py`, the existing `parse_review_filename` cases already cover per-batch plan and code filenames.
  Add one directory-level case: a temp reviews dir holding a historical `<ts>-code-review-01-alpha-r1.md` and a holistic `<ts>-code-review-r1.md` (both with a fenced-yaml `verdict:` header) is summarised through the script's reviews-dir entry point without raising, and both files appear in the result.
  Use the entry point the file's existing tests already call for directory-level summaries; if none exists, call the function `main()` uses to collect rows.
- **Commit:** `docs(review-summary): mark per-batch review parsing as historical`

## Batch Tests

`verify:` runs `test-review-common.py` and `test-review-class-taxonomy.py` (shared helpers), `test-review-templates.py` and `test-review-output-contract.py` (template renders, including the deleted templates' absence), and `test-review-summary.py` (historical filename parsing).
