# Review: 12 (C) — Restructure hub junction layout — 01-gitignore-api

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 01-gitignore-api
date: 2026-05-06
```

## Findings

### [NIT] `tests` list reference doesn't exist in current `main()`
**Step:** Card 2, requirement 7
**Issue:** Requirement 7 says "Update the `main()` runner's `tests` list" but the current `main()` uses inline sequential blocks with no list structure — there's nothing to update.
**Fix:** Rephrase to "Rewrite `main()` to run only the new/updated test functions; remove all old `upsert_split` test blocks."

## Verdict

APPROVE
Batch is well-scoped and self-consistent; requirements are specific; context fields correct; test coverage covers all stated paths.