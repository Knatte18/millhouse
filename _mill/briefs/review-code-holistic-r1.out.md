MILL_REVIEW_BEGIN
# Review: mill-plan/mill-start planning-process gaps, round 2 — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-21
```

## Findings

### [NIT:consistency] cross-batch-build-break duplicates existing path-shape heuristic
**Location:** `plugins/mill/scripts/_plan_validate.py:4100-4111` (new `_CROSS_BATCH_BUILD_BREAK_FILE_EXTENSIONS` / `_cross_batch_build_break_looks_like_file`) vs `plugins/mill/scripts/_plan_validate.py:1819-1820,1912,2697` (pre-existing `_PATH_CANDIDATE_EXTENSIONS` + `"/" in token or token.endswith(...)`)
**Issue:** Card 13 introduces a second, independently-maintained "is this backtick token a file path" heuristic (different extension list, added case-insensitivity) in the same module that already has this exact heuristic for `context-completeness`'s path-vs-symbol classification; the two definitions can silently drift (e.g. `.rs`/`.java` are in the new list but not the old one).
**Fix:** Extend/reuse `_PATH_CANDIDATE_EXTENSIONS` (or a shared superset) for both checks instead of maintaining a second tuple + predicate.

### [NIT:scope] test fixture omits the per-batch frontmatter depends-on card 14 specified
**Location:** `plugins/mill/unit_tests/test-plan-validate-cross-batch-build-break.py:112-138` (`test_does_not_fire_with_depends_on_edge`)
**Issue:** Batch 4 card 14 explicitly requires scenario 2 to set `depends-on: ["alpha"]` on "both the per-batch file's own frontmatter depends-on: and the overview Batch Index entry"; `_write_batch_file` writes no frontmatter at all, so only the overview side is set. Harmless here since `_check_cross_batch_build_break` reads only the overview's Batch Index (via `extract_batch_index`/`_compute_transitive_ancestors`), never per-batch frontmatter, but it's a literal deviation from the card's stated fixture shape.
**Fix:** Add a minimal `depends-on:` frontmatter block to `beta`'s batch file in this scenario, or drop the card's dual-frontmatter instruction if it was never meant to bind for this check.

## Verdict

APPROVE
All four batches match the plan; integration, cross-batch threading, and tests are correct; only two cosmetic NITs found.
MILL_REVIEW_END
