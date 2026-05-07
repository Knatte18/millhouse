# Review: 28 (A) — review-plan robustness — 04-skill-md-fixes

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 04-skill-md-fixes
date: 2026-05-07
```

## Findings

### [BLOCKING] Card 13 misses a third `--skip-validate` occurrence that becomes inconsistent after the fix

**Step:** Card 13
**Issue:** Step 1.5 contains the sentence "mill-plan passes `--skip-validate` only when the fix table instructs it — see the `wiki-config-mutation` row." After Card 13 updates the fix-table row to use `--skip-check wiki-config-mutation`, this sentence is factually wrong — the fix table no longer instructs `--skip-validate`, making the cross-reference misleading and potentially causing a future mill-plan session to issue the wrong flag.
**Fix:** Card 13's requirements must add a third change: update (or remove) the sentence "mill-plan passes `--skip-validate` only when the fix table instructs it — see the `wiki-config-mutation` row." A correct replacement is "mill-plan passes `--skip-check wiki-config-mutation` only when the fix table instructs it — see the `wiki-config-mutation` row." The pipeline-level sentence ("pass `--skip-validate` to the CLI and skip step 1.5 entirely") is still correct and must remain untouched.

## Verdict

REQUEST_CHANGES
Card 13 leaves one inconsistent `--skip-validate` reference that the batch claims to fix.