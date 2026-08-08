All 6 cards (20–25) committed, matching the batch's declared 6 cards exactly. 6 of 6 cards committed — all complete.

Files touched (all absolute paths under `/home/knatte/Code/millhouse/wts/review-gap-classification-by-kind`):
- `plugins/mill/templates/review-discussion.md`
- `plugins/mill/templates/review-plan-batch.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/templates/review-code-batch.md`
- `plugins/mill/templates/review-code-holistic.md`
- `plugins/mill/templates/review-output.schema.md`
- `mill-config.yaml`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-review-templates.py`
- `plugins/mill/unit_tests/test-review-output-contract.py`

Note: `uvx ruff check` on the two edited test files flagged a pre-existing `RUF100 Unused noqa: E402` on the `import _review_common` line — present before this batch's edits, unrelated to the changes made here, left as-is per scope discipline.

{"status":"success","commit_sha":"0c4fcf1112875ef776470b17a080f0df0cdba3cd","session_id":"90e9dfe3-cf37-48ec-9aca-b335974d3e37","cards_done":[20,21,22,23,24,25]}
