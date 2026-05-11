# Batch: review-common-divergence-warning

```yaml
task: 44 (A) — Bug-fix batch 4
batch: review-common-divergence-warning
number: 3
cards: 2
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common.py
depends-on: []
```

## Batch Scope

Surface divergence between the heading-count `parse_blocking_count` returns and any prose count present in the review output (e.g. "Five blocking issues remain"). The returned integer is NOT changed — only a single stderr warning is emitted when the counts disagree. This is a soft signal for log inspection (#225); it does NOT alter the orchestrator's verdict branch.

## Cards

### Card 5: Add prose-count divergence warning to `_review_common.parse_blocking_count`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Define a private helper `_warn_if_prose_diverges(raw_output: str, severity: str, heading_count: int) -> None` immediately above `parse_blocking_count`. It scans `raw_output` for a prose count phrase matching the regex (case-insensitive, MULTILINE off) built from the severity argument: `pattern = re.compile(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+" + re.escape(severity), re.IGNORECASE)`. The severity is interpolated verbatim into the regex; `re.IGNORECASE` makes the comparison case-blind for BLOCKING / blocking / Blocking. This lets the same helper serve discussion-review GAP-severity calls (matches "Three gaps remain") as well as plan/code BLOCKING calls. Word-to-int mapping for the spelled-out forms uses a literal dict (`{"one":1, "two":2, ..., "ten":10}`). If at least one match is found, take the FIRST match's numeric value as `prose_count`. If `prose_count != heading_count`, emit one stderr line: `[_review_common] warning: parse_blocking_count heading count {heading_count} diverges from prose count {prose_count} (severity={severity}) — check review file for missing heading.` If no prose match, return silently.
  2. At the bottom of `parse_blocking_count`, immediately before `return len(pattern.findall(raw_output))`, store the count in a local `heading_count` and call `_warn_if_prose_diverges(raw_output, severity, heading_count)`. Return `heading_count`. No other code-path change.
  3. Do NOT change the docstring's "Match is case-sensitive" line for the heading-count regex — case-sensitivity of `### [BLOCKING]` headings is unchanged. Append a new docstring paragraph: `Emits a one-line stderr warning when a prose count phrase in the output (e.g. "Five blocking issues remain") disagrees with the heading count. The returned count is unchanged; the warning is for log inspection only (#225).`
  4. Do not change `parse_verdict`, `write_review_file`, or any other function in this file.
- **Commit:** `fix(_review_common): warn on prose/heading blocking-count divergence (#225)`

### Card 6: Unit-test `parse_blocking_count` divergence warning

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add four new test functions:
  1. `test_parse_blocking_count_warns_on_prose_divergence_numeric` — input has 3 `### [BLOCKING]` headings AND the prose "5 blocking findings". Call `parse_blocking_count(raw, severity="BLOCKING")` while capturing stderr (use `contextlib.redirect_stderr` and `io.StringIO`). Assert returned count is 3, stderr contains the literal substring `heading count 3 diverges from prose count 5`.
  2. `test_parse_blocking_count_warns_on_prose_divergence_spelled` — input has 3 headings AND the prose "Five blocking issues remain". Same assertions, prose count parsed to 5.
  3. `test_parse_blocking_count_silent_when_aligned` — input has 3 headings AND the prose "3 blocking issues". Captured stderr is empty (no warning).
  4. `test_parse_blocking_count_silent_when_no_prose_count` — input has 3 headings AND no prose match. Captured stderr is empty.
  5. `test_parse_blocking_count_warns_for_gap_severity` — input has 2 `### [GAP]` headings AND the prose "Three gaps remain". Call `parse_blocking_count(raw, severity="GAP")`. Assert returned count is 2, stderr contains `heading count 2 diverges from prose count 3 (severity=GAP)`. This proves the severity-parametrized regex works for non-BLOCKING callers (discussion-review path).
  Each test uses inline raw_output strings (no fixture files). The pattern is identical to existing `parse_verdict` tests in the file; reuse helper imports.
- **Commit:** `test(_review_common): cover parse_blocking_count divergence warning`

## Batch Tests

`verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common.py`. The four new tests above must pass; all pre-existing tests in the file must continue to pass.
