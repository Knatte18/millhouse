# Plan: _plan_validate.py _resolve_symbol_files: naive whole-file text search, no declaration-form check

```yaml
task: '_plan_validate.py _resolve_symbol_files: naive whole-file text search, no declaration-form check'
slug: plan-validate-context-completeness-symbol-branch-bugs
approved: false
started: 20260918-180120
parent: main
root: ""
verify: null
discussion_sha: b92dc8d4da15164406c4a5968519552cdc1ba48e
```

## Batch Index

```yaml
batches:
  - number: 1
    name: resolve-symbol-engine
    file: 01-resolve-symbol-engine.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 2
    name: resolve-symbol-tests
    file: 02-resolve-symbol-tests.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
```

## Shared Decisions

### Decision: declaration-form matching replaces naive whole-file word search

- **Decision:** `_resolve_symbol_files` (`plugins/mill/scripts/_plan_validate.py:1973`) stops using `word_re.search(content)` (a raw case-sensitive whole-word regex against the entire file text) and instead requires a match at an actual declaration site, via one regex set per source extension (`.py`, `.go`, `.cs`, `.ts`). A token that only appears inside a comment, a string/template literal, a struct tag, or as a usage/field-access site does not match, because none of those shapes are declaration syntax.
- **Rationale:** Fixes the false-positive half of the six source issues (#1008, #1015, #1023, #1030, #1033) — a JSON key or hook-event-name string, a comment word, and most usage-site occurrences no longer masquerade as declarations. See `_mill/discussion.md`'s `declaration-form-regex` Decision for the exact per-language regex shapes and the grouped-block/module-level-assignment forms.
- **Applies to:** batch `resolve-symbol-engine`, and every new test in batch `resolve-symbol-tests` that exercises this behavior.

### Decision: qualifier disambiguation stays out of `_resolve_symbol_files` and its cache

- **Decision:** `_resolve_symbol_files` keeps its existing signature, cache (keyed by `search_key` alone), and return shape (`(matches, producing_root)`) unchanged — it never accepts or applies a qualifier. `_symbol_candidate_shape` (`plugins/mill/scripts/_plan_validate.py:1926`) is extended to also return the qualifier segment of a dotted token (`None` for a bare token) alongside the search key it already returns. The caller, `_check_context_completeness`, applies qualifier-based filtering downstream of every `_resolve_symbol_files` call or cache hit, never inside it.
- **Rationale:** Fixes #1037 (a package-qualified reference dropped as ambiguous today) while keeping the cache's existing `search_key`-only contract intact — two dotted tokens sharing a trailing segment but different qualifiers each get filtered against their own qualifier every time, since the cache only ever holds the qualifier-independent raw match list. See `_mill/discussion.md`'s `qualifier-disambiguation` Decision for the full package/namespace-then-directory-basename fallback mechanism.
- **Applies to:** batch `resolve-symbol-engine` (card 2), and the qualifier-disambiguation tests in batch `resolve-symbol-tests`.

### Decision: solution-scope directory pruning extends the existing denylist mechanism

- **Decision:** The directory-pruning the walk already applies (`_SYMBOL_SEARCH_DENYLIST_DIRS`, `plugins/mill/scripts/_plan_validate.py:1828`) gains a second, case-insensitive check against a small fixed list of conventional out-of-solution directory-name markers: `deprecated`, `legacy`, `obsolete`, `archive`. A matching directory is pruned exactly like `node_modules`/`vendor` — never descended into.
- **Rationale:** Fixes #1030 (a real property declaration inside a deprecated, out-of-solution C# tree) without any project-specific configuration. See `_mill/discussion.md`'s `solution-scope-pruning` Decision.
- **Applies to:** batch `resolve-symbol-engine` (card 1), and the solution-scope-pruning tests in batch `resolve-symbol-tests`.

### Decision: `done_gate` left null — pre-existing repo-wide lint debt

- **Decision:** `pipeline.done_gate` is not set by this plan (stays `null`).
- **Rationale:** Both batches' own `verify:` already run the full `test-plan-validate.py` suite (the single test file covering `_plan_validate.py` end to end), so batch-verify scope already covers the affected module. Per this file's own "Done-gate reminder" guidance, `uvx ruff check .` was run from `git_root` against the current worktree tip before defaulting `done_gate` to it — it exits 1 with 2000 pre-existing findings, unrelated to this task's scope. Making `done_gate` depend on clearing that debt first would block every future task in this hub, not just this one, so `done_gate` stays `null` and this finding is recorded here instead.
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
