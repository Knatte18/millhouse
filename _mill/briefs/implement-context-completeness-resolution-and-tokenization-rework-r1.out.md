All 6 cards of batch 01-context-completeness-resolution-and-tokenization-rework completed and committed (6 of 6 cards committed).

Card-by-card summary:
- Card 1 (#1119): widened `_compute_declared_symbols_union` in `plugins/mill/scripts/_plan_validate.py` with a new `_RE_INLINE_ASSIGN_DECLARATION` regex to capture inline `modifier+ identifier = value` declarations.
- Card 2 (#1115): added `_RE_LEADING_ASSIGN_PREFIX` stripping in `_symbol_candidate_shape` so assignment-expression tokens like `x = mod.get_value(args)` resolve via their RHS.
- Card 3 (#1116, #1122): rewrote `_is_literal_enumeration_exempt` to use a self-inclusive strict non-shaped-majority tally instead of "any other non-shaped sibling"; renamed/updated one existing test whose outcome flips under the new rule, added 3 new tests.
- Card 4 (resolution-scope-rework): added `_compute_plan_wide_cited_files`; rewrote `_resolve_symbol_files` to search only the plan-wide cited-files set (dropped `project_root`/`root`/`git_root` params and the `os.walk`); threaded `cited_files_map` through `_check_context_completeness` and `run()`; deleted the now-dead `_SYMBOL_SEARCH_DENYLIST_DIRS`/`_SYMBOL_SEARCH_OUT_OF_SCOPE_DIRS` constants and 7 tests whose outcomes depended solely on deleted mechanisms; added 4 new resolution-scope tests.
- Card 5: migrated every remaining symbol-branch test (41 tests) whose fixture's declaring file wasn't cited anywhere in the plan by adding a second (or, for 2 already-two-batch tests, a third) citing-only batch, preserving each test's original assertions.
- Card 6 (line-join-refactor): replaced the per-physical-line backtick tokenization loop in `_check_context_completeness` with a per-run joined-text pass (fence-delimiter lines always excluded from run membership); updated `_clause_bounds`'s signature with an `extra_boundaries` keyword and threaded `line_boundaries` through `_is_non_dependency_negation_exempt`/`_is_contrast_citation_exempt`; added 3 new regression tests for the cross-line backtick-span bug and its two guard conditions.

Commits (3 total — combined per the brief's "necessarily touch the same file(s)" allowance, each named using the later card's `Commit:` message):
1. `83c04c33` — cards 1, 2, 3
2. `9c62359b` — cards 4, 5
3. `8f64bb3e` (HEAD, full SHA `8f64bb3e0470ee9a31bb9b20ac5dff05307418eb`) — card 6

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py` passes cleanly (all tests green) after each commit and at the final state. `git status --porcelain --untracked-files=no` is clean.

Files touched: `plugins/mill/scripts/_plan_validate.py`, `plugins/mill/unit_tests/test-plan-validate.py`.

{"status":"success","commit_sha":"8f64bb3e0470ee9a31bb9b20ac5dff05307418eb","session_id":"31a40564-8acb-49fa-8c5c-25b39eba0b52","cards_done":[1,2,3,4,5,6]}
