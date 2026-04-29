# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — 01-foundation

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 01-foundation
date: 2026-04-29
```

## Findings

### [NIT] Card 5: old `upsert` test cases not explicitly retired
**Step:** Card 5
**Issue:** Requirements list new `upsert_split` tests but don't say to remove/replace the existing `upsert`-based tests. The import `from _gitignore import END, STANDARD_ENTRIES, START, upsert` fails the moment Card 5 removes all three symbols; the verify catches it but an implementer could add new tests without clearing the old imports.
**Fix:** Add to Card 5 requirements: "Replace the entire import line; surviving symbols are `END`, `START`, `GLOB_ENTRIES`, `ANCHORED_ENTRIES`, `upsert_split`. Remove all existing test functions that call `upsert` or reference `STANDARD_ENTRIES`."

### [NIT] Card 3: `ActiveError` propagates unwrapped for malformed-marker case
**Step:** Card 3
**Issue:** When the dir exists but `.millhouse/active.slug.md` is missing or malformed, `_active.read_slug` raises `ActiveError`. The spec names only `ActiveWorktreeNotFound` (absent dir) and `ActiveWorktreeSlugMismatch` (wrong slug); the malformed-marker case slips through as a third, uncontracted exception type.
**Fix:** Add: "If `_active.read_slug` raises `ActiveError` (marker absent or corrupt inside an existing dir), re-raise as `ActiveWorktreeNotFound` with the original exception chained."

### [NIT] Card 1: defensive `Path(repo_root)` cast silently dropped
**Step:** Card 1
**Issue:** Current body opens with `repo_root = Path(repo_root)` for robustness; the new body omits it. No tests break (CLI and test helper already pass `Path`), but the removal is unannounced and could confuse a reviewer comparing before/after.
**Fix:** Note explicitly in requirements: "Drop `repo_root = Path(repo_root)` — callers always pass `Path` objects (see `_main`, `_check` helper)."

### [NIT] Card 5: `upsert` removal creates silent runtime breakage between batches
**Step:** Card 5 / batch sequencing
**Issue:** Scripts updated in batch 04 (spawn, claim, etc.) still call `upsert` at import time; removing it in batch 01 produces `ImportError` at runtime for batches 02–03. `run-all.py` won't catch this because it tests helpers, not scripts.
**Fix:** Either add a one-liner tombstone (`upsert = None  # removed; callers updated in batch 04`) or acknowledge in the batch scope note that production scripts are intentionally broken until batch 04 lands.

## Verdict

APPROVE
Four NITs, all low-risk; plan is internally consistent and verify catches any implementation oversight.