# Batch: context-completeness-resolution-and-tokenization-rework

```yaml
task: '_plan_validate context-completeness: further false-positive/false-negative gaps, round 3'
batch: context-completeness-resolution-and-tokenization-rework
number: 1
cards: 6
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
depends-on: []
```

## Batch Scope

This batch closes six filed bugs against `_plan_validate.py`'s `context-completeness` check
(`_check_context_completeness`, `_symbol_candidate_shape`, `_resolve_symbol_files` in
`plugins/mill/scripts/_plan_validate.py`) plus one bug traced during exploration, entirely within
this one file and its unit test file. The six cards are ordered so the three independent pure-
function fixes land first (cards 1-3, each test-first per the Testing decisions below), then the two
structural changes that touch `_check_context_completeness`'s own body land in sequence: the
resolution-scope narrowing (card 4) plus its own existing-test migration (card 5), then the
Requirements-text tokenization refactor (card 6), which builds on top of the now-narrowed resolution
call. There is no external interface this batch hands to a later batch — this is the only batch in
the plan.

## Cards

### Card 1: Widen `_compute_declared_symbols_union` for inline `modifier+ identifier = value` declarations (#1119)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new module-level regex near `_BACKTICK_RE`:
  `_RE_INLINE_ASSIGN_DECLARATION = re.compile(r"^(?:\S+\s+)+([A-Za-z_]\w*)\s*=")`.
  In `_compute_declared_symbols_union`'s per-token loop, the current shape is: compute
  `candidate_spans` from paren/brace detection; `if not candidate_spans: continue`. Change the
  `continue` branch: when `candidate_spans` is empty, try `_RE_INLINE_ASSIGN_DECLARATION.match(token)`
  first; on a match, add `match.group(1)` to `declared` and move to the next token; on no match,
  `continue` exactly as today. When `candidate_spans` is non-empty, the existing paren/brace
  extraction (widest-span selection, comma/semicolon split, first/last-word capture) is unchanged.
  The `(?:\S+\s+)+` group requires at least one preceding whitespace-separated token before the
  captured identifier, so a bare `` `identifier = value` `` span with nothing in front of the
  identifier never matches — this is intentional (see verified examples).
  Verified examples: `` `private const double StepDurationS = 10.0` `` (no parens/braces) matches,
  with `(?:\S+\s+)+` consuming `"private const double "` and capturing `StepDurationS` into
  `declared`. `` `timeout = 30` `` (no parens/braces, zero preceding tokens) fails to match at all
  (nothing precedes `timeout`) and contributes nothing to `declared`, preserving today's behavior for
  ordinary prose citing an existing symbol's current value.
  New unit tests in `test-plan-validate.py`, mirroring `test_check_context_completeness_symbol_clean_declared_param_same_card`'s
  and `test_check_context_completeness_symbol_clean_declared_struct_field_cross_card`'s existing
  fixture shape (same-card and cross-card variants):
  `test_check_context_completeness_symbol_clean_declared_inline_assignment_same_card` — a card's own
  Requirements: declares `` `private const double StepDurationS = 10.0` `` then bare-references
  `StepDurationS` later in the same Requirements: text, with an unrelated fixture file also
  declaring a real `StepDurationS` symbol (that would otherwise resolve and fire) — zero errors.
  `test_check_context_completeness_symbol_dirty_bare_assignment_not_a_declaration` — a card's
  Requirements: cites `` `bare_timeout_value = 30` `` with no modifier token in front, then bare-
  references `bare_timeout_value` elsewhere in the plan where a real fixture file declares that exact
  symbol, absent from the referencing card's own refs — the zero-modifier form contributes nothing to
  `declared`, so the reference still resolves and fires (one context-completeness error naming the
  resolved path).
- **Commit:** `fix(plan-validate): widen declared-symbols-union to capture inline modifier+ identifier = value declarations (#1119)`

### Card 2: `_symbol_candidate_shape` leading assignment-target prefix stripping (#1115)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new module-level regex near `_RE_SYMBOL_SHAPE`:
  `_RE_LEADING_ASSIGN_PREFIX = re.compile(r"^[A-Za-z_]\w*\s*(?::\s*[A-Za-z_][\w<>\[\], .]*)?\s*=\s*")`.
  In `_symbol_candidate_shape`, immediately after the existing trailing-suffix-stripping `while True:`
  loop (the one applying `_RE_LINE_RANGE` then the three `_RE_TRAILING_GROUPS` regexes) and BEFORE
  the `if not _RE_SYMBOL_SHAPE.match(base): return None` check, add one line:
  `base = _RE_LEADING_ASSIGN_PREFIX.sub("", base, count=1)`. This strips an optional leading
  `identifier(: Type)? = ` assignment-target prefix once, unconditionally — a no-op when the token
  has no `=`. Every downstream `qualifies()`/qualifier/dotted-pair check operates on the resulting
  `base` exactly as today, unmodified by this card.
  Verified example (#1115): `` `x = mod.func(args)` `` — the existing trailing-suffix stripping
  already removes the `(args)` call suffix (unchanged), leaving `base = "x = mod.func"`; the new
  leading-prefix strip then removes `"x = "`, leaving `base = "mod.func"`, a `_RE_SYMBOL_SHAPE`-
  matchable two-segment dotted token that proceeds through the existing logic with qualifier `"mod"`
  and trailing segment `"func"`.
  New unit test in `test-plan-validate.py`, `test_check_context_completeness_symbol_dirty_assignment_expression_prefix`,
  mirroring `test_check_context_completeness_symbol_dotted_trailing_segment_only`'s existing fixture
  shape: a card's Requirements: cites `` `x = mod.func(args)` `` with a fixture file declaring
  `func` in package `mod`, absent from the card's own refs — exactly one context-completeness error
  with `path == "x = mod.func(args)"` (the original, unstripped token) naming the resolved file.
- **Commit:** `fix(plan-validate): strip leading assignment-target prefix in _symbol_candidate_shape (#1115)`

### Card 3: `_is_literal_enumeration_exempt` majority-non-shaped rule (#1116, #1122)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_is_literal_enumeration_exempt`, replace the current "skip the tested
  occurrence, return `True` on the first OTHER non-shaped sibling found" loop with a self-inclusive
  majority tally: classify EVERY match in `matches` (the tested occurrence included, no `continue`
  for it) as shaped (`"/" in other or other.endswith(_PATH_CANDIDATE_EXTENSIONS)` OR
  `_symbol_candidate_shape(other) is not None`) or non-shaped; count `shaped_count` and
  `non_shaped_count` across all of them; return `non_shaped_count > shaped_count` (a strict majority
  — an exact tie is NOT a majority and does not exempt). The existing `len(matches) < 3: return False`
  early gate is unchanged.
  Every fixture file named README.md anywhere below in this card's own Requirements: (never
  backtick-wrapped in this introductory sentence, to avoid a false self-match here) is the test's own
  tempdir fixture file, not a real dependency — every later backtick-wrapped occurrence is marked
  mentioned, not read individually.
  Update the existing test `test_check_context_completeness_clean_literal_enumeration_mixed_shapes`:
  its #984 fixture line has 8 backtick tokens (symbol-shaped: `TestIsGlyphTarget`, `isGlyphTarget`;
  path-shaped, via the `"/" in token` rule for the first two and the `.md` extension for the third:
  `a/b#C`, `a/b`, `README.md` -- mentioned, not read) -- 5 shaped total -- and non-path/non-symbol
  literal tokens `#x`, `a#b#c`, `.` -- 3 non-shaped. 3 is not a strict majority over 5, so this line
  NO LONGER qualifies for the exemption under the new rule. Rename the test to
  `test_check_context_completeness_dirty_literal_enumeration_mixed_shapes_majority_not_reached`,
  update its docstring to state the new outcome, and change the assertion to `len(check_errors) == 1`
  with `check_errors[0]["path"]` equal to the fixture's own `README.md` name -- mentioned, not read;
  it is the only token both independently resolvable to an on-disk file and absent from the card's
  own refs. `TestIsGlyphTarget`/`isGlyphTarget` never resolve to any fixture file via the symbol
  branch, and `a/b#C`/`a/b` do not exist on disk so the path branch's `resolvable` gate excludes them
  -- update this file's own test-function reference list (the module-level list the
  `__main__`/run-all.py discovery block iterates) to the renamed name.
  Add a new test, `test_check_context_completeness_clean_literal_enumeration_majority_non_shaped`,
  proving the exemption still exists for a genuine non-shaped majority: a Requirements: line with 4
  backtick tokens -- three non-shaped literal test-input values (`` `"a"` ``, `` `"b"` ``, `` `42` ``)
  and one path-shaped fixture file (its own `README.md` -- mentioned, not read; on disk, absent from
  the card's own refs). 3 non-shaped is a strict majority over 1 shaped, so the exemption fires and
  the fixture's own file (mentioned, not read) is not flagged -- 0 context-completeness errors.
  Add a new regression test for #1116's own reported repro line,
  `test_check_context_completeness_dirty_literal_enumeration_issue_1116`: Requirements text (the
  issue's own line) "construct `` `WellboreCases.CaseHydraulic(includeCirculationSub: true)` ``, seed
  it with a converged `` `SteadyStateHydraulicSolver` `` at
  `` `EpsForConvergence = DefaultSolverScalings.Pressure * 10` ``" — 3 backtick tokens: 2 symbol-
  shaped (`WellboreCases.CaseHydraulic(includeCirculationSub: true)` strips its trailing `(...)` call
  suffix via `_symbol_candidate_shape`'s existing trailing-group stripping to the qualifying dotted
  pair `WellboreCases.CaseHydraulic`; `SteadyStateHydraulicSolver` is a qualifying bare identifier)
  and 1 non-shaped (`EpsForConvergence = DefaultSolverScalings.Pressure * 10` has no
  parens/brackets/angle-brackets to strip and, containing spaces and `=`, is not
  `_RE_SYMBOL_SHAPE`-matchable as a whole). 1 is not a strict majority over 2, so the exemption does
  not fire. Add a fixture file declaring `SteadyStateHydraulicSolver` (e.g. a `.cs` file with
  `public class SteadyStateHydraulicSolver {}`), absent from the card's own refs, and assert exactly
  one context-completeness error naming it (`"which resolves to '<path>'"` in the message) —
  `WellboreCases.CaseHydraulic`'s trailing segment `CaseHydraulic` never resolves to any fixture
  file, so it produces no additional finding.
  Add a new regression test for #1122's traced literal-enumeration angle,
  `test_check_context_completeness_dirty_literal_enumeration_issue_1122`: Requirements text
  "Confirm `` `millpy-merge-in-subagent.py` ``'s `` `verify-fix` `` mode never calls
  `` `finalize_from_output` `` -- mentioned, not read; a fictional fixture symbol name below, not
  this card's own dependency." with `millpy-merge-in-subagent.py` on disk (a placeholder fixture
  file) and absent from the card's own refs. 3 backtick tokens: `millpy-merge-in-subagent.py`
  (path-shaped), `verify-fix` (non-shaped — the hyphen is not a `\w` character, so
  `_RE_SYMBOL_SHAPE` never matches it), and the fictional symbol name above (symbol-shaped, mentioned
  not read). 1 non-shaped is not a strict majority over 2 shaped, so the exemption does not fire;
  assert exactly one context-completeness error with `path == "millpy-merge-in-subagent.py"` — the
  fictional symbol name never resolves to any fixture file in this test, so it produces no additional
  finding.
- **Commit:** `fix(plan-validate): require strict non-shaped majority for literal-enumeration exemption (#1116, #1122)`

### Card 4: Narrow `_resolve_symbol_files` to the plan's own already-cited files (resolution-scope-rework)

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new module-level helper, placed near `_compute_declared_symbols_union`:
  ```
  def _compute_plan_wide_cited_files(
      batch_files: list[Path],
      project_root: Path,
      root: str | None,
      *,
      wiki_root: Path | None = None,
      git_root: Path | None = None,
  ) -> dict[str, Path]:
  ```
  Body: for every batch file in `batch_files` (already the caller-filtered, sorted, non-overview
  list `run()` builds), for every card returned by `_parse_cards(batch_path.read_text(encoding="utf-8"))`,
  union `_card_own_reference_set(card_text)`'s tokens into one plan-wide `raw_tokens: set[str]`. For
  each token in `sorted(raw_tokens)`, resolve it via
  `resolve_existing_paths([token], project_root, root, wiki_root=wiki_root, git_root=git_root)`; when
  that returns exactly one path and `path.is_file()`, add `token -> path` to the returned dict. A
  token resolving to zero paths (not yet on disk — an unbuilt `Creates:`/`Moves:`-target token) or to
  a directory is silently omitted — no fallback, matching `resolution-scope-rework`'s "unresolvable,
  never flagged" contract.

  Rewrite `_resolve_symbol_files`'s signature and body:
  ```
  def _resolve_symbol_files(
      search_key: str,
      candidate_files: list[Path],
      cache: dict[str, list[Path]],
  ) -> list[Path]:
  ```
  Drop the `project_root`/`root`/`git_root` parameters and the `candidate_roots` precedence-order
  construction entirely — the caller now supplies the exact, already-resolved file set to search.
  Delete the `os.walk` loop and its `dirnames[:]` pruning against `_SYMBOL_SEARCH_DENYLIST_DIRS`/
  `_SYMBOL_SEARCH_OUT_OF_SCOPE_DIRS`. Keep the `go_top_level_re`/`cs_type_re`/`cs_member_re`/
  `py_def_re`/`py_module_assign_re`/`ts_type_re`/`ts_var_re` construction and the nested
  `_has_declaration` closure unchanged. New body: `if search_key in cache: return cache[search_key]`;
  then build `matches` by iterating `candidate_files`, keeping each `f` whose `f.suffix in
  _SYMBOL_SEARCH_EXTENSIONS`, that is not `_is_conventional_test_file(f)`, and for which
  `_has_declaration(f, content)` is true where `content = f.read_text(encoding="utf-8",
  errors="replace")` read inside a `try/except OSError: continue`-shaped guard (a broken symlink or
  permission-denied file in `candidate_files` is skipped, not fatal — mirrors today's per-file guard
  inside the deleted walk); `cache[search_key] = matches; return matches`.
  Delete the now-dead module-level constants `_SYMBOL_SEARCH_DENYLIST_DIRS` and
  `_SYMBOL_SEARCH_OUT_OF_SCOPE_DIRS` (their only consumer was the deleted walk-pruning code). Do not
  remove `import os` at the top of the file — `os.path.expanduser` elsewhere in this file still needs
  it.

  Update `_check_context_completeness`'s signature: add a keyword parameter
  `cited_files_map: dict[str, Path] | None = None`, materialized to `{}` on entry (mirrors the
  existing `creates_declaring_card_map`/`declared_symbols` `None`-default convention already in this
  function's signature and docstring `Args:` section — extend that section's prose to document
  `cited_files_map`'s role, and update the docstring's "Symbol branch" paragraph to describe a search
  over the plan-wide cited-files set rather than a root-precedence repo walk). At the top of the
  function, alongside the existing `search_cache` declaration (retype it from
  `dict[str, tuple[list[Path], Path | None]]` to `dict[str, list[Path]]`), derive
  `candidate_files = list(dict.fromkeys(cited_files_map.values()))` and build
  `path_to_token: dict[Path, str] = {}` via `for token, path in cited_files_map.items():
  path_to_token.setdefault(path, token)` (first-seen wins on a rare duplicate-path collision). In the
  symbol branch's resolution call site, replace the current cache-check-then-call wrapper (`if
  search_key in search_cache: matches, producing_root = search_cache[search_key] else: matches,
  producing_root = _resolve_symbol_files(search_key, project_root, root, git_root, search_cache)`)
  with a single unconditional call `matches = _resolve_symbol_files(search_key, candidate_files,
  search_cache)` — `_resolve_symbol_files` already returns the cached value directly, so the
  surrounding pre-check is now redundant. Replace
  `canonical = matches[0].relative_to(producing_root).as_posix()` with
  `canonical = path_to_token[matches[0]]`.

  Update `run()`: immediately after `declared_symbols = _compute_declared_symbols_union(plan_dir)`,
  add `cited_files_map = _compute_plan_wide_cited_files(batch_files, project_root, effective_root,
  wiki_root=wiki_root, git_root=git_root)`. Thread `cited_files_map=cited_files_map` into the
  existing `_check_context_completeness(...)` call alongside `declared_symbols=declared_symbols`.

  New fixture-based tests in `test-plan-validate.py`:
  `test_check_context_completeness_symbol_resolution_scope_plan_wide_not_own_card` — a symbol
  (`CellLength`, from #1131's own false-positive list) declared in a fixture file cited by a SECOND
  card's own `Context:` but absent from the tested card's own refs — still flagged (one
  context-completeness error naming the resolved path); proves the plan-wide union, not just the
  same card's own refs, feeds the search.
  `test_check_context_completeness_symbol_resolution_scope_excludes_uncited_repo_file` — the same
  fixture shape as `test_check_context_completeness_symbol_dirty_missing` (a declaring file on disk
  named by NO card anywhere in the plan), using `InnerRadius` (also from #1131) as the symbol name —
  now zero errors, reproducing the #1131/#1129 false-positive fix.
  `test_check_context_completeness_symbol_resolution_scope_qualifier_disambiguation_unaffected` —
  two same-named-symbol candidate files, one cited via the tested card's own `Context:` and the other
  via a second card's `Context:`, disambiguated by a dotted qualifier token — resolves to the
  qualified file exactly as `test_check_context_completeness_symbol_qualifier_package_go` already
  proves pre-narrowing, confirming `_filter_matches_by_qualifier` still receives both candidates once
  both are plan-cited.
  `test_check_context_completeness_symbol_resolution_scope_empty_plan_wide_set_no_crash` — a fixture
  plan where every card's `Context:`/`Edits:`/`Creates:`/`Deletes:`/`Moves:` is `none` (mirroring
  `_make_batch_file_cards`'s all-none card shape), yet one card's Requirements: bare-references a
  real symbol declared in a fixture file that exists on disk — zero errors, no crash (the empty
  plan-wide union yields an empty `candidate_files`, so `_resolve_symbol_files` returns `[]`
  immediately without touching the filesystem).
- **Commit:** `fix(plan-validate): narrow symbol resolution to the plan's own cited files, no repo-wide fallback (resolution-scope-rework)`

### Card 5: Migrate existing symbol-branch tests broken by resolution-scope-rework

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Card 4's resolution-scope-rework makes `_resolve_symbol_files` search only files
  already present in `_compute_plan_wide_cited_files`'s plan-wide map — a symbol declared solely in a
  file that no card's own `Context:`/`Edits:`/`Creates:`/`Deletes:`/`Moves:` cites anywhere in a
  fixture plan can no longer be found (Decision `resolution-scope-rework`'s accepted cost). Grep
  `^def test_check_context_completeness_symbol_` in `plugins/mill/unit_tests/test-plan-validate.py`
  to enumerate every existing symbol-branch test function. For each one whose fixture places its
  target symbol's declaring file under `project_root` WITHOUT any card's `context=`/`edits=`/
  `creates=`/`deletes=`/`moves=` argument to `_make_batch_file` naming that same file anywhere in the
  fixture plan, AND whose assertions depend on that symbol actually being resolved (a
  context-completeness error naming the resolved path, a `_filter_matches_by_qualifier`
  disambiguation outcome, an out-of-scope/denylist-directory outcome, a `_resolve_symbol_files`
  cache-behavior assertion, or similar) rather than on the token failing the shape/exemption gate
  before resolution is ever attempted: add a second batch entry to that test's `_write_plan` call (a
  new `_make_overview` batch dict with `depends-on: []`, a second `_make_batch_file(..., card_num=2,
  context=[<the same file path(s) the fixture already writes to disk>])` file) so the plan-wide
  cited-files union now includes the declaring file — without adding it to the TESTED card's own
  `Context:`/`Edits:`/etc., preserving each test's original "absent from this card's own refs"
  scenario and its original expected error count/message verbatim. Do not modify a function whose
  fixture already cites the target file in the tested card's own refs (e.g.
  `test_check_context_completeness_symbol_clean_in_context`) or whose expected-zero-errors outcome
  does not depend on the file being found at all (e.g. a token failing `_symbol_candidate_shape`'s
  own shape gate before resolution is attempted, or an already-covered same-plan-declared-symbol
  exemption case). Running `PYTHONPATH= uv run --project plugins/mill python
  plugins/mill/unit_tests/run-all.py --only test-plan-validate.py` to green is the authoritative
  completeness check for this card, not a manual tally of function names.
- **Commit:** `fix(plan-validate): migrate existing symbol-branch test fixtures to resolution-scope-rework's plan-wide citation gate`

### Card 6: Joined-text Requirements tokenization for `_check_context_completeness` (line-join-refactor)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Replace `_check_context_completeness`'s current per-physical-line tokenization loop (the
  `requirements_lines = requirements_text.splitlines()` / `for line in requirements_lines:` structure,
  including its own `in_fence` toggle and the `for match in backtick_re.finditer(line):` inner loop)
  with a joined-text pass:
  1. Build `included_lines: list[tuple[int, str]]` by walking `requirements_lines` with the SAME
     quoted-line skip logic already present (a line is quoted, and excluded from `included_lines`,
     when `in_fence` is `True` on entry OR the line's lstripped form starts with `>`; the fence
     toggle on a line starting with ` ``` ` is evaluated on the line's CURRENT state, exactly as
     today) — collect `(original_line_index, line_text)` for every non-quoted line, in order.
  2. Build `joined_text = "\n".join(text for _, text in included_lines)` and `line_starts: list[int]`
     where `line_starts[i]` is `included_lines[i]`'s first-character offset in `joined_text`
     (accounting for the `"\n"` separators between consecutive included lines).
  3. Run `backtick_re.finditer(joined_text)` ONCE (replacing the per-line `finditer(line)` call).
  4. For each match, find `i` (start line index) and `j >= i` (end line index) into `included_lines`/
     `line_starts` such that the match's `[match.start(1), match.end(1))` span falls within those
     lines' own `[line_starts[k], line_starts[k] + len(included_lines[k][1]))` ranges — normally
     `i == j`. Compute `local_text = "\n".join(text for _, text in included_lines[i : j + 1])` and
     `local_offset_base = line_starts[i]`.
  5. Call the four unconditional, non-clause-bounded exemption helpers against the LOCAL span:
     `_is_prohibition_exempt(local_text.lower())`, `_is_literal_enumeration_exempt(local_text,
     match.start(1) - local_offset_base, match.end(1) - local_offset_base)`,
     `_is_cross_card_ownership_exempt(local_text.lower())`, `_is_illustrative_output_exempt(local_text.lower())`
     — same call order as today, only the `line`/`lowered_line`/offset arguments change.
  6. Call the two clause-bounded helpers against the JOINED-text-global span:
     `_is_non_dependency_negation_exempt(joined_text.lower(), match.start(1), match.end(1))` and
     `_is_contrast_citation_exempt(joined_text.lower(), match.start(1), match.end(1))` — see the
     `_clause_bounds` signature change below for how these stay line-capped.
  7. The emitted error dict's `"line"` field becomes `included_lines[i][1].strip()` (the original,
     unquoted physical line containing the token match's START offset) — replacing today's
     `line.strip()`.
  The exemption-check ORDER (prohibition -> non-dependency-negation -> citation-marker ->
  contrast-citation -> cross-card-ownership -> literal-enumeration -> illustrative-output -> path/
  symbol resolution) is unchanged; only which text/offsets each call receives changes, per steps 5-6.

  Update `_clause_bounds`'s signature to
  `_clause_bounds(lowered_line: str, start: int, end: int, *, extra_boundaries: list[int] | None = None) -> tuple[int, int]`.
  When `extra_boundaries` is given (a sorted list of offsets — `_check_context_completeness` passes
  `line_starts[1:]`, since offset 0 needs no boundary marker), the clause-start search additionally
  stops at the highest `extra_boundaries` entry `<= start` and the clause-end search additionally
  stops at the lowest `extra_boundaries` entry `>= end`, each compared against the existing
  `_RE_CLAUSE_BOUNDARY`-based candidate on its own side — whichever candidate is CLOSER to
  `start`/`end` wins on each side independently. When `extra_boundaries` is `None` (the default),
  behavior is byte-for-byte identical to today. Add a `line_boundaries: list[int]` parameter to both
  `_is_non_dependency_negation_exempt` and `_is_contrast_citation_exempt`, forwarded straight through
  to their own internal `_clause_bounds` call's new `extra_boundaries` keyword; thread
  `line_starts[1:]` into both at their call sites (step 6 above).

  New regression test, `test_check_context_completeness_dirty_line_join_backtick_span_crosses_line_break`
  — reproduces the #1122-traced `millpy-fix.py` incident: a Requirements: field spanning two physical
  lines where a single-backtick inline-code span opens on the first line and does not close until
  partway through the second, followed later on that same closing line by a genuine path-shaped
  dependency (absent from the card's own refs) that the OLD per-line tokenizer would silently
  swallow into the mis-paired token (the opening backtick's own line has no closing partner within
  that line, so the pre-fix per-line `finditer` finds zero tokens on the first line and never
  connects the two lines at all). Mirror `test_check_context_completeness_dirty_odd_backtick_count_line_field`'s
  fixture shape, but split the malformed span itself across the two physical lines. Assert exactly
  one context-completeness error naming the genuine trailing dependency.

  New negative-direction test,
  `test_check_context_completeness_clean_line_join_unconditional_exemptions_stay_line_scoped` —
  proves the per-helper line-scoping split (step 5 above) holds: a card's Requirements: field has a
  genuine unlisted path-shaped dependency on one physical line, and, on a DIFFERENT physical line
  elsewhere in the same field, a phrase triggering `_is_cross_card_ownership_exempt` (e.g. "batch 8
  fixes `unrelated.py`"). Assert the genuine dependency on the first line is STILL flagged (one
  context-completeness error), proving the joined-text extraction did not widen that exemption's
  reach to the whole joined Requirements body.
- **Commit:** `fix(plan-validate): join fence-filtered Requirements text before tokenizing, fixing cross-line backtick-span corruption (line-join-refactor)`

## Batch Tests

`verify:` runs the full `test-plan-validate.py` file (all context-completeness coverage — path
branch, symbol branch, and the other checks in this file — lives in this single module, so a
narrower `--only` scope would miss regressions cards 4-6 could introduce in adjacent checks that
share this file's module-level regexes and helpers). No other test file imports the changed private
(`_`-prefixed) functions (verified: `_resolve_symbol_files`, `_symbol_candidate_shape`,
`_is_literal_enumeration_exempt`, `_compute_declared_symbols_union`, `_clause_bounds`,
`_is_non_dependency_negation_exempt`, `_is_contrast_citation_exempt`, and `_check_context_completeness`
itself are referenced only inside `_plan_validate.py` and `test-plan-validate.py`), so no other
test file needs to run for this batch.
