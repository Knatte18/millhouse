# Batch: plan-validate-check-fixes

```yaml
task: '_plan_validate.py: further context-completeness, fence/indent-drift, and tag-exclusion gaps'
batch: plan-validate-check-fixes
number: 1
cards: 7
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: []
```

## Batch Scope

This batch implements every code fix in `_mill/discussion.md` against
`plugins/mill/scripts/_plan_validate.py`, one card per Decision, each paired with its own unit test(s)
in `plugins/mill/unit_tests/test-plan-validate.py`. All seven cards edit the same two files; there is no
external interface for a later batch to consume — batch 2 (the `mill-plan/SKILL.md` fix-table doc edit)
is independent and touches neither file this batch edits. Cards are ordered so no two cards' edits land
on overlapping line ranges: cards 1 and 3 both touch `run()`'s check-invocation block, but at two
different, non-adjacent call sites (`_check_move_target_collision`'s call vs `_check_context_
completeness`'s call and the `moves_sources`/`moves_targets` computation line just above it) — card 1
runs first and only touches the former; card 3 runs later and only touches the latter, so neither
card's inline-backtick anchors are invalidated by the other's edit. Cards 4 and 6 both edit inside
`_resolve_symbol_files` too — card 4 adds a new helper call in the per-file walk (the
`_is_conventional_test_file` skip, right after the extension check), card 6 changes only the
`cs_member_re` pattern string a few lines below the walk — these are two distinct, non-adjacent spots
in the same function, so card 4's edit does not shift the line `cs_member_re` sits on, and neither
card's inline-backtick anchor is invalidated by the other's edit.

## Cards

### Card 1: `_check_move_target_collision` — intra-plan Moves chain false positive

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Fix the `intra-plan-move-chain` Decision: `_check_move_
  target_collision`'s condition 1 wrongly flags a `Moves:` target that collides only with an in-plan
  `Moves:` source slated to vacate that path (e.g. a batch with `Moves: a.go -> b.go` and
  `Moves: b.go -> c.go`: `b.go` currently exists on disk, so condition 1 fires on it even though it is
  about to be vacated by the first pair).

  In `_check_move_target_collision`'s signature, add a new positional parameter
  `moves_sources: set[str],` immediately before the `*,` that starts its keyword-only arguments (after
  `root: str | None,`). Update its docstring's "Args:" section to document `moves_sources` (mirror the
  existing `moves_targets`/`creates_union` Args entries elsewhere in this file for phrasing) and add one
  sentence to the docstring's numbered "Three collision conditions" list noting condition 1 is
  suppressed when the target is itself a plan-wide `Moves:` source.

  In the per-target loop, change the condition-1 check from `if existing:` to
  `if existing and dst not in moves_sources:` — the line reading exactly
  `if existing:` immediately before the `errors.append({` block whose `"message"` is
  `f"Moves: target '{dst}' already exists on disk"`.

  Update `run()`'s call site: it currently invokes `_check_move_target_collision(batch_files,
  project_root, effective_root, wiki_root=wiki_root, git_root=git_root)`. `run()` already computes
  `moves_sources, moves_targets = compute_moves_union(plan_dir)` earlier in the function (the same call
  that already feeds `_check_context_completeness`) — thread that same `moves_sources` value into this
  call as a new positional argument, immediately after `effective_root` and before the keyword
  arguments.

  Write unit tests in `test-plan-validate.py` (near the existing `_check_move_target_collision` tests):
  (a) a batch with `Moves: a.go -> b.go` and `Moves: b.go -> c.go` (same batch) produces zero
  `move-target-collision` findings; (b) the same chain split across two batches (`Moves: a.go -> b.go`
  in batch 1, `Moves: b.go -> c.go` in batch 2) also produces zero findings, confirming the plan-wide
  (not same-batch-only) scope; (c) a negative test: a `Moves:` target that already exists on disk and is
  NOT any batch's `Moves:` source still produces a `move-target-collision` finding, unchanged from
  today's behavior.
- **Commit:** `fix(plan-validate): move-target-collision no longer flags intra-plan rename chains`

### Card 2: `_card_own_reference_set` — Moves: target exemption in the declaring card

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Fix the `move-target-own-card-exemption` Decision: `context-completeness` wrongly
  flags a rename card's own `Moves:` destination when that card's `Requirements:` names it — the card
  performing the rename is exactly the one whose prose must describe what happens to the destination.

  In `_card_own_reference_set`, its Moves:-pair walk currently reads only the source half:
  the line `tokens.add(pair_m.group(1))` inside the `while k < len(lines):` loop under the `_RE_MOVES_
  HEADER` branch. Add a second line immediately after it, `tokens.add(pair_m.group(2))`, so both the
  source and destination halves of every `Moves:` pair are collected into the card's own reference set.

  Update the function's docstring, which currently reads "combines ... with the source-only half of its
  Moves: pairs (the destination half is deliberately excluded -- a Requirements: reference to a
  not-yet-existing Move target is not "already declared")." Replace that parenthetical with the
  opposite: both halves of a card's own `Moves:` pairs are now collected, since the card declaring a
  rename is the one whose `Requirements:` legitimately describes the destination.

  Write unit tests: (a) a card with `Moves: old.go -> new.go` whose `Requirements:` cites `` `new.go` ``
  produces zero `context-completeness` findings; (b) a negative test: a DIFFERENT card (not the one
  declaring the `Moves:` pair) citing that same not-yet-existing target in its own `Requirements:` still
  produces a finding, confirming the exemption is scoped to the declaring card only.
- **Commit:** `fix(plan-validate): context-completeness exempts a card's own Moves: target`

### Card 3: `_check_context_completeness` — same-plan declared-symbol exemption

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Fix the `declared-symbols-exemption` Decision: the symbol branch has no forward
  exemption when a plan introduces its own new identifier (a function-signature parameter, a
  struct-literal field) in one card's `Requirements:` prose and a bare reference to that same
  identifier appears elsewhere in the plan, causing a false match against an unrelated pre-existing
  repo symbol of the same name.

  Add a new module-private helper function, placed immediately after `_build_creates_declaring_card_map`
  and before `_check_context_completeness`:

  ```python
  def _compute_declared_symbols_union(plan_dir: Path) -> set[str]:
      """
      Return the plan-wide union of identifiers declared inside a signature- or struct-literal-shaped
      backtick token anywhere in any card's Requirements: text.

      For every card in the plan (via `_parse_cards` on every `??-*.md` batch file except
      `00-overview.md`), scans its Requirements: text (via `_requirements_fence_aware_body`, the same
      fence-aware extraction `_check_context_completeness` itself uses) for every backtick token
      matching `_BACKTICK_RE` that contains a balanced `(...)` or `{...}` span. For each such token,
      when both a `(...)` and a `{...}` span are present (e.g. a struct-literal token whose field type
      itself contains a function type, `` `type Deps struct { Acquire func() error }` ``), picks
      whichever pair's outermost span is WIDER -- an inner, narrower span (the empty `()` in `func()`
      here) would otherwise win by being checked first and yield an empty, useless `inner` substring.
      Takes the substring between that pair's first opening delimiter and its last closing delimiter,
      splits it on `,`/`;`, and for each non-empty clause adds BOTH its first and its last
      whitespace-separated word to the result set when that word matches `^[A-Za-z_]\\w*$` -- the first
      word covers a Go/Rust-style `name Type` parameter order, the last word covers a C#/TS-style
      `Type name` order.

      This is context-completeness's symbol-branch equivalent of `compute_creates_union`'s path-branch
      plan-wide union: a token this set contains is a symbol the PLAN ITSELF is introducing (a new
      parameter name, a new struct field) rather than a pre-existing repo symbol, so a bare reference
      to it elsewhere in the plan's prose must not be treated as an unlisted dependency.

      Args:
          plan_dir: Directory containing the plan files (00-overview.md + batch files).

      Returns:
          The set[str] of candidate declared-symbol names found across the whole plan. Returns an
          empty set when `plan_dir` does not exist or contains no qualifying tokens.
      """
      if not plan_dir.exists():
          return set()

      declared: set[str] = set()
      bare_word_re = re.compile(r"^[A-Za-z_]\w*$")

      for batch_path in sorted(plan_dir.glob("??-*.md")):
          if batch_path.name == "00-overview.md":
              continue
          text = batch_path.read_text(encoding="utf-8")
          for _card_num, card_lines in _parse_cards(text):
              requirements_text = _requirements_fence_aware_body(card_lines)
              if requirements_text is None:
                  continue
              for match in _BACKTICK_RE.finditer(requirements_text):
                  token = match.group(1)
                  candidate_spans = []
                  if "(" in token and ")" in token:
                      candidate_spans.append((token.find("("), token.rfind(")")))
                  if "{" in token and "}" in token:
                      candidate_spans.append((token.find("{"), token.rfind("}")))
                  if not candidate_spans:
                      continue
                  start, end = max(candidate_spans, key=lambda span: span[1] - span[0])
                  if end <= start:
                      continue
                  inner = token[start + 1:end]
                  for clause in re.split(r"[;,]", inner):
                      words = clause.split()
                      if not words:
                          continue
                      for word in (words[0], words[-1]):
                          if bare_word_re.match(word):
                              declared.add(word)

      return declared
  ```

  In `_check_context_completeness`'s signature, add a new keyword-only parameter
  `declared_symbols: set[str] | None = None,` immediately after the existing
  `creates_declaring_card_map: dict[str, tuple[int, int]] | None = None,` parameter.

  In the function body, immediately after the existing line
  `if creates_declaring_card_map is None:` / `creates_declaring_card_map = {}` materialization block,
  add the mirror materialization:
  ```python
  if declared_symbols is None:
      declared_symbols = set()
  ```

  In the symbol branch's shape gate, immediately after the line `search_key, qualifier = shape_result`
  (inside the `if not is_path_shaped:` block), insert the new exemption:
  ```python
  # Same-plan declared-symbol exemption (symbol branch only): a search key some card's
  # Requirements: declares as a new function-signature parameter or struct-literal field is
  # not resolved as an unlisted dependency.
  if search_key in declared_symbols:
      continue
  ```

  Update the function's docstring: add a new item "14." to the numbered exemption list, immediately
  after item 13 ("Illustrative-output framing...") and before the closing paragraph beginning
  "Not-shaped-at-all or unresolvable tokens": "14. Same-plan declared symbol (symbol branch only): a
  search key that some card's Requirements: declares as a new function-signature parameter or
  struct-literal field (extracted from a parenthesized/braced backtick token) is a symbol the plan
  itself is introducing, not an existing dependency to resolve." Also add a `declared_symbols` entry to
  the docstring's "Args:" section, immediately after the existing `creates_declaring_card_map` entry,
  documenting it the same way (plan-wide set from `_compute_declared_symbols_union`, defaults to `None`,
  materialized to an empty set, empty set is the correct no-op default).

  In `run()`, immediately after the existing line
  `moves_sources, moves_targets = compute_moves_union(plan_dir)`, add:
  ```python
  declared_symbols = _compute_declared_symbols_union(plan_dir)
  ```
  Then update the `_check_context_completeness(...)` call a few lines below: it currently ends with
  `creates_declaring_card_map=creates_declaring_card_map,` before its closing `))`. Add
  `declared_symbols=declared_symbols,` as a new line immediately after that one.

  Write unit tests: (a) same-card case — a card whose `Requirements:` backtick-quotes a function
  signature like `` `planReapCycle(live []string, inFlight map[string]bool)` `` and separately
  references `` `inFlight` `` produces zero findings, in a repo containing an unrelated file with a real
  `inFlight` declaration; (b) cross-card case — an earlier card's `Requirements:` quotes
  `` `type Deps struct { Acquire func() error }` ``, a later card references `` `Acquire` ``: zero
  findings; (c) negative test — a token NOT present in any signature/struct-shaped backtick anywhere in
  the plan still resolves and fires normally, confirming the exemption doesn't over-suppress.
- **Commit:** `fix(plan-validate): context-completeness exempts same-plan declared symbols`

### Card 4: `_resolve_symbol_files` — never resolve a symbol to a conventional test file

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Fix the `test-file-exclusion` Decision: symbol resolution must never resolve a
  bare backtick token to a conventional test file — a card should never be told to add another
  package's test file to its read-only `Context:` allowlist.

  Add a new module-private helper, placed immediately before `_resolve_symbol_files`'s own `def`:
  ```python
  _RE_CS_TEST_STEM = re.compile(r"Tests?$")


  def _is_conventional_test_file(path: Path) -> bool:
      """
      Return True when `path` follows a conventional test-file naming pattern for its own language.

      `.go`: stem ends with `_test` (Go's own test-file convention, e.g. `cleanup_test.go`).
      `.py`: stem starts with `test_` or ends with `_test` (pytest/unittest conventions).
      `.cs`: stem ends with `Test` or `Tests` (xUnit/NUnit/MSTest convention, e.g. `FooTests.cs`).
      `.ts`: stem ends with `.test` or `.spec` (Jest/Jasmine convention -- `Path("foo.test.ts").stem`
      is `"foo.test"`, so this checks the stem's own suffix, not a second `.suffix` lookup).

      A symbol declared ONLY in a test file must never be surfaced by `_resolve_symbol_files` as a
      dependency a card should add to its read-only `Context:` -- a bulk-mode reviewer would never
      expect another package's test file there.
      """
      stem = path.stem
      suffix = path.suffix
      if suffix == ".go":
          return stem.endswith("_test")
      if suffix == ".py":
          return stem.startswith("test_") or stem.endswith("_test")
      if suffix == ".cs":
          return bool(_RE_CS_TEST_STEM.search(stem))
      # suffix == ".ts" (the only remaining member of _SYMBOL_SEARCH_EXTENSIONS)
      return stem.endswith(".test") or stem.endswith(".spec")
  ```

  In `_resolve_symbol_files`'s per-file walk, immediately after the existing line
  `if file_path.suffix not in _SYMBOL_SEARCH_EXTENSIONS:` / `continue` pair, add:
  ```python
  if _is_conventional_test_file(file_path):
      continue
  ```
  so a test file is skipped before its content is ever read.

  Update `_resolve_symbol_files`'s own docstring to note that a conventional test file (per
  `_is_conventional_test_file`) is pruned from the walk before content is read, alongside the existing
  denylist-dir pruning it already documents.

  Write a unit test: a repo where the only real declaration of a search key lives in each of a
  `_test.go`, a `test_*.py`, a `FooTests.cs`, and a `foo.test.ts` file in turn (one scenario per
  language, or a combined fixture covering all four), referenced from a card's `Requirements:` prose by
  bare symbol name, produces zero `context-completeness` findings for that token (unresolvable-with-
  confidence once the test file is excluded, matching the existing "zero matches" no-op path).
- **Commit:** `fix(plan-validate): symbol resolution excludes conventional test files`

### Card 5: `_symbol_candidate_shape` — single-letter identifier and qualifier gate

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Fix the `single-letter-gate` Decision: a single-character bare identifier
  (illustrative step names like `` `A` ``, `` `B` ``, `` `D` ``) and a single-character dotted qualifier
  (a stdlib/BCL-receiver-shaped token like `` `t.Cleanup` ``, where `t` is Go's idiomatic
  `*testing.T` receiver name) must never be treated as symbol-shaped.

  In `_symbol_candidate_shape`'s inner `qualifies()` closure, currently reading exactly
  `return segment != segment.lower() or "_" in segment`, change it to additionally require a length
  greater than one character:
  ```python
  return len(segment) > 1 and (segment != segment.lower() or "_" in segment)
  ```

  Immediately below that closure, the function currently has an `if len(segments) == 1:` branch
  returning `(base, None) if qualifies(base) else None`, followed by a two-line dotted-token branch
  ending in the single statement `return (trailing_segment, segments[0]) if qualifies(trailing_segment)
  else None` (where `trailing_segment = segments[-1]` is bound on the line just above it). Change the
  dotted-token branch so a single-character qualifier disqualifies the WHOLE token (not just
  qualifier-based disambiguation downstream), by binding the qualifier to a name and checking its length
  before returning — replace that whole two-line dotted-token branch (the `trailing_segment = ...` line
  and the `return (trailing_segment, segments[0]) ...` line) with:
  ```python
  if len(segments) == 1:
      return (base, None) if qualifies(base) else None

  trailing_segment = segments[-1]
  qualifier = segments[0]
  if len(qualifier) <= 1:
      return None
  return (trailing_segment, qualifier) if qualifies(trailing_segment) else None
  ```

  Update the function's docstring to note both new constraints: a bare or trailing-segment identifier of
  length 1 never qualifies regardless of case/underscore content, and a dotted token whose qualifier
  segment is length 1 is not symbol-shaped at all (not merely exempt from qualifier-based
  disambiguation) — single-letter receiver/loop/parameter variables are near-universal convention across
  Go/C#/TS/Python and essentially never disambiguate a real project-specific type.

  Write unit tests: (a) `` `t.Cleanup` `` referencing a real `Cleanup` declaration elsewhere in the repo
  produces zero `context-completeness` findings (previously would have matched the unrelated file); (b)
  a bare single-letter token like `` `A` `` produces zero findings even when a file coincidentally
  declares a symbol literally named `A`; (c) a negative test confirming a genuine two-or-more-character
  qualified token (e.g. `` `fe.Cleanup` ``) still resolves and fires normally when uncited, so the length
  gate doesn't over-suppress multi-character qualifiers.
- **Commit:** `fix(plan-validate): symbol resolution ignores single-letter identifiers and qualifiers`

### Card 6: `cs_member_re` — stop matching `new X(...)` as a member declaration

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Fix the `cs-member-regex-tightening` Decision: `cs_member_re`'s unbounded `.*`
  between the access modifier and the symbol lets a `throw new InvalidOperationException(...)`- or
  `= new Foo();`-shaped line match as though the constructed type were itself a declared member.

  In `_resolve_symbol_files`, `cs_member_re` is currently assigned via `re.compile(...)` to the pattern
  `` r"\b(?:public|private|protected|internal)\b.*\b" + sym + r"\b\s*[({;=]" `` (a single-line pattern
  string). Change it to forbid the literal keyword `new` appearing between the modifier and the symbol
  — replace that pattern string with:
  ```python
  cs_member_re = re.compile(
      r"\b(?:public|private|protected|internal)\b(?:(?!\bnew\b).)*?\b" + sym + r"\b\s*[({;=]"
  )
  ```

  Update the comment immediately above it (currently reading ".cs: a type-level declaration, or a
  member-level declaration guarded by an access modifier.") to note the exclusion: a `new <Symbol>`
  occurrence between the modifier and the symbol is unambiguously a construction expression, never a
  member declaration, so it is excluded from matching.

  Write unit tests: (a) a `.cs` file containing
  `public void Foo() { throw new InvalidOperationException("x"); }`, referenced via
  `` `InvalidOperationException` `` in a card's `Requirements:`, produces zero `context-completeness`
  findings (previously would have matched); (b) a positive/regression test confirming a genuine member
  declaration where the symbol itself is the member name immediately preceding member-declaration
  punctuation — e.g. `public int InvalidOperationException { get; set; }` (the symbol precedes `{`
  directly; no `new` between modifier and symbol) — still matches `cs_member_re` and the check still
  fires when this member is uncited.
- **Commit:** `fix(plan-validate): cs_member_re no longer matches a new-expression as a declaration`

### Card 7: `_check_requirements_quote_indent_drift` — paired-fence indent mismatch detection

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Fix the `paired-fence-indent-check` Decision: a new-code fence that immediately
  follows a byte-matched anchor fence in the same card, but is indented differently from it, is
  silently skipped today as an "illustrative snippet" — never flagged — even though pasting it verbatim
  at the wrong indent raises `IndentationError`.

  Add a new module-private helper, placed immediately after `_add_n_leading_spaces` and before
  `_card_edits_tokens`:
  ```python
  def _first_nonblank_line_indent(text: str) -> int | None:
      """Return the leading-space count of the first non-blank line in `text`, or `None` if every
      line is blank.

      Mirrors `_strip_n_leading_spaces`/`_add_n_leading_spaces`'s "skip blank lines" convention -- a
      fence's own baseline indentation is measured from its first line that actually has content.
      """
      for line in text.splitlines():
          if line.strip():
              return len(line) - len(line.lstrip(" "))
      return None
  ```

  In `_check_requirements_quote_indent_drift`'s per-card loop, immediately before the line
  `for fence_idx, fence_body in enumerate(fence_bodies, start=1):`, add two new local variables that
  reset every card (this line is already inside the per-card loop body, so placing the reset here
  re-executes it once per card automatically):
  ```python
  last_matched_indent: int | None = None
  last_matched_token: str | None = None
  ```

  Refactor the existing byte-exact-clean check — the `if any(fence_body in resolved_contents[t] for t
  in ordered_resolved_tokens): continue` statement immediately after the `fence_body = re.sub(...)`
  line at the top of the per-fence loop body. Replace that whole `if any(...): continue` statement with
  a token-capturing loop (matching the shape the strip and add passes below it already use), recording
  the match into the two new variables before continuing:
  ```python
  clean_match_token = None
  for t in ordered_resolved_tokens:
      if fence_body in resolved_contents[t]:
          clean_match_token = t
          break
  if clean_match_token is not None:
      last_matched_indent = _first_nonblank_line_indent(fence_body)
      last_matched_token = clean_match_token
      continue
  ```

  In the strip pass, the existing match branch's `if matched_token is not None:` block ends with an
  `errors.append({...})` call (the "after stripping N leading spaces per line" message) immediately
  followed by `matched = True` then `break`. Immediately before that `matched = True` line, add the same
  two-variable capture:
  ```python
  last_matched_indent = _first_nonblank_line_indent(fence_body)
  last_matched_token = matched_token
  ```

  In the add pass, the existing match branch's `if matched_token is not None:` block ends with an
  `errors.append({...})` call (the "after adding N leading spaces per line" message) immediately
  followed by `break`, with no `matched`-style flag of its own. Change it to track whether the add pass
  matched (mirroring the strip pass's `matched` flag) and capture the same two variables. Introduce
  `add_matched = False` immediately before this pass's own `for n in range(1, 41):` loop, set
  `add_matched = True` alongside the two-variable capture inside the match branch, and add an
  `if add_matched: continue` immediately after that loop (mirroring the existing `if matched: continue`
  immediately after the strip pass's own loop) — replace the whole add-pass loop (from its
  `for n in range(1, 41):` line through its closing `break`) with:
  ```python
  add_matched = False
  for n in range(1, 41):
      matched_token = None
      for candidate in (
          _add_n_leading_spaces(fence_body, n),
          _add_n_leading_spaces(fence_body, n, include_blank=True),
      ):
          for token in ordered_resolved_tokens:
              if candidate in resolved_contents[token]:
                  matched_token = token
                  break
          if matched_token is not None:
              break
      if matched_token is not None:
          errors.append({
              "check": "requirements-quote-indent-drift",
              "batch": batch_path.stem,
              "card": card_num,
              "path": matched_token,
              "message": (
                  f"card {card_num}'s Requirements: fence {fence_idx} "
                  f"matches '{matched_token}' after adding {n} "
                  f"leading spaces per line (found N={n})"
              ),
          })
          last_matched_indent = _first_nonblank_line_indent(fence_body)
          last_matched_token = matched_token
          add_matched = True
          break
  if add_matched:
      continue
  ```

  Immediately after that (replacing the point where the per-fence loop iteration used to fall through
  silently — this is the end of the `for fence_idx, fence_body in enumerate(fence_bodies, start=1):`
  loop body), add the new paired-fence detection:
  ```python
  # Neither the clean check, strip pass, nor add pass matched -- illustrative new/replacement
  # code. Check indentation against the immediately preceding matched anchor fence in
  # fence_bodies order, if any.
  if last_matched_indent is not None:
      sibling_indent = _first_nonblank_line_indent(fence_body)
      if sibling_indent is not None and sibling_indent != last_matched_indent:
          errors.append({
              "check": "requirements-quote-indent-drift",
              "batch": batch_path.stem,
              "card": card_num,
              "path": last_matched_token,
              "message": (
                  f"card {card_num}'s Requirements: fence {fence_idx} (new/replacement "
                  f"code) immediately follows matched fence {fence_idx - 1}, but its "
                  f"first line is indented {sibling_indent} spaces vs the anchor fence's "
                  f"{last_matched_indent} spaces"
              ),
          })
  last_matched_indent = None
  last_matched_token = None
  ```

  Update the function's docstring: note the new paired-fence detection immediately after the existing
  paragraph ending "...is an illustrative snippet showing new/desired-state code, not a drifted quote,
  and is silently skipped -- never flagged." Add: "Exception: when such an unmatched fence immediately
  follows (in `fence_bodies` order — any prose between the two fences in the raw text does not break
  the pairing) a fence that DID match (clean, strip, or add), its own first-non-blank-line indentation
  is compared against that anchor fence's own first-non-blank-line indentation; a mismatch is flagged
  as a new finding (same check name, distinct message). This comparison only ever looks at the single
  immediately-preceding fence — it does not chain across multiple consecutive unmatched fences."

  Write unit tests: (a) a card with a byte-matched anchor fence (2-space list-continuation indent)
  immediately followed (in `fence_bodies` order, with short connective prose like a "with:" label
  between the two fences in the raw text) by a new-code fence at a DIFFERENT indent produces one
  new-shape `requirements-quote-indent-drift` finding, with `path` equal to the anchor fence's own
  matched `Edits:` token; (b) the same setup with matching indents produces zero findings; (c) an
  unmatched fence NOT immediately preceded (in `fence_bodies` order) by a matched one — e.g. a card
  whose only fence is itself unmatched, with no prior anchor — produces no new-shape finding; (d) a card
  with three fences — matched anchor, then two consecutive unmatched fences — produces exactly one
  finding (for the first unmatched fence only), confirming the anchor state resets after one comparison
  and does not chain across multiple trailing unmatched fences.
- **Commit:** `fix(plan-validate): indent-drift flags mismatched new-code fences after a matched anchor`

## Batch Tests

`verify:` runs the entire `plugins/mill/unit_tests/test-plan-validate.py` file — the single test file
covering every check in `_plan_validate.py`, per `mill-plan/SKILL.md`'s "single test file" verify
pattern. Every card in this batch edits `_plan_validate.py` itself, so scoping to any narrower `--only`
subset would leave later cards' regressions against earlier cards' fixes unverified; running the whole
file after every card's commit is the correct, already-documented scope for a batch whose `Edits:` is
this file.
