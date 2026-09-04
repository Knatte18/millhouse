MILL_REVIEW_BEGIN
# Review: mill-go: concurrency, silently-ignored fields, and bookkeeping bugs in execution/handoff

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] #906 reuse of `_check_card_numbering` cannot detect the collision it's meant to catch
**Section:** #906 scope bullet + Decision `906-reuse-existing-plan-validate-helper` + Testing (#906).
**Issue:** Verified `_plan_validate.py:908-974` — `_check_card_numbering` returns only `errors: list[dict]`, built from a cross-batch duplicate scan (`card_to_batches[n]` with `len(batch_set) > 1`). The local `card_to_batches`/`per_batch` dicts are never returned. Calling this function pre-insertion, on the unmodified on-disk set, as the discussion prescribes, cannot tell whether candidate `N` is already used by a *different* batch: since `N` isn't yet written anywhere in the target batch, it appears in at most one batch on disk, so `len(batch_set)` is never `>1` for it and no error is ever produced for it — the exact check the design needs ("does N belong to another batch") is structurally unanswerable from this function's return value.
**Fix:** Either have the Builder call `_parse_cards` per batch file directly to build the used-numbers set itself, or add a genuinely new (returned) lookup surface to `_plan_validate.py` — and update the Decision's rationale/rejected-alternatives accordingly, since "reuses tested logic ... exactly as-is" as currently written does not achieve the stated goal.

## Verdict

REQUEST_CHANGES
#906's helper-reuse design cannot detect the cross-batch collision it claims to check for.
MILL_REVIEW_END
