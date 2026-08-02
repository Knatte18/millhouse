# Batch: plan-validate-line-field

```yaml
task: Improve diagnosability of plan-validate errors and finalize verify-replay failures
batch: plan-validate-line-field
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
depends-on: []
```

## Batch Scope

Fixes Gap 1 (#772): `_check_context_completeness`'s emitted error dicts name the batch and card but not the offending source line, so tracing a false positive back to the actual malformed `Requirements:` line requires an ad-hoc re-run of the same regex. This batch adds a `line` field carrying the raw offending line (verbatim, stripped) and updates the mill-plan validator-fixer table to mention it. Test coverage for both the new field and the odd-backtick-count false-positive mechanism lives in the next batch — split out because `test-plan-validate.py` (252KB) alone pushes this batch's combined context estimate over `pipeline.max_batch_context_tokens`. This batch is otherwise independent of every other batch in this plan — see the overview's "two unrelated gaps share one plan" Shared Decision.

## Cards

### Card 1: Add `line` field to `_check_context_completeness` error dicts

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_check_context_completeness` (`_plan_validate.py:1471`), the per-line loop `for line in requirements_lines:` (line 1536) already has `line` in scope when the error dict is built at the `errors.append({...})` call (lines 1579-1589). Add a `"line": line.strip()` key to that dict (stripped of leading/trailing whitespace, otherwise verbatim, no length cap — do NOT compute an absolute file line number; see `_mill/discussion.md`'s `gap1-line-field-not-line-number` Decision). Update the function's docstring line reading `Error dict shape: \`\`{check, batch, card, path, message}\`\`.` to `Error dict shape: \`\`{check, batch, card, path, message, line}\`\`.`.
- **Commit:** `fix(plan-validate): add line field to context-completeness error dicts`

### Card 2: Document the new `line` field in mill-plan's validator-fixer table

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the validator-fixer-remedy table's `context-completeness` row (`plugins/mill/skills/mill-plan/SKILL.md:267`), append a sentence noting the error dict's `line` field carries the exact offending `Requirements:` line (stripped) so the autonomous fixer can locate it directly without re-deriving it from the batch file. Keep the row's existing remedy text (the "add to Context:" instruction and its parenthetical caveat) unchanged — only append the new sentence at the end of the cell.
- **Commit:** `docs(mill-plan): document context-completeness line field in fixer table`

## Batch Tests

`verify:` runs `run-all.py --only test-plan-validate.py`, the sole test file covering `_plan_validate.py`'s `_check_context_completeness` check that this batch modifies.
