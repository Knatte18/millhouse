# Batch: reviewer-self-id-templates

```yaml
task: 'Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran'
batch: reviewer-self-id-templates
number: 4
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-templates.py
depends-on: []
```

## Batch Scope

This batch adds a new, optional `reviewer_self_id:` field to the three discussion/plan review prompt templates and documents it in the schema doc. It has no dependency on any other batch — it is a pure prompt/doc addition, independent of the `--reviewer` flag machinery in batches `discussion-review-cli`/`plan-review-cli`. `_render.py`'s `_TOKEN_RE = re.compile(r"<([A-Z][A-Z0-9_]*)>")` hard-fails rendering with `KeyError` on any unresolved `<UPPERCASE_TOKEN>`-shaped placeholder, so every new example line in these three templates MUST use lowercase, non-token placeholder text (matching the style of the existing `reviewed_file: <artefact reference>` / `date: <UTC YYYY-MM-DD>` lines) — never an uppercase `<TOKEN>` shape, which would only work if it were a real `render_prompt` kwarg (it is not). `plugins/mill/unit_tests/test-review-templates.py::test_all_templates_render` already renders all five real templates (including all three this batch edits) against the real, unresolved token set every backend supplies specifically to guard against this exact class of mistake — no new test needs to be added for it (see batch `unit-tests`'s Batch Tests note); this batch's own `verify:` re-runs that existing guard test directly.

## Cards

### Card 9: `reviewer_self_id` field in `review-discussion.md`

- **Context:**
  - `plugins/mill/scripts/_render.py`
- **Edits:**
  - `plugins/mill/templates/review-discussion.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the yaml metadata example block (currently lines 43-48, inside the fenced ` ``` ` output-format block), add a new line `reviewer_self_id: <your own model self-identification, if known>` immediately after `reviewer_model: <REVIEWER_MODEL>` (line 45) and before `reviewed_file: <artefact reference>` (line 46). Use exactly this lowercase, non-token placeholder text. Add one short sentence instructing the reviewer to independently state, in the `reviewer_self_id:` field, what model/version it believes itself to be — as its own best-effort assessment, distinct from the `reviewer_model:` value already dictated to it on line 3 (`Reviewer model: **<REVIEWER_MODEL>**`). Place this sentence directly above the `## Output format — STRICT` heading (line 31), as a short new paragraph, not inline with any existing sentence.
- **Commit:** `mill: add reviewer_self_id field to review-discussion.md template`

### Card 10: `reviewer_self_id` field in `review-plan-batch.md`

- **Context:**
  - `plugins/mill/scripts/_render.py`
- **Edits:**
  - `plugins/mill/templates/review-plan-batch.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the yaml metadata example block (currently lines 57-62), add `reviewer_self_id: <your own model self-identification, if known>` immediately after `reviewer_model: <REVIEWER_MODEL>` (line 59) and before `reviewed_file: <BATCH_NAME>` (line 60). Same lowercase, non-token placeholder rule as Card 9. Add the same one-sentence instruction as Card 9, placed directly above the `## Output format — STRICT` heading (line 47).
- **Commit:** `mill: add reviewer_self_id field to review-plan-batch.md template`

### Card 11: `reviewer_self_id` field in `review-plan-holistic.md`

- **Context:**
  - `plugins/mill/scripts/_render.py`
- **Edits:**
  - `plugins/mill/templates/review-plan-holistic.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the yaml metadata example block (currently lines 54-59), add `reviewer_self_id: <your own model self-identification, if known>` immediately after `reviewer_model: <REVIEWER_MODEL>` (line 56) and before `reviewed_file: plan/` (line 57). Same lowercase, non-token placeholder rule as Card 9. Add the same one-sentence instruction as Card 9, placed directly above the `## Output format — STRICT` heading (line 44).
- **Commit:** `mill: add reviewer_self_id field to review-plan-holistic.md template`

### Card 12: document `reviewer_self_id` in `review-output.schema.md`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/templates/review-output.schema.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `reviewer_self_id: <optional, reviewer-reported self-identification>` to the fenced "File format" worked example block (currently lines 9-17), immediately after `reviewer_model: <reviewer name from config, e.g. sonnetmax>` (line 14) and before `reviewed_file: <path to the artefact that was reviewed>` (line 15) — the field-ordering convention Cards 9-11 also follow. Add a new row to the "Metadata block fields" table (currently lines 44-49), immediately after the `reviewer_model` row: `| `reviewer_self_id` | string | no | optional, reviewer-self-reported model identification; unverified |`. Add a one-line note directly below the table distinguishing `reviewer_self_id` (unverified, reviewer-reported, best-effort, present only in the discussion and plan review templates, never validated by `parse_verdict()`, the parser defined in `_review_common.py`) from `reviewer_model` (orchestrator-supplied, dictated to the reviewer up front, and the field `_review_common.apply_actual_model_override()` — invoked via the CLIs' `--actual-model` flag — can rewrite after the fact).
- **Commit:** `mill: document reviewer_self_id field in review-output.schema.md`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-review-templates.py::test_all_templates_render`, the existing test that renders all five real on-disk templates (including all three this batch edits) against the exact token set each backend supplies, specifically to catch an accidentally introduced unresolved `<UPPERCASE>` token. This is the authoritative guard for the placeholder-text constraint called out in Batch Scope above — no new test file is needed for this batch.
