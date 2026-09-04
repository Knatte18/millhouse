All 3 cards (of 3 declared) are committed, verify passes, and the working tree is clean.

Summary of work in `/home/knatte/Code/millhouse/wts/plan-validate-context-completeness-missing-symbol-refs`:
- `plugins/mill/scripts/_plan_validate.py` — added `_SYMBOL_SEARCH_EXTENSIONS`/`_SYMBOL_SEARCH_DENYLIST_DIRS` constants, `_symbol_candidate_shape`, `_resolve_symbol_files`, `_covered_by_own_refs` helpers; wired the symbol branch into `_check_context_completeness`'s per-token loop (with a caller-side `search_cache` check, corrected in card 3 to make the shared cache actually save invocation count, not just filesystem-walk count); updated module/function docstrings.
- `plugins/mill/unit_tests/test-plan-validate.py` — added 16 new tests (8 core + 8 edge-case/regression) covering clean/dirty resolution, zero/ambiguous matches, call-site suffix stripping, lowercase shape-gate exclusion, dotted trailing-segment resolution, root-precedence regression, cache-invocation-count regression, and prohibition/citation exemptions; registered all in `main()`'s dispatch list; updated the module docstring's check-coverage summary.
- `_mill/plan/01-symbol-reference-check.md` — amended card 3's `Context:`/`Edits:` lists (moved `_plan_validate.py` to `Edits:`) and added an implementer note explaining why a small wiring fix was needed there, per the "file discovered mid-card" protocol.

Commits (all pushed): `5eca04a9`, `c443cd3a`, `b9cfd27c` (plan edit), `41591862`. Final `verify:` run passed all tests.

```json
{"status":"success","commit_sha":"41591862fa161645cc04e299ee429d0eefebead7","session_id":"fc8b2a94-287a-4809-b4a4-de38d92a799a","cards_done":[1,2,3]}
```
