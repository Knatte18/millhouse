# Batch: requirements-quote-indent-drift-check

```yaml
task: 'mill-plan: Requirements find/replace fences lose byte-exactness under list-nested indentation'
batch: requirements-quote-indent-drift-check
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
depends-on: []
```

## Batch Scope

This batch adds one new mechanical `_plan_validate.py` check
(`requirements-quote-indent-drift`) that catches the byte-exactness bug
described in `_mill/discussion.md`: a card's `Requirements:` fence quoting
exact source text can silently pick up a uniform per-line indent from
Markdown list-continuation nesting, so the quoted text no longer byte-matches
the real source file even though it "looks right" to a human or LLM reviewer.
Card 1 implements the check and wires it into `_plan_validate.run()`. Card 2
adds the corresponding `mill-plan/SKILL.md` Step 1.5 fix-table row (the
mechanical fix mill-plan applies when the check fires) and extends the
existing `Requirements:` bullet under `## Principles` with write-time
guidance. Card 3 adds the nine unit tests specified in
`_mill/discussion.md`'s `## Testing` section. All three cards live in one
batch and one Sonnet session because the fix-table prose (Card 2) must
describe Card 1's mechanical-fix semantics exactly, and Card 3's tests
exercise Card 1's exact behavior — splitting these across batches would risk
the three drifting out of sync with each other, which is the same class of
bug this task exists to prevent. No batch-local decisions differ from
`## Shared Decisions` in the overview.

## Cards

### Card 1: Implement `_check_requirements_quote_indent_drift` and wire it into `run()`

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add three new module-level pieces to `plugins/mill/scripts/_plan_validate.py`,
  inserted immediately after `_check_context_completeness`'s `return errors`
  (around line 1581) and before the `# Check 8 — all-files-touched-mismatch`
  section-separator comment (around line 1584). All three regexes/constants
  below are written fresh for this check; do not reuse or modify
  `_extract_requirements_text`'s `header_re`/`any_field_header_re` objects
  themselves (they stay exactly as they are for `_check_context_completeness`
  and every other caller) — just replicate the same pattern strings locally.

  1. `_strip_n_leading_spaces(text: str, n: int) -> str`: for each line of
     `text` (split via `.splitlines()`), strip up to `n` leading space
     characters — remove exactly `n` when the line has at least that many
     leading spaces, otherwise strip only however many leading spaces the
     line actually has (no error on short/blank lines). Rejoin lines with
     `"\n"`. This is a fixed per-line strip, NOT `textwrap.dedent`'s
     common-minimum-strip — per `_mill/discussion.md`'s
     `trigger-heuristic-near-miss` Decision, `textwrap.dedent` silently
     misses drift when the true source excerpt has nonzero baseline
     indentation.

  2. `_card_edits_tokens(card_text: str) -> list[str]`: return the backtick
     tokens under a single card's own `- **Edits:**` header, in declaration
     order (a `list`, not a `set` — order is load-bearing for the tie-break
     below). Walk `card_text.splitlines()` matching `_RE_REFS_HEADER`
     (module-level, already defined at line 79) where
     `m.group(1) == "Edits"`; for the inline form extract
     `re.findall(r"`([^`]+)`", inline)`, for the multi-line form walk
     `_RE_REFS_SUB` (line 94) sub-bullets the same way `_card_own_reference_set`
     does at line 1408 (mirror that function's two-branch inline/sub-bullet
     walk, but scoped to the `Edits` field only and returning an ordered list
     instead of a set). An inline value of `none` naturally yields zero tokens
     since `none` is not backtick-wrapped.

  3. `_requirements_fence_aware_body(card_lines: list[str]) -> str | None`:
     locate the `Requirements:` header's line index by matching
     `re.compile(r"^-\s*\*\*Requirements:\*\*")` directly against
     `card_lines` (do NOT call `_extract_requirements_text` for this
     purpose — per `_mill/discussion.md`'s `fence-aware-boundary-detection`
     Decision, that function returns a joined string, not an index). Return
     `None` if no such line exists. From the found index, walk forward over
     the ORIGINAL (untruncated) `card_lines`, tracking a boolean `in_fence`
     that toggles on every line whose `.startswith("```")` (the header line
     itself does not toggle it — fences never start on the header line in
     this codebase's convention). Collect lines into the result until either
     (a) a line matches `re.compile(r"^-\s*\*\*[A-Za-z]+:\*\*")` (the same
     pattern as `_extract_requirements_text`'s `any_field_header_re`) while
     `in_fence` is `False` — stop before that line, or (b) `card_lines` is
     exhausted. Join collected lines with `"\n"` and return. This re-scan
     exists so a fence quoting another SKILL.md's `### Phase: X` heading or
     `- **Field:**`-shaped bullet does not get mistaken for this field's own
     boundary and truncate the fence body — see the Decision's rationale for
     why this is scoped to the `Requirements:`-field boundary only, not
     `_parse_cards`'s pre-existing (and here, out-of-scope) card-boundary
     non-fence-awareness.

  4. `_check_requirements_quote_indent_drift(batch_files: list[Path], project_root: Path, root: str | None, *, wiki_root: Path | None = None, git_root: Path | None = None) -> list[dict]`:
     same parameter shape as `_check_context_completeness` minus the
     `creates_union`/`deletes_union`/`moves_targets` args (not needed — this
     check only ever compares against `Edits:` files, which by definition
     already exist on disk, per `_mill/discussion.md`'s
     `match-target-edits-only` Decision). Define a module-level fence regex
     `re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)` (there is no existing
     fence-parsing helper anywhere in this file — confirmed by grep) next to
     the other module-level regex constants (near line 91-97), and use it,
     not an inline literal, inside the check function. Body:
     - For each `batch_path` in `batch_files`, read its text and call
       `_parse_cards(text)` (line 120) exactly like `_check_context_completeness`
       does.
     - For each `(card_num, card_lines)`: compute
       `edits_tokens = _card_edits_tokens("\n".join(card_lines))`; if empty,
       `continue` (no-op card per the `clean_no_edits_field` test).
     - Compute `requirements_text = _requirements_fence_aware_body(card_lines)`;
       if `None`, `continue`.
     - Find all fence bodies via the module-level fence regex's
       `.findall(requirements_text)`; if none, `continue`. Iterate every
       fence found (a Requirements: field may legitimately contain more than
       one fence) — 1-indexed as `fence_idx` for the error message.
     - Resolve `edits_tokens` to real files, in order, using
       `resolve_existing_paths([token], project_root, root, wiki_root=wiki_root, git_root=git_root)`
       (imported at line 71) for each token; keep only tokens that resolved
       (silently drop tokens that don't resolve to an on-disk file — e.g. a
       stale/typo'd `Edits:` entry is `non-existent-path`'s concern, not
       this check's). If nothing resolved for the card, `continue` past the
       whole card (skip all its fences).
     - Read each resolved file's content once per card (not once per fence),
       normalizing `"\r\n"` to `"\n"` — per `_mill/discussion.md`'s
       line-ending-normalization Technical-context bullet, this prevents a
       false negative when the plan file's fence uses `\n` but the target
       file on disk was checked out with `\r\n`. Build a `dict[str, str]`
       mapping each resolved token to its normalized content, preserving
       `edits_tokens`' declaration order separately (the dict alone does not
       preserve order in the tie-break sense needed below — iterate the
       ordered `edits_tokens` list, not the dict, when searching for a
       match).
     - For each fence body: normalize its own `"\r\n"` to `"\n"` too. First,
       check whether the raw (unstripped) normalized fence is already a
       literal substring of ANY resolved file's content — if so, `continue`
       to the next fence (this is the "already byte-exact, nothing to flag"
       case; also correctly no-ops for a fence with zero leading whitespace,
       since every `N >= 1` strip on such a fence is a no-op that reduces to
       this same already-checked raw content). Otherwise, loop `n` from `1`
       to `40` inclusive (ascending): compute
       `stripped = _strip_n_leading_spaces(normalized_fence, n)`; walk
       `edits_tokens` in declaration order and check `stripped in content`
       against each token's normalized content, taking the FIRST token (in
       declaration order) that matches — per `_mill/discussion.md`'s
       `edits-tie-break` Decision. The moment any token matches at the
       current `n`, append exactly one error dict (see shape below) and
       `break` out of the `n` loop entirely (ascending-`n`, first-match-wins
       — do not continue searching higher `n` once a hit is found at a lower
       one, even if a different file would also match at a higher `n`). If
       no `n` in `1..40` matches for any token, no error is emitted for that
       fence (the "illustrative snippet showing new code" case).
     - Error dict shape (exactly `{check, batch, card, path, message}`, no
       new keys — this is `run()`'s documented return contract):
       `check` = the literal string `"requirements-quote-indent-drift"`;
       `batch` = `batch_path.stem`; `card` = `card_num`; `path` = the
       matched token (the `Edits:` file path the stripped content matched
       against); `message` = a string naming the card, the fence index, the
       matched path, and the matched strip amount `n`, e.g.
       `f"card {card_num}'s Requirements: fence {fence_idx} matches '{matched_token}' after stripping {n} leading spaces per line (found N={n})"`.
       The `message` must carry the numeral `n` in a way `mill-plan`'s
       Step 1.5 fixer can parse back out (the literal substring `N={n}` is
       sufficient and matches this codebase's existing message-embeds-data
       convention, e.g. `verify-not-isolated`'s payload shape).
  5. Wire the new check into `run()` (around line 2500-2504, immediately
     after the existing `_check_context_completeness(...)` call and before
     the `_check_all_files_touched_mismatch(...)` call): add
     `errors.extend(_check_requirements_quote_indent_drift(batch_files, project_root, effective_root, wiki_root=wiki_root, git_root=git_root))`.
  6. Add one new entry to the module-level docstring's "Checks performed
     (check keys):" list (top of file, immediately after the existing
     `context-completeness` entry around line 43-45), in the same
     one-line-summary style as its neighbors, e.g.
     `requirements-quote-indent-drift — a card's Requirements: fenced block quoting exact source text that only byte-matches its own Edits: file(s) after stripping a fixed per-line indent (list-continuation-indentation bug signature)`.
- **Commit:** `feat(plan-validate): add requirements-quote-indent-drift check`

### Card 2: Document the check's fix and the write-time guidance in `mill-plan/SKILL.md`

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Two edits to `plugins/mill/skills/mill-plan/SKILL.md`, both already
  precisely specified by `_mill/discussion.md`'s Technical context section
  (this card restates them verbatim so the implementer does not need to
  cross-reference `_mill/discussion.md`):

  1. In the Step 1.5 fix table (around line 141-165), add one new row
     immediately after the existing `context-completeness` row (around line
     157), following the exact `| check | mechanical fix |` column format of
     its neighbors. `check` column: `requirements-quote-indent-drift`.
     `mechanical fix` column text: "Locate the card's `Requirements:` fence
     identified by the error payload's `message` (its first line/snippet and
     the reported strip amount `N`). Strip exactly `N` leading space
     characters from each line of the fence body (not necessarily to column
     0 — preserve whatever baseline indentation remains after the strip) so
     its content is a literal byte-exact substring of the target `Edits:`
     file named in the payload's `path` field." Use the literal
     `` `Requirements:` ``, `` `N` ``, `` `Edits:` `` backtick-wrapping shown
     here, matching the neighboring rows' style.

  2. In the `## Principles` section's existing `Requirements:` bullet (around
     line 278, the one starting "`Requirements:` must use stable
     identifiers" and currently ending "...forces the implementer to
     explore, defeating the cold-start guarantee."), append one new sentence
     (same bullet, not a new bullet) reading: "Any fenced block quoting exact
     source text inside `Requirements:` must reproduce the source's own
     original indentation byte-for-byte and must NOT pick up extra leading
     whitespace from the surrounding list item's continuation indent —
     author such fences so their content, read literally, is already a
     byte-exact substring of the file being quoted, regardless of how deeply
     the enclosing list item is nested (the source excerpt may legitimately
     have its own nonzero baseline indentation — e.g. quoting an indented
     method body — the rule is 'no *extra* indentation beyond the source's
     own,' not 'no indentation at all')." Do not create a new subsection —
     per `_mill/discussion.md`'s `doc-placement-principles-bullet` Decision,
     this bullet is already the canonical home for `Requirements:`-authoring
     rules and a one-sentence rule does not warrant new subsection ceremony
     (contrast `## Rename mechanic`, which needed a full subsection for
     multiple ordered steps).
- **Commit:** `docs(mill-plan): warn against Requirements: fence indent drift and add fix-table row`

### Card 3: Add the nine `requirements-quote-indent-drift` unit tests

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add nine new test functions to
  `plugins/mill/unit_tests/test-plan-validate.py`, following the exact
  `_make_batch_file`/`_write_plan`/assert-and-print-PASS-or-FAIL/return-0-or-1
  pattern used by every neighboring `test_check_context_completeness_*`
  function (see e.g. `test_check_context_completeness_dirty_missing` around
  line 1639 for the exact shape to mirror: build a `tempfile.TemporaryDirectory()`,
  write target file(s) under `project_root`, build batch text via
  `_make_batch_file(..., edits=[...], requirements="...")` — note
  `_make_batch_file`'s `requirements` kwarg writes the given text verbatim
  as the field body, letting these tests embed real fence syntax — write via
  `_write_plan`, call `_plan_validate.run(plan_dir, project_root)`, filter
  `result` for `e["check"] == "requirements-quote-indent-drift"`, assert the
  expected count and (for dirty tests) the expected `card`/`path` fields,
  print `PASS <name>`/`FAIL <name>: <exc>`, return `0`/`1`). Insert the new
  functions immediately after
  `test_check_context_completeness_dirty_line_range_suffix_missing` (the
  last existing `context-completeness` test) and before the
  `# skip_checks filtering (Card 7 / #188)` comment (around line 4972-4973).
  Also add all nine new function names to the `tests = [...]` list inside
  `main()` (around line 4959-4972), inserted in the same location under a
  new comment `# requirements-quote-indent-drift check (mill-plan-requirements-byte-exactness-gap)`,
  directly after the `test_check_context_completeness_*` entries and before
  the `# skip_checks filtering (Card 7 / #188)` comment. The nine functions,
  exactly as named and specified in `_mill/discussion.md`'s `## Testing`
  section:

  1. `test_check_requirements_quote_indent_drift_clean_exact_match`: a card
     with `edits=["src/target.py"]` where `src/target.py`'s on-disk content
     contains a line, and the batch's `Requirements:` fence body is already
     byte-identical to that line (no leading-space drift to strip) → assert
     zero `requirements-quote-indent-drift` errors.
  2. `test_check_requirements_quote_indent_drift_clean_illustrative_snippet`:
     a card with `edits=["src/target.py"]` where the fence body shows
     plausible-looking but different code that is not a substring of
     `src/target.py`'s content at any `n` in `1..40` → assert zero errors
     (proves the near-miss heuristic does not false-positive on legitimate
     illustrative fences).
  3. `test_check_requirements_quote_indent_drift_clean_no_edits_field`: a
     card with `edits=None` (renders as `Edits: none`) and any
     `requirements` fence body → assert zero errors (the check is a no-op
     with nothing to compare against).
  4. `test_check_requirements_quote_indent_drift_dirty_list_continuation_indent`:
     `src/target.py`'s on-disk content contains a flush-left (zero baseline
     indent) multi-line snippet; the fence body is that exact snippet with a
     uniform number of extra leading spaces (e.g. 2) prepended to every line
     — raw fence content is NOT a substring of the file, but stripping 2
     leading spaces per line IS → assert exactly one error, with `card == 1`,
     `path == "src/target.py"`, and `message` containing the substring
     `"N=2"`.
  5. `test_check_requirements_quote_indent_drift_dirty_nonzero_baseline_indent`:
     `src/target.py`'s on-disk content contains a multi-line snippet already
     indented 4 spaces per line (e.g. simulating a method body); the fence
     body is that same snippet with a further uniform 2 extra spaces per
     line prepended (i.e. 6 total) — raw is not a substring, but stripping
     exactly 2 (leaving the original 4-space baseline intact) IS a substring
     → assert exactly one error with `message` containing `"N=2"`, proving
     the ranged search recovers drift when the true excerpt is not flush at
     column 0 (the case `textwrap.dedent`'s common-minimum-strip would have
     missed).
  6. `test_check_requirements_quote_indent_drift_dirty_multiple_fences_one_card`:
     a `requirements` field body containing two separate fenced blocks (two
     ` ``` `-delimited sections) under the same card, where only the second
     fence has the list-continuation-indent drift bug against
     `src/target.py`'s content (the first fence is already byte-exact, or is
     an unrelated illustrative snippet) → assert exactly one error total,
     and that its `message` identifies the drifted fence (e.g. via the
     `fence_idx` reflected in the message, or by asserting the message's
     content snippet matches the second fence's text, not the first's).
  7. `test_check_requirements_quote_indent_drift_dirty_crlf_source_lf_fence`:
     write `src/target.py` to disk with `\r\n` line endings (e.g.
     `"line one\r\nline two\r\n"` containing the target snippet), while the
     plan batch file's `requirements` fence body uses plain `\n` line
     endings for the same snippet content, with a uniform list-continuation
     indent bug applied on top (raw does not match; some `n` in `1..40`
     matches only after both the `\r\n`-to-`\n` normalization AND the `n`-space
     strip are applied) → assert exactly one error fires, proving the
     line-ending normalization step runs before the substring comparison
     (without it, this case would false-negative since raw `\r\n` bytes on
     disk never equal `\n` bytes in the fence even after the correct `n` is
     stripped).
  8. `test_check_requirements_quote_indent_drift_dirty_fence_contains_nested_heading`:
     the drifted fence's body itself contains a line starting with `### `
     and a line shaped like `- **SomeField:**` (simulating a `Requirements:`
     fence that quotes a chunk of another SKILL.md file), with the
     list-continuation-indent drift bug also present → assert exactly one
     error fires, proving `_requirements_fence_aware_body`'s `in_fence`
     tracking is not fooled by field/heading look-alike lines nested inside
     the fence. If constructing this fixture via `_make_batch_file` (which
     routes through `_parse_cards` when `_plan_validate.run` is called)
     causes `_parse_cards`'s own pre-existing, out-of-scope card-boundary
     logic to mis-split on the nested `### ` line before this check ever
     sees the card, build the test's expected batch-file text as a raw
     string directly (bypassing `_make_batch_file` for this one test only)
     so the fixture's card boundary is unambiguous and the test isolates
     `_requirements_fence_aware_body`'s field-boundary fence-awareness from
     that separate, out-of-scope limitation; verify empirically which
     approach is needed while implementing this test.
  9. `test_check_requirements_quote_indent_drift_dirty_multiple_edits_tie_break`:
     a card with `edits=["src/first.py", "src/second.py"]` where BOTH
     `src/first.py`'s and `src/second.py`'s on-disk content independently
     contain the same `n`-stripped fence content as a literal substring (at
     the same `n`) → assert exactly one error, whose `path` field equals
     `"src/first.py"` (the first-listed `Edits:` file, per the
     `edits-tie-break` Decision), not `"src/second.py"`.
- **Commit:** `test(plan-validate): add requirements-quote-indent-drift clean/dirty coverage`

## Batch Tests

`verify:` runs the whole `test-plan-validate.py` file via `run-all.py --only
test-plan-validate.py` (not a narrower `-k`-style filter, since this file's
runner takes whole-file names, not individual test-function names) —
appropriate here because Card 1 wires the new check directly into
`_plan_validate.run()`, and `test-plan-validate.py` already contains
`test_run_returns_sorted`/`test_run_no_overview` meta-tests plus every other
check's clean/dirty pairs that exercise the same `run()` entry point; a
narrower scope would risk missing a regression the new check's wiring
introduces into an existing check's error ordering or aggregation. This
mirrors how `_check_requirements_quote_indent_drift` was itself planned as a
sibling of `_check_context_completeness` — same file, same test file, same
`run()` wiring point.
