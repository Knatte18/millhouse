# Batch: context-completeness-exemptions-tests

```yaml
task: '_plan_validate.py context-completeness: path-token exemption list gaps'
batch: context-completeness-exemptions-tests
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: [1]
```

## Batch Scope

This batch adds unit tests for the three exemptions batch 1 (`01-context-completeness-exemptions.md`)
implemented, one card per exemption (cards 4-6, continuing batch 1's card numbering). It depends on
batch 1 because these tests assert on behavior batch 1's code provides; splitting it into its own
batch (rather than pairing each exemption's implementation and tests in one card) keeps this batch's
sole edited file, `plugins/mill/unit_tests/test-plan-validate.py` (~118k context-token estimate),
from combining with batch 1's `_plan_validate.py` (~44k) in one batch and exceeding
`pipeline.max_batch_context_tokens` (120000) — see `00-overview.md`'s Shared Decisions. Every card's
`Context:` is `none`: each test's exact expected string/count is already fully specified in this
card's own `Requirements:` below, so the implementer does not need to re-read `_plan_validate.py`
(added last batch) to write these tests correctly.

## Cards

### Card 4: Ownership exemption unit tests

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add the following test functions to `plugins/mill/unit_tests/test-plan-validate.py`, immediately
  after `test_check_context_completeness_dirty_quoted_material_prose_after_fence_closed` (the last
  existing `context-completeness` test in the file), following that same function's exact fixture
  pattern (`tempfile.TemporaryDirectory`, `_make_overview`, `_make_batch_file`, `_write_plan`,
  `_plan_validate.run(plan_dir, project_root)`, filter `result` to `check == "context-completeness"`,
  assert count, `try`/`except AssertionError` PASS/FAIL print convention identical to every existing
  test in this file):

  - `test_check_context_completeness_clean_ownership_batch_fixes` — a card whose `Requirements:`
    contains `` "the stale prose reference in `x.cs`, which batch 8 fixes." `` (verbatim `#1022`
    shape, comma before the ownership phrase) — asserts 0 `context-completeness` errors.
  - `test_check_context_completeness_clean_ownership_card_corrects` — `` "for the same reason card 23
    corrects one stale sentence in `golang.go`." `` — asserts 0 errors.
  - `test_check_context_completeness_clean_ownership_synonym_addresses` — `` "batch 4 addresses
    `y.py`." `` (a close-synonym verb, not one of the four issue-sourced verbs) — asserts 0 errors.
  - `test_check_context_completeness_clean_ownership_past_tense` — `` "batch 8 fixed `x.cs`." `` —
    asserts 0 errors (guards the hand-spelled past-tense form actually exists in
    `_OWNERSHIP_VERB_FORMS`).
  - `test_check_context_completeness_clean_ownership_possessive` — `` "batch 8's fix touches
    `x.cs`." `` — asserts 0 errors (guards the regex's optional `'s` group).
  - `test_check_context_completeness_dirty_ownership_no_number_not_exempted` — `` "batch fixes
    `x.py`." `` (no card/batch number) — asserts exactly 1 `context-completeness` error whose `path`
    is `x.py`, guarding against over-matching a bare "batch"/"card" mention with no number.
  - `test_check_context_completeness_dirty_ownership_separate_line_not_exempted` — a card whose
    `Requirements:` has the ownership phrase on one bullet line ("- batch 8 fixes something else.")
    and the token on a *different* bullet line ("- Read `x.py` for the new logic.") — asserts exactly
    1 `context-completeness` error whose `path` is `x.py`, confirming the exemption is genuinely
    line-scoped (not plan-wide or card-wide).

  Every path named in a fixture's `Requirements:` prose that is asserted clean (0 errors) must
  resolve to a real file under `project_root` in that test's own fixture setup (create the file with
  placeholder content, exactly as the existing contrast-citation tests do for `fixtures/alpha.py`),
  and every card must declare a real `Edits:` file unrelated to the tested path (the existing tests'
  `edits=["other.py"]` convention) so the fixture itself is otherwise structurally valid.
  Register each new test function in `main()`'s `tests` list, immediately after
  `test_check_context_completeness_dirty_quoted_material_prose_after_fence_closed` in that list, in
  the same order as the bullets above.
- **Commit:** `test(plan-validate): cover cross-card ownership context-completeness exemption`

### Card 5: Literal-enumeration exemption unit tests

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add the following test functions, immediately after Card 4's last added test function
  (`test_check_context_completeness_dirty_ownership_separate_line_not_exempted`), following the same
  fixture pattern Card 4 uses:

  - `test_check_context_completeness_clean_literal_enumeration_mixed_shapes` — a card whose `Requirements:` contains the verbatim `#984` test-input list (mentioned, not read): `` "`TestIsGlyphTarget` tables `isGlyphTarget` over at least `a/b#C`, `a/b`, `#x`, `a#b#c`, `README.md`, the empty string, and `.`, ..." `` — create a real `README.md` under
    `project_root` (so the token independently resolves, matching the reported false-positive's exact
    trigger condition) — asserts 0 `context-completeness` errors.
  - `test_check_context_completeness_dirty_literal_enumeration_below_threshold_not_exempted` — mentioned, not read, throughout this bullet — a card whose `Requirements:` contains only 2 backtick tokens on the line, one of them non-path-shaped and non-resolving (e.g. `` "Accepts `#x` or `README.md` as input." ``, with a real `README.md` on disk) — asserts exactly 1 `context-completeness` error whose `path` is `README.md` — below the 3-token threshold, so the exemption must NOT fire.
  - `test_check_context_completeness_dirty_literal_enumeration_all_path_shaped_not_exempted` — a card
    whose `Requirements:` contains 3+ backtick tokens, all path-shaped and all resolving to real
    files under `project_root` (e.g. `` "reads `a.py`, `b.py`, and `c.py` for the merge." `` with all
    three files created) — asserts exactly 3 `context-completeness` errors (a genuine multi-file
    dependency enumeration must never be swept in).

  Register each new test function in `main()`'s `tests` list, immediately after Card 4's last
  registered test, in the same order as the bullets above.
- **Commit:** `test(plan-validate): cover literal-value enumeration context-completeness exemption`

### Card 6: Illustrative-output exemption unit tests

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add the following test functions, immediately after Card 5's last added test function
  (`test_check_context_completeness_dirty_literal_enumeration_all_path_shaped_not_exempted`),
  following the same fixture pattern Card 4 uses. Every `README.md`/`./README.md` occurrence quoted below is a literal example string inside this card's own fixture description — mentioned, not read, never a file this plan card reads:

  - `test_check_context_completeness_clean_illustrative_output_emitting` — the verbatim `#985`
    sentence: `` "an answer whose `Dir` is `\".\"` emitting the bare `README.md`, never
    `./README.md`." `` (mentioned, not read) — create a real `README.md` under `project_root` —
    asserts 0 `context-completeness` errors.
  - `test_check_context_completeness_clean_illustrative_output_rendering` — `` "the view renders the
    bare `README.md` for a dot directory." `` (mentioned, not read) — asserts 0 errors (a second
    `_OUTPUT_VERB_FORMS` entry).
  - `test_check_context_completeness_clean_illustrative_output_printing` — `` "the CLI prints the
    bare `README.md` to stdout." `` (mentioned, not read) — asserts 0 errors (a third
    `_OUTPUT_VERB_FORMS` entry).
  - `test_check_context_completeness_clean_illustrative_output_past_tense` — `` "the answer emitted
    the bare `README.md`." `` (mentioned, not read) — asserts 0 errors (guards the hand-spelled
    past-tense form actually exists in `_OUTPUT_VERB_FORMS`).
  - `test_check_context_completeness_dirty_illustrative_output_no_verb_not_exempted` — mentioned, not read, throughout this bullet — a card whose `Requirements:` names `` `README.md` `` on a line with no output verb (e.g. "Read `README.md` for the project description.") — asserts exactly 1 `context-completeness` error whose `path` is `README.md`.

  Register each new test function in `main()`'s `tests` list, immediately after Card 5's last
  registered test, in the same order as the bullets above.
- **Commit:** `test(plan-validate): cover illustrative-output context-completeness exemption`

## Batch Tests

`verify:` runs `test-plan-validate.py` directly (a single test file, not the unbounded `run-all.py`)
— this is the file every card in this batch edits, and its own existing 200+ tests plus the 17 new
ones cards 4-6 add are the batch's complete test surface. No other test file imports or exercises
`_check_context_completeness`.
