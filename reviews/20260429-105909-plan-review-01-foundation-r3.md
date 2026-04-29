# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — 01-foundation

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 01-foundation
date: 2026-04-29
```

## Findings

### [NIT] Card 3: missing-marker edge case absent from spec and tests
**Step:** Card 3 — `resolve_active_worktree`
**Issue:** The plan specifies tests for "missing dir" and "marker-slug-mismatch" but not the case where the directory and `.millhouse/` subdir exist but `active.slug.md` is absent. `_active.read_slug` raises `ActiveError` there, which propagates uncaught — neither `ActiveWorktreeNotFound` nor `ActiveWorktreeSlugMismatch`.
**Fix:** Either document the propagation as intentional ("`ActiveError` escapes for missing-marker state"), or add a `try/except ActiveError → raise ActiveWorktreeNotFound` guard and cover it in tests.

### [NIT] Twin invariant test — "module-name lines" is underspecified
**Step:** Card 1 — twin test description
**Issue:** "Strips docstrings and module-name lines" is ambiguous; neither `_sibling.py` file has module-name variable assignments, so only the module-level docstring differs between the two files.
**Fix:** Clarify as "strip the module-level docstring (first triple-quoted string)"; the current wording risks implementers over-stripping or misunderstanding what to remove.

## Verdict

APPROVE
Plan is internally consistent, correctly scoped to pure helpers, and cross-card test dependencies (Card 1 breaks test-paths.py until Card 4 migrates fixtures) are explicitly documented and handled within batch verify.