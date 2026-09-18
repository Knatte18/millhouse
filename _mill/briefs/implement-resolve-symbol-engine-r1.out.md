Confirmed: both card commits present, matching the batch's declared `Commit:` messages exactly (2 of 2 cards committed — full completion, no cards remaining). Working tree is clean, `verify:` passed cleanly.

{"status":"success","commit_sha":"9ee1e838883d5721f2ee32995b8e79bf63e2115f","session_id":"f1b26928-7ec7-4101-8adc-91ef6f4592ca","cards_done":[1,2]}

Files touched: `/home/knatte/Code/millhouse/wts/plan-validate-context-completeness-symbol-branch-bugs/plugins/mill/scripts/_plan_validate.py` — added `_SYMBOL_SEARCH_OUT_OF_SCOPE_DIRS`, rewrote `_resolve_symbol_files`'s matching engine to use per-extension declaration-form regexes (`.go`/`.cs`/`.py`/`.ts`) with solution-scope directory pruning, added `_filter_matches_by_qualifier` and its `_RE_GO_PACKAGE`/`_RE_NAMESPACE` helpers, and changed `_symbol_candidate_shape`'s return type plus both `_check_context_completeness` call sites to thread the qualifier through to the new disambiguation logic.

{"status":"success","commit_sha":"9ee1e838883d5721f2ee32995b8e79bf63e2115f","session_id":"f1b26928-7ec7-4101-8adc-91ef6f4592ca","cards_done":[1,2]}
