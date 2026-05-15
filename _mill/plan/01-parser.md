# Batch: parser

```yaml
task: Wrap claude -p via psmux to use subscription instead of API credits
batch: parser
number: 1
cards: 4
verify: python plugins/mill/unit_tests/test-psmux-capture.py
depends-on: []
```

## Batch Scope

This batch delivers the pure-Python output parser
`_psmux_capture.extract_response(capture_text, begin_marker, end_marker) -> str`
plus its unit tests and fixtures. The parser slices Claude's response out of
a psmux capture-pane snapshot using the dual-marker protocol agreed in
`_mill/discussion.md`. The parser has zero psmux dependency -- it operates on
strings only -- and is the foundation the wrapper (batch 03) calls on every
poll cycle.

**External interface for batch 03:** `extract_response(capture_text: str,
begin_marker: str, end_marker: str) -> str`, raising `MarkerNotFoundError`
when either marker is missing or the end marker does not appear after the
begin marker. No other public symbols.

**Batch-local decisions:**
- Test-first within the batch: card 1 writes the stub (so imports work),
  card 2 writes fixtures, card 3 writes tests, card 4 implements the
  parser logic to pass the tests.
- Markers in fixtures are the literal strings `MILL_BEGIN_AAA` and
  `MILL_END_BBB` (not real random hex) -- fixtures are static inputs;
  randomness belongs in the wrapper, not the test corpus.
- Fixtures contain only the input capture text. Expected outputs live as
  string constants inside `test-psmux-capture.py` -- no `.expected.txt`
  sidecars.


## Cards

### Card 1: parser stub and exception class

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_llm_common.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_psmux_capture.py`
- **Deletes:** none
- **Requirements:** Module docstring stating the parser is the pure-function
  output parser for psmux capture-pane text used by `millpy-claude-sub.py`,
  with no psmux subprocess dependency. Define `class MarkerNotFoundError(Exception)`
  with a one-line docstring. Define
  `def extract_response(capture_text: str, begin_marker: str, end_marker: str) -> str:`
  whose body is `raise NotImplementedError("implemented in card 4")`. ASCII
  only in module/source strings (docstrings may contain UTF-8 prose). The
  module must import cleanly with no side effects.
- **Commit:** `feat(mill): add _psmux_capture parser stub`

### Card 2: parser test fixtures

- **Context:**
  - `_mill/discussion.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/fixtures/psmux-capture/clean.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/multiline.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/with-status.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/with-scrollback.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/whitespace-compressed.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/quoted-marker-text.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/no-end-marker.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/markers-reversed.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/polling-not-ready.txt`
- **Deletes:** none
- **Requirements:** Each fixture is a verbatim psmux capture-pane snapshot
  pattern matching the cases in `_mill/discussion.md` `## Testing` section.
  Use the literal marker strings `MILL_BEGIN_AAA` and `MILL_END_BBB`
  throughout. UTF-8 encoded, LF line endings, no BOM. Each fixture is the
  capture INPUT only; expected outputs are not stored as files. Specific
  contents:
  - `clean.txt`: minimal pwsh prompt header line, the `MILL_BEGIN_AAA`
    marker on its own line, a single response line `PONG`, the
    `MILL_END_BBB` marker on its own line, an empty trailing pwsh prompt.
  - `multiline.txt`: marker on its own line, three lines of haiku-style
    response (each line non-empty, including a `PowerShellthreadsweaveasone`
    line that mirrors the TUI whitespace artifact), end marker.
  - `with-status.txt`: marker, two-line response, end marker, then a
    `*Crunched for 3s` status line BELOW the end marker (asserts the
    parser stops at the end marker).
  - `with-scrollback.txt`: marker, then 80 numbered lines `LINE_1` through
    `LINE_80`, then end marker. Used to assert the parser handles long
    payloads without truncation.
  - `whitespace-compressed.txt`: marker, single response line missing a
    space between two adjacent words, end marker. Asserts the parser
    passes the line through unchanged.
  - `quoted-marker-text.txt`: marker, response that mentions both
    `MILL_BEGIN_AAA` and `MILL_END_BBB` mid-line (e.g. inside backticks
    or quotes), then a final end-marker on its own line. Asserts only
    standalone-line markers count.
  - `no-end-marker.txt`: begin marker present, response present, end
    marker absent. Asserts `MarkerNotFoundError`.
  - `markers-reversed.txt`: end marker appears BEFORE begin marker in the
    capture (both present, both standalone). Asserts `MarkerNotFoundError`.
  - `polling-not-ready.txt`: begin marker present, response in progress
    (e.g. `PON` partial line), end marker absent. Asserts
    `MarkerNotFoundError` (the polling-loop's expected interim state).
- **Commit:** `test(mill): add psmux-capture parser fixtures`

### Card 3: parser tests

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_psmux_capture.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/clean.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/multiline.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/with-status.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/with-scrollback.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/whitespace-compressed.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/quoted-marker-text.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/no-end-marker.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/markers-reversed.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/polling-not-ready.txt`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-psmux-capture.py`
- **Deletes:** none
- **Requirements:** Module docstring naming the file under test. Mirror
  the `def main() -> int` runner pattern from
  `plugins/mill/unit_tests/test-llm-claude.py` (sys.path insert,
  per-test counters, `if __name__ == "__main__": sys.exit(main())`).
  Resolve fixtures via `Path(__file__).resolve().parent / "fixtures" /
  "psmux-capture" / "<name>.txt"`. Use markers `MILL_BEGIN_AAA` and
  `MILL_END_BBB` in every call. Nine tests, one per fixture:
  1. `clean.txt` -> assert returns the literal string `"PONG"`.
  2. `multiline.txt` -> assert returns the three response lines joined
     by `"\n"` (verify the exact string against an inline constant in
     the test file).
  3. `with-status.txt` -> assert returns the two-line response (the
     `*Crunched for 3s` line is NOT included).
  4. `with-scrollback.txt` -> assert returns the 80 numbered lines
     joined by `"\n"` (build the expected via
     `"\n".join(f"LINE_{i}" for i in range(1, 81))`).
  5. `whitespace-compressed.txt` -> assert returns the response line
     verbatim, including the missing space (the parser does not edit
     whitespace).
  6. `quoted-marker-text.txt` -> assert returns the response with the
     mid-line marker mentions intact (only standalone-line markers
     terminate the slice).
  7. `no-end-marker.txt` -> assert calling
     `_psmux_capture.extract_response(...)` raises
     `MarkerNotFoundError`.
  8. `markers-reversed.txt` -> assert raises `MarkerNotFoundError`.
  9. `polling-not-ready.txt` -> assert raises `MarkerNotFoundError`.
  All assertions ASCII-only (use `[FAIL]` / `[OK]` prefixes per
  `test-llm-claude.py` style). Tests must fail when run against the
  card 1 stub (proving they exercise the function); tests must pass
  after card 4.
- **Commit:** `test(mill): implement psmux-capture parser tests`

### Card 4: parser implementation

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/unit_tests/test-psmux-capture.py`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/clean.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/multiline.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/with-status.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/with-scrollback.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/whitespace-compressed.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/quoted-marker-text.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/no-end-marker.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/markers-reversed.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/polling-not-ready.txt`
- **Edits:**
  - `plugins/mill/scripts/_psmux_capture.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace the `NotImplementedError` body of
  `extract_response`. Algorithm:
  1. Split `capture_text` on `"\n"` preserving order; do not strip the
     list itself.
  2. Iterate the lines from index 0; record `begin_idx` as the first index
     `i` where `lines[i].strip() == begin_marker`.
  3. If no such index exists, raise
     `MarkerNotFoundError(f"begin marker {begin_marker!r} not found in
     capture")`.
  4. Iterate from `begin_idx + 1`; record `end_idx` as the first index `j`
     where `lines[j].strip() == end_marker`.
  5. If no such index exists, raise
     `MarkerNotFoundError(f"end marker {end_marker!r} not found after
     begin marker in capture")`.
  6. Return `"\n".join(lines[begin_idx + 1 : end_idx])`.
  Note: out-of-order markers (end before begin) naturally fail step 4
  because the search starts after begin_idx; do NOT add a separate check.
  Pure function; no I/O, no logging, no global state. Card 3's tests
  must pass in full after this card.
- **Commit:** `feat(mill): implement _psmux_capture.extract_response`

## Batch Tests

The batch is verified by `python plugins/mill/unit_tests/test-psmux-capture.py`
(also exercised by `python plugins/mill/unit_tests/run-all.py`). The test
file enumerates one assertion per fixture in `fixtures/psmux-capture/`.
Card 3 introduces the test file; card 4 implements the parser; the per-batch
verify command must exit 0 to pass.
