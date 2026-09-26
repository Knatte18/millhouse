# Batch: symbol-resolution

```yaml
task: "plan validator and wiki-guard hook false positives"
batch: "symbol-resolution"
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate-symbol-resolution.py
depends-on: []
```

## Batch Scope

Fixes the symbol branch of context-completeness (issue 1158): framework types never resolve to repo files, and a dotted `Type.Member` token resolves through `Type` first, with a member of a type declared in the card's own refs counting as covered.
Error message wording and error-dict shape stay unchanged.
Batch-local decision: the existing `test-plan-validate.py` (too large to cite) is not edited; the new test file is standalone.

## Cards

### Card 7: framework-type exclusion and type-qualified member resolution

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  All edits are in the symbol branch and its helpers; do not touch the path branch.
  1. Add module-level `_FRAMEWORK_TYPE_NAMES: frozenset[str]` placed immediately before `_symbol_candidate_shape`, each name listed once, cross-language by design, containing: `InvalidOperationException`, `ArgumentException`, `ArgumentNullException`, `ArgumentOutOfRangeException`, `NotSupportedException`, `NotImplementedException`, `KeyNotFoundException`, `FormatException`, `Exception`, `Math`, `Path`, `File`, `Directory`, `String`, `Convert`, `Enumerable`, `List`, `Dictionary`, `HashSet`, `Task`, `Span`, `Guid`, `DateTime`, `TimeSpan`, `Console`, `Environment`, `Debug`, `Array`, `Object`, `Nullable`, `Promise`, `Map`, `Set`, `Error`, `JSON`, `ValueError`, `TypeError`, `KeyError`, `RuntimeError`, `OSError`. Add a comment that the set is a curated, extendable single constant and that its cross-language over-reach is accepted.
  2. Add helper `_resolve_type_files(type_name, candidate_files, cache)` mirroring `_resolve_symbol_files`'s signature and memoization (its own cache dict, never the symbol search cache), returning the candidate files that TYPE-declare `type_name`: `.cs` a line matching `\b(?:class|struct|interface|enum|record)\s+<name>\b`; `.ts` a line matching `\b(?:class|interface|enum|type)\s+<name>\b`; `.py` a line matching `^\s*class\s+<name>\b`; `.go` a line matching `^type\s+<name>\b`. Skip files whose suffix is not in `_SYMBOL_SEARCH_EXTENSIONS`, skip `_is_conventional_test_file` files, tolerate `OSError` on read exactly as `_resolve_symbol_files` does. Use `re.escape` on the name.
  3. In `_check_context_completeness` create one `type_cache: dict[str, list[Path]]` alongside `search_cache` and `ignore_memo`. In the symbol branch, after the shape gate and the same-plan declared-symbol exemption and before the prohibition-marker exemption, add the framework gate: let `framework_name` be `qualifier` when it is not None else `search_key`; when `framework_name` is in `_FRAMEWORK_TYPE_NAMES` and `_resolve_type_files(framework_name, candidate_files, type_cache)` is empty, skip the token (`continue`). A repo type that declares the same name keeps today's resolution.
  4. In the symbol-resolution `else` arm, before the existing `search_cache` lookup, add type-first resolution for a dotted token whose `qualifier` is not None and whose first character is uppercase: `type_files = _resolve_type_files(qualifier, candidate_files, type_cache)`. When it holds exactly one file `type_file`: compute `canonical = path_to_token[type_file]`, lazily compute `own_refs`, and if `_covered_by_own_refs(canonical, own_refs, moves_sources)` is True skip the token (covered even when the member is not declared yet). Otherwise check that the member is declared there via `_resolve_symbol_files(search_key, [type_file], {})` (a throwaway cache); if it is not declared in that file skip the token (unresolvable, never flagged); if it is, emit the existing symbol-branch error dict with the unchanged message wording, `canonical` as the resolved path, and `line` exactly as the existing symbol error does. When `type_files` has zero or more than one file, fall through to the existing behavior (`_resolve_symbol_files` then `_filter_matches_by_qualifier`), which still serves lowercase package qualifiers such as a Go package name. Factor the shared error-append into a small local helper only if that avoids duplicating the dict literal; the emitted `message` text must not change.
  5. Update `_check_context_completeness`'s docstring: add numbered exemptions 15 (framework type never resolved, with the repo-declared-type override) and 16 (type-qualified member resolves via its type; covered when the type's file is in the card's own refs), and update the symbol-branch description paragraph so it no longer says the qualifier is used only for namespace and directory disambiguation. Keep the existing "message must not drift" notes.
  No change to `_symbol_candidate_shape`, `_resolve_symbol_files`, `_filter_matches_by_qualifier`, or `_compute_plan_wide_cited_files`.
- **Commit:** `fix(plan-validate): skip framework types and resolve Type.Member via its type`

### Card 8: symbol-resolution tests

- **Context:** none
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-plan-validate-symbol-resolution.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create a standalone test file modelled on the sibling `test-plan-validate-indent-drift-line.py` (sys.path insert of the scripts directory relative to `HUB`, import the `_plan_validate` module, plain `def test_*` functions with assertions, `main() -> int` runner printing failures to stderr, `sys.exit(main())`). Build each fixture in a `tempfile.TemporaryDirectory`: a project root with real `.cs` files, hand-written overview and batch text, and a call to the validator's top-level run function with the plan directory and project root as its two positional arguments, filtering results to `check == "context-completeness"`. Use the helper shapes of the existing symbol-branch tests in the large existing test file as a reference for the overview and batch text layout, but write the helpers locally (a small overview builder and a batch builder taking context, edits, and requirements). Every cited file must be cited in some card's `Context:` or `Edits:` so it enters the plan-wide cited-file search space. Scenarios:
  - A bare framework exception name in Requirements with a cited `.cs` file that mentions it only in a member-shaped line (for example a `public` method line that names it before an opening parenthesis): no error.
  - The same with a cited `.cs` file that declares `class` of that exact name: still flagged, naming that file (repo-type override).
  - Framework-qualified tokens for `Path.Combine` and `Math.Max`: no error even when cited files declare methods named `Combine` and `Max`.
  - A dotted `HydraulicsParticipant.Replace` where the card's `Edits:` is the file declaring the class (member not yet declared there) and another cited file declares a `Replace` method: no error.
  - Same with the member already declared in the Edits file: no error.
  - The class file is cited elsewhere in the plan (different card) and declares `Replace`, but is not in the token card's own refs: exactly one error whose message contains the resolved class file path, with the unchanged wording `which resolves to '`.
  - The class file does not declare the member (another cited file does): no error.
  - Two cited files declare the same class name: falls through to the existing behavior (assert no crash and that a single-match directory-qualified case still resolves as before, or no error when still ambiguous).
  - Regression guard: a lowercase Go package qualifier token such as `reedengine.New` with two cited `.go` files still narrows by package and flags the right file.
- **Commit:** `test(plan-validate): cover framework-type and Type.Member resolution`

## Batch Tests

`verify:` runs only the new `test-plan-validate-symbol-resolution.py`. The existing `test-plan-validate.py` (a very large file that already exercises the symbol branch) must also pass unchanged after this batch; the implementer runs it once at the end of card 7 as a manual regression check with `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py`, but it is deliberately not in the per-round `verify:` because of its runtime.
