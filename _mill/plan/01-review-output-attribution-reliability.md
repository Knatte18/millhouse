# Batch: review-output-attribution-reliability

```yaml
task: 'Review output reliability: metadata misattribution and factual-accuracy failures'
batch: review-output-attribution-reliability
number: 1
cards: 8
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-templates.py
depends-on: []
```

## Batch Scope

This batch is the entire plan: it closes all three of #989 (drop the unreliable `reviewer_self_id`
field from every template it appears in, plus the schema doc), and #991/#1003 (extend the
existing "Mechanism claims must be source-verified." rule — already present in the two plan-review
templates — to the two code-review templates), and updates the unit tests that cover both changes.
No batch is needed for #1018 — see `00-overview.md`'s Shared Decision
"#1018 (reviewer_model misattribution under agent-mode override) requires no code change". All
eight cards touch small, independent regions of eight small text files; none has a real code
dependency on another, so they are grouped into one batch rather than split, per the "smart unit"
guidance (splitting on natural boundaries — here there is really one boundary: "review templates +
their tests").

## Cards

### Card 1: Remove reviewer_self_id from review-discussion.md

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/review-discussion.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete the sentence (and one adjacent blank line, so exactly one blank line
  remains between the preceding `Class governs who decides…` bullet paragraph and the following
  `## Output format — STRICT` heading):
```
Independently state, in the `reviewer_self_id:` field below, what model/version you believe yourself to be — this is your own best-effort assessment, distinct from the `reviewer_model:` value already dictated to you above.
```
  Also delete the line `reviewer_self_id: <your own model self-identification, if known>` from the
  fenced yaml example block under `## Output format — STRICT` (it sits directly below
  `reviewer_model: <REVIEWER_MODEL>` in that block) — leave `reviewer_model: <REVIEWER_MODEL>` and
  every other line in that block unchanged.
- **Commit:** `docs(review): remove reviewer_self_id from review-discussion.md template`

### Card 2: Remove reviewer_self_id from review-plan-holistic.md

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/review-plan-holistic.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete the sentence (and one adjacent blank line, so exactly one blank line
  remains between the preceding `Platform-behavior-claim verification` criteria bullet and the
  following `## Output format — STRICT` heading):
```
Independently state, in the `reviewer_self_id:` field below, what model/version you believe yourself to be — this is your own best-effort assessment, distinct from the `reviewer_model:` value already dictated to you above.
```
  Also delete the line `reviewer_self_id: <your own model self-identification, if known>` from the
  fenced yaml example block under `## Output format — STRICT` (it sits directly below
  `reviewer_model: <REVIEWER_MODEL>` in that block) — leave `reviewer_model: <REVIEWER_MODEL>` and
  every other line in that block unchanged.
- **Commit:** `docs(review): remove reviewer_self_id from review-plan-holistic.md template`

### Card 3: Remove reviewer_self_id from review-plan-batch.md

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/review-plan-batch.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete the sentence (and one adjacent blank line, so exactly one blank line
  remains between the preceding `**Reviewer note:**` paragraph and the following
  `## Output format — STRICT` heading):
```
Independently state, in the `reviewer_self_id:` field below, what model/version you believe yourself to be — this is your own best-effort assessment, distinct from the `reviewer_model:` value already dictated to you above.
```
  Also delete the line `reviewer_self_id: <your own model self-identification, if known>` from the
  fenced yaml example block under `## Output format — STRICT` (it sits directly below
  `reviewer_model: <REVIEWER_MODEL>` in that block) — leave `reviewer_model: <REVIEWER_MODEL>` and
  every other line in that block unchanged.
- **Commit:** `docs(review): remove reviewer_self_id from review-plan-batch.md template`

### Card 4: Remove reviewer_self_id from review-output.schema.md

- **Context:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Edits:**
  - `plugins/mill/templates/review-output.schema.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Three edits to this one file:
  1. In the `## File format` fenced-markdown example near the top of the file, delete the line
     `reviewer_self_id: <optional, reviewer-reported self-identification>` from the illustrative
     yaml block (it sits directly below `reviewer_model: <reviewer name from config, e.g.
     sonnetmax>`) — leave every other line in that block unchanged.
  2. In the "Metadata block fields" table, delete the entire row naming the removed field:
```
| `reviewer_self_id` | string | no | optional, reviewer-self-reported model identification; unverified |
```
  3. Replace the paragraph immediately after that table (currently two sentences on one line,
     starting with the removed field's own name followed by "is unverified and
     reviewer-reported…") with this single sentence, which keeps only the still-accurate
     `reviewer_model` / `apply_actual_model_override()` content and drops the removed field's
     explanation entirely:
```
`reviewer_model` is orchestrator-supplied — dictated to the reviewer up front — and `apply_actual_model_override()` (invoked via the CLIs' `--actual-model` flag) can rewrite it after the fact.
```
     Do not touch the following paragraph (the one beginning `` `duration_s`, `tool_calls`, and
     `cost_usd` are orchestrator-supplied… ``) — it is unrelated and stays exactly as-is.
- **Commit:** `docs(review): remove reviewer_self_id field from review-output.schema.md`

### Card 5: Add mechanism-claim source-verification rule to review-code-holistic.md

- **Context:**
  - `plugins/mill/templates/review-plan-holistic.md`
- **Edits:**
  - `plugins/mill/templates/review-code-holistic.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `review-code-holistic.md`'s `## Source-grounding rule` section, insert a new
  paragraph directly after the existing sentence `Fabricating file contents — or inferring them
  from filename / position alone — is a worse failure than halting honestly.` and directly before
  the following `## Criteria (apply to the implementation as a whole)` heading. Copy the paragraph
  verbatim, byte-for-byte, from `review-plan-holistic.md`'s own `## Source-grounding rule` section
  — it is the paragraph beginning `**Mechanism claims must be source-verified.**` there (the
  paragraph immediately following that same "Fabricating file contents…" sentence in that file).
  Do not reword it.
- **Commit:** `docs(review): extend mechanism-claim source-verification rule to review-code-holistic.md`

### Card 6: Add mechanism-claim source-verification rule to review-code-batch.md

- **Context:**
  - `plugins/mill/templates/review-plan-batch.md`
- **Edits:**
  - `plugins/mill/templates/review-code-batch.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `review-code-batch.md`'s `## Source-grounding rule` section, insert a new
  paragraph directly after the existing sentence `Fabricating file contents — or inferring them
  from filename / position alone — is a worse failure than halting honestly.` and directly before
  the following `## Criteria (apply to the batch's implementation)` heading. Copy the paragraph
  verbatim, byte-for-byte, from `review-plan-batch.md`'s own `## Source-grounding rule` section —
  it is the paragraph beginning `**Mechanism claims must be source-verified.**` there (the
  paragraph immediately following that same "Fabricating file contents…" sentence in that file).
  Do not reword it.
- **Commit:** `docs(review): extend mechanism-claim source-verification rule to review-code-batch.md`

### Card 7: Remove reviewer_self_id round-trip tests from test-review-common.py

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete two inline test blocks from inside `main()` (this file is a flat
  sequential script, not pytest-style functions — each block is a comment + assertion(s) + a
  `print("PASS: ...")` call, with no separate registration to update). Delete the entire block
  (comment through the `print` call, inclusive) starting at the comment
  `# apply_actual_model_override: leaves a reviewer_self_id: line untouched when rewriting
  reviewer_model: -- only the reviewer_model: line changes.` and ending at
  `print("PASS: apply_actual_model_override leaves reviewer_self_id line untouched")`. Delete the
  entire block starting at the comment `# write_review_file: preserves a reviewer_self_id: line
  verbatim` and ending at `print("PASS: write_review_file preserves reviewer_self_id line
  verbatim")` (including its `with _test_helpers.safe_temp_dir() as tmpdir:` block). Leave every
  other test block in this file — including the other `apply_actual_model_override` and
  `write_review_file`/`finalize_scope` blocks immediately before and after these two — untouched.
- **Commit:** `test(review): remove reviewer_self_id round-trip tests (field removed from templates)`

### Card 8: Extend test-review-templates.py for the mechanism-claim rule and reviewer_self_id removal

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-review-templates.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Two changes to this file:
  1. In `test_plan_mechanism_claim_rule_present`, change the loop's list from
     `["review-plan-holistic", "review-plan-batch"]` to
     `["review-plan-holistic", "review-plan-batch", "review-code-holistic", "review-code-batch"]`
     so the existing `"Mechanism claims must be source-verified." in source` assertion also covers
     the two code-review templates Card 5 and Card 6 added the rule to. Update the function's
     docstring (currently "The mechanism-claim source-verification rule (#949) is present verbatim
     in both plan-review templates' raw source.") to say "…in all four plan- and code-review
     templates' raw source." (adjust the wording to read naturally; the `#949` reference stays).
  2. Add a new test function `test_reviewer_self_id_removed_from_templates`, placed directly after
     `test_deleted_prose_stays_deleted` (which it mirrors in style) and before
     `test_kept_prose_stays_kept`, with this body:
     ```python
     def test_reviewer_self_id_removed_from_templates() -> None:
         """reviewer_self_id was removed from the three templates that used to carry it (#989)."""
         for name in ["review-discussion", "review-plan-holistic", "review-plan-batch"]:
             source = _read_template_source(name)
             assert "reviewer_self_id" not in source, (
                 f"{name} still contains reviewer_self_id"
             )
         print("PASS test_reviewer_self_id_removed_from_templates")
     ```
     Register the new function in `main()`'s `tests` list, placed directly after
     `test_deleted_prose_stays_deleted` in that list (matching its placement in the file above),
     before `test_kept_prose_stays_kept`.
- **Commit:** `test(review): assert mechanism-claim rule on code templates and reviewer_self_id removal`

## Batch Tests

`verify:` runs `run-all.py --only test-review-common.py test-review-templates.py` — the two files
this batch edits, both already unit-testing the templates/backend this batch changes. No other
test file references `reviewer_self_id` or the mechanism-claim rule text, so this scope is
complete. `test-review-common.py`'s two deleted blocks were the only `reviewer_self_id`-specific
assertions in that file (confirmed by grep across `plugins/mill/unit_tests/` before writing this
plan — the only other matches are the two blocks this batch's Card 7 removes and the ones Card 8
adds in `test-review-templates.py`).
