MILL_REVIEW_BEGIN
# Review: _plan_validate context-completeness: further false-positive/false-negative gaps, round 3 — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-23
```

## Findings

### [BLOCKING:design] Card 4's call-site simplification breaks an existing cache-count test
**Location:** batch 1 / card 4, `_check_context_completeness` symbol-branch call site.
**Issue:** Card 4 replaces the current cache-check-then-call wrapper (`plugins/mill/scripts/_plan_validate.py:2997-3002`: `if search_key in search_cache: ... else: matches, producing_root = _resolve_symbol_files(...)`) with an unconditional `matches = _resolve_symbol_files(search_key, candidate_files, search_cache)` on every occurrence. `_resolve_symbol_files` itself still short-circuits its filesystem walk via its own `if search_key in cache: return cache[search_key]`, but the outer **function object** is now invoked once per token occurrence, not once per distinct key. `test_check_context_completeness_symbol_cache_invoked_once_per_key` (`plugins/mill/unit_tests/test-plan-validate.py:3976-4036`) monkey-patches `_plan_validate._resolve_symbol_files` with a counting wrapper and asserts `call_count[0] == 1` after two cards ("alpha", "beta") both reference `SaveState`; after card 4's change this becomes `call_count[0] == 2`, failing verify. This test is not in card 4's 6-function deletion list, and card 5's own text explicitly names "a `_resolve_symbol_files` cache-behavior assertion" as a migration target but only edits the fixture (to keep resolution working under the narrowed scope) — it never revisits the `call_count` assertion, which fails independent of the fixture.
**Fix:** Either keep a cheap caller-side `if search_key in search_cache` guard so the outer call still happens once per key, or have card 5 explicitly update `test_check_context_completeness_symbol_cache_invoked_once_per_key`'s assertion (and docstring) to the new once-per-occurrence semantics.

### [NIT:consistency] `path_to_token`'s "first-seen wins" claim is actually alphabetical-first
**Location:** batch 1 / card 4, `_compute_plan_wide_cited_files` / `path_to_token` construction.
**Issue:** `cited_files_map` is populated by iterating `sorted(raw_tokens)`, so `path_to_token.setdefault(path, token)` — built later from `cited_files_map.items()` — actually keeps whichever citing token sorts alphabetically first among duplicate-path spellings, not whichever card cited it first in plan order. The comment "(first-seen wins on a rare duplicate-path collision)" implies encounter order, which could mislead a future maintainer about which token wins.
**Fix:** Reword the comment to "alphabetically-first token wins" (or sort by (batch_index, card_number) instead if plan-order priority is actually intended).

## Verdict

REQUEST_CHANGES
Card 4's redundant-pre-check removal breaks an existing symbol-cache unit test that card 5 doesn't fix.
MILL_REVIEW_END
