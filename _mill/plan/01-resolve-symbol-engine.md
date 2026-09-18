# Batch: resolve-symbol-engine

```yaml
task: '_plan_validate.py _resolve_symbol_files: naive whole-file text search, no declaration-form check'
batch: resolve-symbol-engine
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: []
```

## Batch Scope

This batch rewrites the resolution engine inside `plugins/mill/scripts/_plan_validate.py`'s `context-completeness` check: `_resolve_symbol_files` (declaration-form matching + solution-scope pruning, card 1) and `_symbol_candidate_shape` + its caller `_check_context_completeness` (qualifier disambiguation, card 2). No test files are touched here — batch `resolve-symbol-tests` (depends-on this batch) adds all new test coverage. Both cards are self-contained, independently verifiable commits: card 1 changes only `_resolve_symbol_files`'s internal matching behavior (its signature and cache contract are untouched); card 2 changes `_symbol_candidate_shape`'s return shape and its one call site together, since that shape change and the call site that unpacks it must land in the same commit to avoid an intermediate broken state.

## Cards

### Card 1: `_resolve_symbol_files` declaration-form matching + solution-scope pruning

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace `_resolve_symbol_files`'s naive `word_re.search(content)` whole-file text search with declaration-form matching, and extend its directory pruning with solution-scope markers. Both changes are internal to this function — its signature (`_resolve_symbol_files(search_key, project_root, root, git_root, cache)`), its cache contract (keyed by `search_key` alone, unchanged), and its return shape (`(matches: list[Path], producing_root: Path | None)`) all stay exactly as today.

  **Solution-scope pruning.** Add a new module-level frozenset `_SYMBOL_SEARCH_OUT_OF_SCOPE_DIRS = frozenset({"deprecated", "legacy", "obsolete", "archive"})` next to the existing `_SYMBOL_SEARCH_DENYLIST_DIRS`. In the `os.walk` loop's `dirnames[:] = [...]` pruning line, additionally prune any directory whose basename, lowercased, is in `_SYMBOL_SEARCH_OUT_OF_SCOPE_DIRS` — i.e. a directory is pruned when its basename is in `_SYMBOL_SEARCH_DENYLIST_DIRS` (exact match, existing behavior) OR its lowercased basename is in `_SYMBOL_SEARCH_OUT_OF_SCOPE_DIRS` (case-insensitive, new). Keep both checks in the same `dirnames[:]` list-comprehension filter — do not add a second `os.walk` pass.

  **Declaration-form matching.** Replace the body's per-file `if word_re.search(content): matches.append(file_path)` with a per-line scan of `content.splitlines()` that only counts a line as a match when it matches one of the declaration-form patterns for the file's own extension, built from `re.escape(search_key)` (call the escaped form `sym` below):

  - **`.go`:** either (a) a top-level declaration line matching `^(?:func\s+(?:\([^)]*\)\s*)?{sym}\s*[(\[]|(?:type|const|var)\s+{sym}\b)`, or (b) a grouped-block member line. Track a single boolean `in_go_group` while scanning a `.go` file's lines in order: a line matching `^(const|var|type)\s*\($` sets `in_go_group = True` (an unmatched opening paren on its own grouped-declaration line — `const (`, `var (`, or `type (`); a line matching `^\)\s*$` while `in_go_group` is `True` sets it back to `False`; while `in_go_group` is `True`, a line matching `^\s*{sym}\b` counts as a declaration-form match. This is a single bounded open/unclosed-group counter (a boolean, since Go doesn't nest these blocks), not general enclosing-scope tracking.
  - **`.cs`:** either (a) a type-level declaration matching `\b(?:class|struct|interface|enum|record)\s+{sym}\b`, or (b) a member-level declaration matching `\b(?:public|private|protected|internal)\b.*\b{sym}\b\s*[({{;=]` (an access modifier anywhere earlier on the same line, followed eventually by the symbol followed by `(`, `{{`, `;`, or `=` — covers methods, properties, and fields).
  - **`.py`:** either (a) `^\s*(?:def|class)\s+{sym}\b`, or (b) a module-level (column-0, unindented) assignment/annotation matching `^{sym}\s*(?::\s*\S.*)?=` (covers `{sym} = ...` and `{sym}: <type> = ...`). A same-shape line indented one or more levels (a class-body attribute) does NOT count — this is a deliberately accepted residual gap (see `_mill/discussion.md`'s `declaration-form-regex` Decision, Python bullet): Python has no access-modifier keyword to anchor a class-body-attribute pattern on the way the `.cs` member pattern does, so it is left as a documented zero-match case rather than adding enclosing-scope (class/def) tracking.
  - **`.ts`:** either (a) `\b(?:function|class|interface|type|enum)\s+{sym}\b`, or (b) `\b(?:export\s+)?(?:const|let|var)\s+{sym}\b`.

  A file is a match when at least one line matches per the rules for that file's extension. Every pattern above requires `re.escape(search_key)` substituted for `{sym}`/`sym` — do not use the raw `search_key` unescaped. The existing `_SYMBOL_SEARCH_EXTENSIONS` tuple (`.py`, `.go`, `.cs`, `.ts`) and the existing per-file `try: content = file_path.read_text(...) except OSError: continue` unreadable-file handling are both unchanged — only what counts as a match within an already-read file's content changes.

  Update `_resolve_symbol_files`'s docstring: the sentence describing "case-sensitive whole-word-matches `search_key` against the text of every file" becomes a description of declaration-form matching per the rules above (reference this by behavior, not by repeating every regex verbatim in the docstring — the code is the source of truth for the exact patterns). Add one sentence noting the solution-scope pruning extension alongside the existing denylist-dirs sentence.
- **Commit:** `fix(plan-validate): declaration-form symbol matching + solution-scope pruning in _resolve_symbol_files`

### Card 2: `_symbol_candidate_shape` qualifier + caller-side disambiguation

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change `_symbol_candidate_shape`'s return type from `str | None` to `tuple[str, str | None] | None`: `None` when the token is not symbol-shaped (unchanged condition), else a 2-tuple of `(search_key, qualifier)` where `search_key` is exactly what the function returns today (the bare identifier, or a dotted pair's trailing segment) and `qualifier` is `segments[0]` when `len(segments) == 2` (today's dotted case) else `None` (today's bare-identifier case). Do not change which tokens qualify — the existing `qualifies()` helper and the `_RE_SYMBOL_SHAPE` gate are unchanged.

  Update `_check_context_completeness`'s one call site (the `is_path_shaped` branch's `else:` arm, where it currently does `search_key = _symbol_candidate_shape(token)` then `if search_key is None: continue`) to unpack the new tuple: `shape_result = _symbol_candidate_shape(token)`, `if shape_result is None: continue`, `search_key, qualifier = shape_result`. Every other use of `search_key` in that arm (the `search_cache` lookup, the `_resolve_symbol_files` call, the `len(matches) != 1` guard, `matches[0].relative_to(producing_root)`) keeps using the unpacked `search_key` string exactly as before — `_resolve_symbol_files` itself is not touched by this card and takes no `qualifier` argument.

  Add qualifier-based disambiguation between the existing `matches, producing_root = ...` retrieval (from `search_cache` or a fresh `_resolve_symbol_files` call) and the existing `if len(matches) != 1: continue` guard: when `qualifier is not None` and `len(matches) > 1`, call a new module-level helper `_filter_matches_by_qualifier(matches: list[Path], qualifier: str) -> list[Path]` and use its return value in place of `matches` for the rest of this arm (including the `len(...) != 1` check and the `matches[0]` canonicalization). When `qualifier is None`, or `len(matches) <= 1`, skip the filtering call entirely and use `matches` unchanged — this preserves today's exact behavior for bare tokens and for already-unambiguous dotted tokens.

  Define `_filter_matches_by_qualifier` near `_resolve_symbol_files`: for each candidate `Path` in `matches`, read its text (reuse the same `try: ... except OSError: continue`-guarded read pattern `_resolve_symbol_files` already uses — a candidate that becomes unreadable between the original walk and this filter step is simply excluded, not an error) and, per its suffix, look for a qualifier-declaring line: `.go` → `^package\s+(\w+)$` (first match in the file); `.cs`/`.ts` → `^namespace\s+([\w.]+)` (first match in the file; compare `qualifier` against the LAST dot-separated segment of the captured group, e.g. `Foo.Bar.Baz` matches qualifier `Baz`). `.py` files, and any `.go`/`.cs`/`.ts` file with no such line, have no qualifier-declaring line at all. Build `package_matches = [p for p in matches if <p's captured qualifier segment, when present, equals `qualifier`>]` (a `.py` file, or a `.go`/`.cs`/`.ts` file with no qualifier-declaring line, is never added to `package_matches` — absence is not a match). If `len(package_matches) == 1`, return `package_matches`. Otherwise, fall back to directory-basename matching over the ORIGINAL `matches` list (not `package_matches`): `dir_matches = [p for p in matches if p.parent.name.lower() == qualifier.lower()]`. Return `dir_matches` regardless of its length (0, 1, or >1) — the caller's existing `len(...) != 1` guard, applied to this function's return value, already handles the "still ambiguous" and "resolved to nothing" cases correctly without this helper needing its own special-casing.

  Update `_check_context_completeness`'s docstring, in its "Symbol branch" paragraph: state that a dotted token's qualifier now participates in disambiguation (package/namespace match, falling back to directory-basename match) instead of being discarded, and that this filtering happens on the caller side, after every `_resolve_symbol_files` call or cache hit, never inside `_resolve_symbol_files` itself.
- **Commit:** `fix(plan-validate): qualifier-based disambiguation for dotted symbol references`

## Batch Tests

`verify:` runs the full `plugins/mill/unit_tests/test-plan-validate.py` suite — the single test file covering `_plan_validate.py`'s `run()` and every one of its checks, including every existing `test_check_context_completeness_symbol_*` test. This batch changes internal matching behavior only (no signature or cache-contract change survives past card 2's own commit), so the existing suite is the regression gate for this batch; batch `resolve-symbol-tests` (depends-on this batch) adds the new coverage for the declaration-form, qualifier-disambiguation, and solution-scope-pruning behavior introduced here. Full-suite scope is used rather than a narrower `--only` selection because `test-plan-validate.py` is the one test file for the one module this batch edits — there is no narrower file-level scope available.
