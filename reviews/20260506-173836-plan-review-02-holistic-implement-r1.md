# Review: 14 (D) — Holistic-fix agent for cross-batch funn (conflicts with 15) — 02-holistic-implement

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-holistic-implement
date: 2026-05-06
```

## Findings

### [BLOCKING] `--review-file` described as "required" breaks test_4
**Step:** Card 5, Step 1
**Issue:** The plan says "Add `--review-file` (required, type str)" — an implementer translates this to `required=True` in argparse. With `required=True`, `parse_args([])` calls `sys.exit(2)` raising `SystemExit`, so test_4 (`main([])` → rc==1) fails with an uncaught exception, not a return value.
**Fix:** Replace "(required, type str)" with "(type str, default None)" to make the intent explicit; the manual `if args.review_file is None` check already handles enforcement.

### [BLOCKING] Card 6 replacement spec omits `review.code.holistic: true` gate
**Step:** Card 6, Requirements items 1–8
**Issue:** The existing section opens with "and only if `review.code.holistic: true`". The 8 replacement items begin directly with reading `holistic_rounds` and starting the loop — no outer gate. An implementer writing the replacement per spec omits the condition entirely, so holistic review runs even when `holistic: false`.
**Fix:** Add a requirement 0 (before the loop): "Open with the existing outer guard — only execute this section if `review.code.holistic` is truthy in config."

### [NIT] Step 20 contradicts shared decision `from-import-style`
**Step:** Card 5, Step 20
**Issue:** Decision `from-import-style` says use `from _implementer_common import _forward_output` and call as `_forward_output(output)`. Step 20 says `return _implementer_common._forward_output(output)` — attribute-access style, which requires `import _implementer_common` (not the from-import).
**Fix:** Align step 20 with the decision: `return _forward_output(output)`, and clarify the import block entry as `from _implementer_common import _forward_output`.

## Verdict

REQUEST_CHANGES
Two blockers: `required=True` breaks test_4; missing `holistic: true` gate causes unconditional holistic review.