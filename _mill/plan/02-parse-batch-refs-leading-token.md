# Batch: parse-batch-refs-leading-token

```yaml
task: Fix plan validator Moves-target gap, code-review backtick parser, and mill-start encoding crash
batch: parse-batch-refs-leading-token
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-plan-validate.py
depends-on: []
```

## Batch Scope

`_review_common.parse_batch_refs`'s multi-line sub-bullet extraction currently `extend`s every backtick-wrapped span found on a sub-bullet line into the token list, not just the leading path. A scope sub-bullet that pairs a real path with a parenthetical containing further backtick-quoted prose (e.g. `` `cmd/lyx/main_test.go` (batch 3 routed `boardcli`'s dir through `paths.Resolve` ...) ``) therefore yields phantom ref tokens, which `resolve_ref_paths` hard-fails on, producing a top-level `verdict: ERROR` that blocks an entire holistic code review. This batch restricts the sub-bullet extraction to the leading token only (Card 4), pins that behavior with a regression test (Card 5), and adds a companion test proving the same repro shape is independently caught by the existing plan-validate Check 6 at `--stage prepare` time — documenting the two checks as intentionally layered, not redundant (Card 6). The single-line inline form (multiple comma/backtick-separated tokens on one line) is untouched; it is a separately-tested, legitimate convention outside this bug's scope.

## Cards

### Card 4: Restrict parse_batch_refs sub-bullet extraction to the leading backtick token

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `parse_batch_refs`, inside the multi-line sub-bullet `while j < len(lines):` loop (the `else:` branch taken when the field header's inline value is empty), the current body is:
  ```
  rest = sm.group(1).strip()
  bt = re.findall(r"`([^`]+)`", rest)
  if bt:
      tokens.extend(bt)
  j += 1
  ```
  Change `tokens.extend(bt)` to `tokens.append(bt[0])` so only the leading backtick-wrapped span on the sub-bullet line is kept; any further backtick spans on the same line (prose parentheticals) are discarded. Do not change the regex, the `rest = sm.group(1).strip()` line, the `if bt:` guard, the `j += 1` increment, or any other branch of `parse_batch_refs` (the single-line inline-form branch a few lines above, which legitimately keeps every backtick token via `tokens` built from `backtick_tokens`, must remain untouched).
- **Commit:** `fix(review-common): parse_batch_refs keeps only leading backtick token per sub-bullet`

### Card 5: Add regression test pinning the leading-token-only behavior

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new test block to `main()` immediately after the existing block whose body asserts `refs == ["path/a", "path/b"]` and prints `"PASS: parse_batch_refs multi-line bullet form returns both paths"`. Follow the same style as that block (a `with _test_helpers.safe_temp_dir() as tmpdir:` block writing a `batch.md` file via `batch.write_text(...)`, calling `parse_batch_refs(batch)`, asserting the result, then `print("PASS: ...")`). The new block must reproduce the #580 bug shape exactly: a `- **Context:**` multi-line header followed by one sub-bullet line that pairs a leading real-looking path token with a parenthetical containing additional backtick-wrapped non-path text on the same line, e.g.:
  ```
  "### Card 1\n\n"
  "- **Context:**\n"
  "  - `cmd/lyx/main_test.go` (batch 3 routed `boardcli`'s dir through `paths.Resolve`)\n"
  "- **Creates:** none\n"
  ```
  Assert `refs == ["cmd/lyx/main_test.go"]` — i.e. the phantom tokens `boardcli` and `paths.Resolve` must NOT appear in the result. Print a `PASS:` line describing the phantom-token suppression (e.g. `"PASS: parse_batch_refs sub-bullet keeps only leading token, drops prose backticks"`).
- **Commit:** `test(review-common): pin parse_batch_refs leading-token-only sub-bullet behavior`

### Card 6: Add layered-defense test proving Check 6 independently catches the same repro shape

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new test function `test_check_reads_not_backtick_path_dirty_multiline_multi_backtick` modeled directly on the existing `test_check_reads_not_backtick_path_dirty` function (same fixture pattern: `tempfile.TemporaryDirectory()`, `_make_overview([{"name": "alpha", "file": "01-alpha.md"}])`, a hand-written `batch_text` string, `_write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])`, then `_plan_validate.run(plan_dir, project_root)` and filtering `check6 = [e for e in result if e["check"] == "reads-not-backtick-path"]`). Unlike the existing dirty test (which uses the single-line inline form `` - **Context:** `src/foo.py` (used by foo) ``), this new test's `batch_text` must use the **multi-line sub-bullet form** with a sub-bullet line carrying two backtick-wrapped spans — the exact shape that reaches `parse_batch_refs` unfiltered before Card 4/5's fix and that Check 6 is supposed to catch independently at plan-validate time:
  ```
  "- **Context:**\n"
  "  - `cmd/lyx/main_test.go` (batch 3 routed `boardcli`'s dir through `paths.Resolve`)\n"
  "- **Edits:** none\n"
  "- **Creates:** none\n"
  "- **Deletes:** none\n"
  "- **Moves:** none\n"
  ```
  (Create `cmd/lyx/main_test.go` under `project_root` first, same as the existing dirty test does for `src/foo.py`, so check 1 (`non-existent-path`) does not also fire and confound the `check6` assertion.) Assert `len(check6) >= 1` (do not assert an exact count or pin which of Check 6's two guards — `len(bt_matches) > 1` at line 1073, or the separate "prose alongside backtick path" guard at lines 1095-1107 — produced the finding; either is acceptable proof that Check 6 independently flags this shape). Print `"PASS: test_check_reads_not_backtick_path_dirty_multiline_multi_backtick"` on success, matching the existing functions' print/return-code convention (`return 0` on pass, `print(f"FAIL ...", file=sys.stderr); return 1` on `AssertionError`). Register the new function in the `tests = [...]` list inside `main()`, immediately after the existing `test_check_reads_not_backtick_path_dirty,` entry.
- **Commit:** `test(plan-validate): pin Check 6 catches multi-backtick sub-bullet (layered defense with parse_batch_refs)`

## Batch Tests

`verify:` runs `test-review-common.py` (covers Cards 4 and 5 — the `parse_batch_refs` fix and its new regression test, plus the existing sub-bullet/inline/Moves-exclusion tests that must keep passing unchanged) and `test-plan-validate.py` (covers Card 6's new Check 6 test, plus the existing `reads-not-backtick-path` and `all-files-touched-mismatch` tests, which must be unaffected since this batch does not touch `_plan_validate.py`'s check logic).
