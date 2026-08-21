## Pushback on round 4's Card 10 fix (revised, not applied verbatim)

Round 4's BLOCKING finding "`Card 10 uses resolve_ref_paths/ReviewError without _review_common.py
in Context:`" (`20260821-102729-plan-review-r4.md`) was accepted and fixed by adding
`plugins/mill/scripts/_review_common.py` to Batch 2 Card 10's `Context:` list (commit `2505862b`,
round-4 fixer report `20260821-102825-plan-fix-r4.md`).

Re-running Step 1.5's pre-review validator for round 5 surfaced a real, confirmed harm from that fix:

```
{"check": "batch-oversized", "batch": "02-validator-checks-lang-gitignore", "card": null,
 "path": null, "message": "batch context ~135746 tokens (cap 120000)"}
```

Measured directly: `_plan_validate.py` = 30465 tokens, `test-plan-validate.py` = 74469 tokens
(sum 104934 — Card 10's own `Edits:` already, alone, consume 87% of the 120000 cap), plus
`_review_common.py` = 30812 tokens = 135746 total. Since Card 10 must edit both large files
regardless of which batch it lives in, **no batch split resolves this** — any batch containing
Card 10 plus a full-file `_review_common.py` Context breaches the cap by the same margin.

Per the `mill-receiving-review` decision tree's legitimate-pushback rule #2 ("Fix breaks
something — identify what breaks"), reverting the Context: addition is justified: the underlying
concern (implementer needs `resolve_ref_paths`'s exact signature) is fully addressed without it —
Card 10's Requirements now inline the complete call signature, kwarg-for-kwarg, plus `ReviewError`'s
shape and `resolve_ref_paths`'s raise/return semantics, mirroring the same "no need to read the
source, exact usage given inline" precedent Card 8 already establishes in this same batch for
`_compute_transitive_ancestors`/`_plan_dag.py`.

## Fixed

- Card 10's `Context:` reverted to `none`; Requirements now inline `resolve_ref_paths`'s and
  `ReviewError`'s exact call/raise shape, with an explicit note on why `_review_common.py` is
  excluded from `Context:` (the batch-oversized math above).

## Pushed Back

- Round 4's literal remedy ("add `_review_common.py` to Card 10's `Context:`") — superseded by the
  inline-signature approach above, which resolves the same underlying concern without breaching
  `batch-oversized`.
