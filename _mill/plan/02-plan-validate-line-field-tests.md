# Batch: plan-validate-line-field-tests

```yaml
task: Improve diagnosability of plan-validate errors and finalize verify-replay failures
batch: plan-validate-line-field-tests
number: 2
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
depends-on: [1]
```

## Batch Scope

Test coverage for batch 1's new `line` field on `_check_context_completeness`'s error dicts, plus a regression test for the actual odd-backtick-count false-positive mechanism (corrected during discussion review from an earlier, incorrect split-across-two-lines theory). Split into its own batch, depending on batch 1, purely because `test-plan-validate.py` (252KB) combined with `_plan_validate.py` and `_mill/discussion.md` pushed batch 1's combined context estimate over `pipeline.max_batch_context_tokens` — there is no logical reason for this to be a separate unit of work otherwise.

## Cards

### Card 3: Extend `test-plan-validate.py` for the new field and the odd-backtick-count false positive

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. In `test_check_context_completeness_dirty_missing` (`test-plan-validate.py:1639`), add an assertion immediately after the existing `assert e["path"] == "src/helper.py", ...` line: `assert e["line"] == "See \`src/helper.py\` for the pattern to follow.", f"wrong line: {e['line']!r}"`. The fixture's `requirements` string is `"  See \`src/helper.py\` for the pattern to follow.\n"` (a single line); `.strip()` on that line yields exactly this expected value.
  2. Add a new test function `test_check_context_completeness_dirty_odd_backtick_count_line_field` reproducing the actual false-positive mechanism from `_mill/discussion.md`'s Gap 1 Problem section (the corrected, single-line mechanism — NOT a two-line-split reference, which `backtick_re.findall(line)` cannot mis-pair since it carries no state across lines). Construct a `Requirements:` fixture containing one line with an ODD number of backtick characters positioned so `backtick_re.findall(line)`'s greedy left-to-right pairing groups an unintended span of text between two backticks that were never meant to delimit a path reference (e.g. a stray backtick from an incompletely-closed quote sitting between two otherwise-independent backtick-quoted references on the same line), such that the resulting mis-paired token is path-shaped enough to pass the `"/" in token or token.endswith(_PATH_CANDIDATE_EXTENSIONS)` filter and independently resolve as an existing file not present in the card's own refs — reproducing the observed "bare `/`"-shaped false positive. Assert exactly one `context-completeness` error is produced for the card, and assert its `line` field equals that single malformed line (`.strip()`ped) verbatim — not any other line in the card's `Requirements:` block. Follow the existing tests' `_make_overview`/`_make_batch_file`/`_write_plan` fixture helpers and this file's PASS/FAIL print-and-return-code convention.
- **Commit:** `test(plan-validate): cover new line field and odd-backtick-count false positive`

## Batch Tests

`verify:` runs `run-all.py --only test-plan-validate.py`, the sole test file this batch modifies.
