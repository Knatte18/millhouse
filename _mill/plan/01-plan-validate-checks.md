# Batch: plan-validate-checks

```yaml
task: "_plan_validate and baseline verify gate gaps"
batch: "plan-validate-checks"
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py test-plan-validate-card-numbering.py test-plan-validate-indent-drift-line.py
depends-on: []
```

## Batch Scope

Two mechanical-gate improvements in `plugins/mill/scripts/_plan_validate.py`: a starts-at-1 check in the `card-numbering` check (#1142), and a numeric `line` locator on every `requirements-quote-indent-drift` error (#1143).
One batch because both edit the same module and share the `_parse_cards` helper family.
No later batch consumes an interface from this one.

## Cards

### Card 1: card-numbering starts-at-1 check

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate-card-numbering.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `_check_card_numbering`, after the existing within-batch and cross-batch checks, add a starts-at-1 check over `all_cards` (the `(stem, card_number)` list the function already builds).
  - Skip it when `all_cards` is empty.
  - Otherwise pick the minimum by `min(all_cards, key=lambda t: (t[1], t[0]))` so ties resolve deterministically to the alphabetically first batch stem.
  - When that minimum card number is not 1, append one error dict with `check: "card-numbering"`, `batch` set to the stem holding the minimum, `card: 1`, `path: None`, and `message` reading `card 1 breaks sequential numbering within batch <stem> (numbering starts at <min>, not 1)`.
  - The message prefix stays identical to the existing card-numbering messages so the fix-table row still applies.
  - Extend `test-plan-validate-card-numbering.py` (add tests and register them in its `main`) by calling `_plan_validate._check_card_numbering` directly on hand-written batch files containing only `### Card N: t` heading lines, the shape `_write_batch_file` in that file already produces.
  - Cases: cards `[2, 3]` in one batch produce exactly one error with `card == 1` and the minimum named in the message; cards `[1, 2]` produce none; a two-batch plan (`[1, 2]` and `[3, 4]`) produces none; a two-batch plan where only the later-file batch holds the minimum (`[3, 4]` in `01-a.md`, `[2]` in `02-b.md`) names the stem of the batch holding 2; an empty plan (batch files with no cards) produces none.
  - Run `test-plan-validate.py`; if an existing fixture there now fails only because its cards start above 1, fix that fixture to start at 1 (or adjust its assertion to the new extra finding when the fixture deliberately exercises a gap), and touch nothing else in that file.
- **Commit:** feat(plan-validate): flag card numbering that does not start at 1

### Card 2: line locator on requirements-quote-indent-drift errors

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-plan-validate-indent-drift-line.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add `_parse_cards_positioned(batch_text: str) -> list[tuple[int, list[str], int]]` returning `(card_number, card_lines, start_line)` where `start_line` is the 1-based line number in the batch file of the card's `### Card N:` heading; move the current `_parse_cards` scan into it unchanged apart from recording the start index, and reduce `_parse_cards` to a wrapper returning the first two tuple elements so every other caller is untouched.
  - Split the scan in `_requirements_fence_aware_body` into `_requirements_fence_aware_span(card_lines: list[str]) -> tuple[int, int] | None` returning `(header_index, end_index_exclusive)` into `card_lines` (same header regex, same fence toggle, same stop condition), and make `_requirements_fence_aware_body` return `"\n".join(card_lines[start:end])` from it with byte-identical output.
  - Add `_requirements_fence_open_lines(card_lines: list[str], card_start_line: int) -> list[int]`: over the span's lines after the header line, toggle `in_fence` on every line whose `lstrip()` starts with three backticks (the same convention as the two helpers above) and record `card_start_line + index_in_card_lines` each time the toggle turns on, so element k-1 is the file line of fence k's opening delimiter.
  - In `_check_requirements_quote_indent_drift`, iterate `_parse_cards_positioned`, compute the card's fence-open-line list once, and add `"line": <int>` to every error dict at all three emit sites (strip pass, add pass, new/replacement-code sibling-indent check) using the list element for that site's `fence_idx`.
  - When the list has no element for `fence_idx` (defensive; the two fence scanners disagree only on exotic mid-line backtick text), set `"line": None` and omit the line suffix from the message.
  - Message changes: the strip and add messages become `card N's Requirements: fence K (line L) matches 'P' after ...` with the remainder of the text unchanged; the sibling message becomes `card N's Requirements: fence K (line L, new/replacement code) immediately follows matched fence J, but its first line ...` with the remainder unchanged.
  - Update `test_check_requirements_quote_indent_drift_dirty_over_indent_message_frozen` in `test-plan-validate.py`: its fixture builds the batch via `_make_batch_file` and `_write_plan`; compute the expected line from the written batch file text (find the line index of the first fence delimiter) rather than hard-coding a guess, and change its expected message to include ` (line <L>)` after `fence 1`.
  - Run the whole of `test-plan-validate.py` and fix only assertions broken by the new message suffix.
  - Create `test-plan-validate-indent-drift-line.py` as a self-contained standalone test (tempfile fixtures, hand-written batch text, direct calls to `_plan_validate._check_requirements_quote_indent_drift(batch_files, project_root, None)`, a `main()` that runs each case, same `HUB`/`sys.path` bootstrap as `test-plan-validate-card-numbering.py`).
  - Fixtures use a source file `src/target.py` inside a temp project root and a batch file whose card is NOT the first thing in the file (put a preamble section and an earlier card above it) and whose target card has several fences, so the asserted line is neither 1 nor the first fence.
  - Cases: strip-pass error whose `line` equals the actual 1-based line of that fence's opening delimiter in the batch text (compute the expected value with `text.splitlines()`); add-pass error (a flattened fence whose source is indented) with the correct `line`; sibling-indent error (a clean matched fence followed by an unmatched fence indented differently) with the correct `line`; a card with a clean fence followed by a drifting second fence reports the second fence's line, not the first's; each message contains `(line <L>`.
- **Commit:** feat(plan-validate): add line locator to requirements-quote-indent-drift errors

## Batch Tests

`verify:` runs `run-all.py --only` over three files: `test-plan-validate.py` (edited by both cards: one frozen-message test and any fixture the new numbering check breaks), `test-plan-validate-card-numbering.py` (extended by card 1), and the new `test-plan-validate-indent-drift-line.py` (card 2).
The scope covers every test file this batch edits or creates and nothing broader.
