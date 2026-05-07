# Batch: test-fixtures

```yaml
task: 24 (A) — mill-misc-fixes
batch: test-fixtures
number: 1
cards: 4
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Updates the three remaining production-relevant assets that still reference the legacy batch-card field names `Reads:` / `Modifies:`. After this batch, every plan-validation surface (validator regex, `parse_batch_refs`, the `plan-batch.md` template, the test fixtures, the integration sample, the holistic-review reviewer prompt) speaks the same canonical vocabulary `Context:` / `Edits:` / `Creates:` / `Deletes:`. Bug A's mechanism — `_make_batch_file` generating cards the validator silently does not parse, leading to stub-queue exhaustion in tests 4 and 5 — is fixed by Card 1. Tests 6 and 7 are fixed by Card 2 (`effort` kwarg now in the assertion). Cards 3 and 4 finish the field-rename sweep so no stale corner remains for a future bug report. The verify command (`run-all.py`) is the regression net: pre-batch `1 of 47` test files fails (`test-review-plan-flow.py` — 4 of its test cases); post-batch all 47 test files pass.

## Cards

### Card 1: Rename Reads/Modifies to Context/Edits in `_make_batch_file`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_make_batch_file` (lines 64-85 of `test-review-plan-flow.py`), rename the bullet `- **Reads:** {reads_part}` to `- **Context:** {reads_part}` (single-line form preserved) and rename `- **Modifies:** none` to `- **Edits:** none`. Update the docstring inside `_make_batch_file` (line 71) from `"""Return batch file text (single-line Reads:/Creates:/Deletes: form)."""` to `"""Return batch file text (single-line Context:/Edits:/Creates:/Deletes: form)."""`. Do NOT rename the function's `reads` parameter or the local `reads_part` variable — those are internal names and renaming them is out of scope. Do NOT change the `Creates:` or `Deletes:` bullets or the YAML frontmatter inside the f-string. The canonical field names are confirmed by `_review_common.py` line 278 (`r"^-\s*\*\*(Context|Edits|Creates|Deletes):\*\*(?P<inline>.*)$"`).
- **Commit:** `fix(tests): rename Reads/Modifies to Context/Edits in _make_batch_file`

### Card 2: Add `effort: None` to test 6 and test 7 retry-kwargs assertions

- **Context:**
  - `plugins/mill/scripts/_reviewer_test_stub.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-review-plan-flow.py`, locate the assertion in test 6 (around line 442) that reads `assert retry_kwargs == {"session_id": "sid-1", "resume": True, "timeout": None}, (` and update the expected dict to `{"session_id": "sid-1", "resume": True, "timeout": None, "effort": None}`. Do the same in test 7 (around line 487) for the holistic-retry assertion `assert retry_kwargs == {"session_id": "sid-2", "resume": True, "timeout": None}, (` → `{"session_id": "sid-2", "resume": True, "timeout": None, "effort": None}`. The `effort: None` key reflects the `_reviewer_test_stub.run` signature at `_reviewer_test_stub.py` line 72-74 which captures `effort` (default None) into kwargs. Do not modify any other test or change the `_reviewer_test_stub` module.
- **Commit:** `fix(tests): include effort kwarg in test 6/7 retry-kwargs assertions`

### Card 3: Update integration fixture `01-core.md` to canonical field names

- **Context:**
  - `plugins/mill/templates/plan-batch.md`
- **Edits:**
  - `plugins/mill/integration_tests/fixtures/sample-plan/01-core.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `01-core.md` lines 25-26, replace `- **Modifies:** scripts/_render.py` with `- **Edits:** \`scripts/_render.py\`` and `- **Reads:** scripts/_render.py` with `- **Context:** \`scripts/_render.py\``. Backtick-wrap the path on each line per the canonical batch-card format defined by `plan-batch.md` (single backtick around the path). Do not modify any other line in the file.
- **Commit:** `fix(integration): rename Reads/Modifies to Context/Edits in sample-plan fixture`

### Card 4: Update `review-code-holistic.md` prose to canonical field names

- **Context:**
  - `plugins/mill/templates/plan-batch.md`
- **Edits:**
  - `plugins/mill/templates/review-code-holistic.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `review-code-holistic.md` line 18, replace the substring ``Reads:`/`Modifies:`/`Creates:`` with ``Context:`/`Edits:`/`Creates:``. Preserve the surrounding bullet text exactly (`every batch's cards are realised; every file listed across all batches' ... is present in the source files provided.`). The reviewer-prompt text must reference the canonical field names so the holistic-review LLM checks the right fields.
- **Commit:** `fix(templates): rename Reads/Modifies to Context/Edits in review-code-holistic prose`

## Batch Tests

The verify command `python plugins/mill/unit_tests/run-all.py` is the canonical regression net. Pre-batch failure profile: `1 of 47` test files fails — `test-review-plan-flow.py` — with 4 failing test cases (tests 4, 5, 6, 7). Post-batch expectation: 47/47 test files passing. The verify also catches any unintended regression introduced by Cards 3 or 4 (which alter integration/template assets that other tests indirectly depend on, e.g. `test-review-code-flow.py` reads the same fixture root). The integration_tests directory is not part of `run-all.py`'s scope (those are `integration_tests/` and run separately) — Card 3's fixture change is verified by the implementer reading the rendered file once.
