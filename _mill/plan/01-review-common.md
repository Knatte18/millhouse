# Batch: review-common

```yaml
task: "61 (A) -- Review pipeline fixes"
batch: review-common
number: 1
cards: 3
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Three independent fixes inside `_review_common.py` and its companion unit-test file. (1) Add a `.ipynb`-aware reader so that `bulk_files` and `bulk_files_with_diff` include only cell-source for Jupyter notebooks, not the megabyte-scale cell-output payload (#308). (2) Add a UTC-timestamp regression test for `write_review_file` so the proposal's #317 observation (review filenames in local time) cannot regress (#317). (3) Extend `parse_verdict` test coverage to lock in the already-working scan-anywhere behaviour against multiple yaml blocks, trailing prose, and yaml fences with trailing whitespace (#315 part 1). No public API surface changes; all changes are additive.

Batch tests run via `python plugins/mill/unit_tests/run-all.py`. The bulker change is mode-additive (`.ipynb` extension dispatch); non-notebook reads are unchanged.

## Cards

### Card 1: ipynb-aware reader in _review_common

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add a module-level helper `_read_for_bulk(p: Path) -> str` to `plugins/mill/scripts/_review_common.py`. Place it directly above `bulk_files` (after the `parse_missing_context` block, before the `bulk_files` definition).
  - Behaviour: when `p.suffix == ".ipynb"`, read the file as UTF-8, `json.loads` the content, and return `"\n\n".join(...)` over each cell `c` in `notebook.get("cells", [])` where `c.get("cell_type") in ("code", "markdown")`. For each matching cell, compute the source as: if `c["source"]` is a list, `"".join(c["source"])`; otherwise treat it as a string. Cells of other types (e.g. `"raw"`) are skipped. For any other extension, return `p.read_text(encoding="utf-8", errors="replace")` (the existing behaviour). On `json.JSONDecodeError` while parsing `.ipynb`, print a one-line ASCII-only warning to stderr starting with `[_read_for_bulk] warning:` and return the empty string `""` so the file shows up as `--- FILE: ... ---\n\n` in the bulk (visible to operator, non-crashing).
  - Add `import json` to the top-of-file imports if not already present (`_review_common.py` already imports `json` only inside `_scan_rate_limit`-style helpers; add a top-level `import json` so the helper is self-contained).
  - Edit `bulk_files` (currently at `plugins/mill/scripts/_review_common.py:691`): replace the inner `p.read_text(encoding="utf-8")` with a call to `_read_for_bulk(p)`. Keep the existing `try/except FileNotFoundError` block unchanged (the new helper does not need to handle missing-file; `_read_for_bulk` is only called when the path exists).
  - Edit `bulk_files_with_diff` (currently at `plugins/mill/scripts/_review_common.py:707`): replace the inner `p.read_text(encoding="utf-8", errors="replace")` with `_read_for_bulk(p)`. Note: `bulk_files_with_diff` may still emit a `--- DIFF: ... ---` block for small diffs; the diff path is unchanged. The helper substitution only affects the `--- FILE: ... ---` full-content branch.
  - Add a new `def _test_read_for_bulk_ipynb()` group to `plugins/mill/unit_tests/test-review-common.py` (place it adjacent to the existing `bulk_files` tests, alphabetically ordered by helper name within the file is acceptable). Cases (one assert per case, distinct print-on-pass lines per existing convention):
    - Code-cell-only notebook -> source concatenated with `\n\n` separator.
    - Markdown-cell-only notebook -> source concatenated.
    - Mixed code + markdown -> both sources, in document order, separated by `\n\n`.
    - Cell with `source` as a list of strings -> joined via `"".join(...)`.
    - Cell with `source` as a single string -> returned verbatim.
    - Raw-cell present -> skipped (not included in output).
    - Non-`.ipynb` file (e.g. `.py`) -> existing `p.read_text` behaviour.
    - Malformed JSON `.ipynb` -> returns `""` and prints a warning to stderr containing `[_read_for_bulk]` (use `capsys` if available; otherwise capture stderr via `contextlib.redirect_stderr` and assert the prefix is present).
  - Use `tempfile.TemporaryDirectory` for the fixtures (project convention). Build notebook fixtures by writing `json.dumps(...)` to a `.ipynb` file in the temp dir. Do NOT add a real `.ipynb` artifact to the repo.
- **Commit:** `fix(review): ipynb-aware reader in _review_common bulker (#308)`

### Card 2: UTC-timestamp regression test for write_review_file

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add a regression test `def _test_write_review_file_utc_timestamp()` to `plugins/mill/unit_tests/test-review-common.py`. Place it adjacent to other `write_review_file` tests.
  - Strategy: monkeypatch `_review_common.datetime` with a stub class whose `.now(tz)` returns a fixed UTC instant (use a `unittest.mock.patch` or a simple monkey-patch via `setattr`). Pass `datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)` as the frozen instant.
  - Cases:
    - Call `write_review_file(reviews_dir, "code", 1, "raw", scope=None)` and assert the returned `Path.name == "20260102-030405-code-review-r1.md"`.
    - Repeat with `scope="holistic"` -> same filename (no scope segment).
    - Repeat with `scope="01-foundation"` -> `"20260102-030405-code-review-01-foundation-r1.md"`.
    - Repeat with `review_type="discussion"` (scope ignored for discussion) -> `"20260102-030405-discussion-review-r1.md"`.
    - Repeat with `review_type="plan"` and `scope="01-foundation"` -> `"20260102-030405-plan-review-01-foundation-r1.md"`.
  - Use `tempfile.TemporaryDirectory()` for `reviews_dir`. Assert each file exists on disk after writing.
  - Drop the previously-described guard test; the frozen-clock test above is sufficient to lock UTC behaviour. (A `mock.assert_called_with(timezone.utc)` guard is not added because `datetime.now(timezone.utc)` passes the timezone positionally, making the assertion brittle and redundant with the frozen-clock assertion.)
- **Commit:** `test(review-common): regression for utc timestamps in write_review_file (#317)`

### Card 3: extend parse_verdict test coverage

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add new cases to the existing `parse_verdict` test block in `plugins/mill/unit_tests/test-review-common.py` (around line 383-424). Keep the existing PASS-on-print convention.
  - Cases (one assertion + one PASS print per case):
    - **Multiple yaml blocks; first wins.** Input: `"# Header\n\n```yaml\nverdict: APPROVE\n```\n\nMore text\n\n```yaml\nverdict: REQUEST_CHANGES\n```\n"`. Assert `parse_verdict(raw) == "APPROVE"`.
    - **Trailing prose after yaml.** Input: `"```yaml\nverdict: APPROVE\n```\n\nThanks, this looks great.\n"`. Assert `parse_verdict(raw) == "APPROVE"`.
    - **Yaml fence with trailing whitespace.** Input: `"```yaml   \nverdict: APPROVE\n```   \n"` (note three spaces after both fences). Assert `parse_verdict(raw) == "APPROVE"` (the existing `line.rstrip() == "\`\`\`yaml"` and `line.rstrip() == "\`\`\`"` comparisons already strip trailing whitespace; this case locks the behaviour in).
    - **Prose preamble + yaml block.** Input: `"Review written to ...md. Verdict is APPROVE.\n\n# Review: X\n\n```yaml\nverdict: APPROVE\n```\n"`. Assert `parse_verdict(raw) == "APPROVE"` (the existing line 398-401 case covers a similar shape; this case extends with explicit prose paragraph).
    - **Yaml block contains 'verdict:' with extra whitespace.** Input: `"```yaml\n  verdict:   APPROVE   \n```\n"`. Assert `parse_verdict(raw) == "APPROVE"` (existing `stripped.startswith("verdict:")` + `.strip()` handles this; this case locks it in).
  - Each case follows the existing pattern: build `raw`, call `parse_verdict(raw)`, assert the expected value, `print("PASS: parse_verdict <description>")` on success.
- **Commit:** `test(review-common): extend parse_verdict coverage for prose preamble and multi-yaml (#315)`

## Batch Tests

The batch is verified by running `python plugins/mill/unit_tests/run-all.py` from the worktree root. All new tests must pass; all existing tests must continue passing. The bulker change is mode-additive (extension-keyed dispatch); the only behavioural regression risk is a `.ipynb` file in the existing test corpus accidentally tripping a new code path -- the run-all script will catch that.
