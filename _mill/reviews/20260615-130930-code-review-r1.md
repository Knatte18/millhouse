I have enough to write the review. Let me summarize my findings:

1. **mill-fold SKILL.md lines 29/37** — "runs the phase guard" wording is stale. The guard is now unclaimed-only, not phase-based. Card 5 requirement (3) retitled the section but didn't explicitly cover these two inline step-description references. The plan's Shared Decision says all phase-guard references should be updated. This is a NIT — it's a doc inconsistency, not a code bug.

2. **`_parse.py` does not include `deferred` in its returned dicts** — but `millpy-fold.py` uses `wiki.list_tasks_brief()` (the client/store API), which does include `deferred`. No issue.

3. **Card 3 requirement (5d)** — card says `_fetch_one=` but the guard fires before `fetch_one`, so `_fetch_one` is passed but irrelevant. The test is structurally correct though — the `_make_fake_fetch_one` was included unnecessarily but doesn't cause a test failure. Not a bug.

4. Everything else looks aligned — the allowlist predicate, `.get()` usage, removal of `LOCKED_FOLD_PHASES`, refusal message format, CLAUDE.md update, all four doc surfaces.

The "phase guard" wording residue in mill-fold SKILL.md lines 29/37 is the only imperfection, and it's a NIT — the guard section itself is correctly titled, just the cross-reference label in step descriptions wasn't updated.

MILL_REVIEW_BEGIN
# Review: Fix mill-ghissues-to-tasks to refuse fold-ins into done and deferred tasks — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-15
```

## Findings

### [NIT] Stale "phase guard" wording in mill-fold SKILL step descriptions

**Location:** `plugins/mill/skills/mill-fold/SKILL.md:29,37`
**Issue:** Both invocation-form step-1 descriptions still say "runs the phase guard"; the guard section itself was correctly retitled to "## Unclaimed-only guard" (line 41) but these two cross-references were not updated.
**Fix:** Replace "runs the phase guard" with "runs the unclaimed-only guard" at both lines.

## Verdict

APPROVE
One minor doc wording residue; all code, tests, and policy surfaces are correctly implemented.
MILL_REVIEW_END