# Batch: implementer-signal-fixes

```yaml
task: "Fix pre-existing unit-test failures, CRLF cleanliness false-positive, and review false-BLOCKING on Go"
batch: implementer-signal-fixes
number: 2
cards: 5
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py test-implementer-common.py"
depends-on: []
```

## Batch Scope

Two production false-positives in the implementer's cleanliness/verify signal path: (1) the CRLF cleanliness false-positive — the cleanliness snapshot is written in text mode (CRLF-translated on Windows) and `_is_formatter_drift_only` diffs with CR-blind `git diff -w`, so a pure CRLF-vs-LF delta is misreported as real dirt; and (2) the Go review false-BLOCKING — `_is_benign_windows_cleanup` uses a bare `"fail"` substring marker that matches benign Go test output, so a benign Windows cleanup-race exit is treated as a real failure (`stuck/verify` -> BLOCKING). Cards 4-6 are production fixes; cards 7-8 add regression tests. This is one batch because all four files are in the implementer-signal surface and cards 5 & 6 edit the same file (`_implementer_common.py`) sequentially. No file overlaps any other batch. Batch-local decisions: Go failure markers are matched **line-anchored**, never as the bare substring `fail`; snapshot writes use `newline=""`.

## Cards

### Card 4: Make the cleanliness snapshot CRLF-safe

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_cleanliness.capture_snapshot`, the snapshot is written via `snapshot_path.write_text(..., encoding="utf-8")` with no `newline` argument, so on Windows text-mode translation rewrites `\n` to `\r\n`. Add `newline=""` to that `write_text` call so the on-disk snapshot keeps LF terminators and does not itself surface as a ` M` git-status entry. In `_cleanliness.compute_new_dirt`, the live/after porcelain set-comparison (`post_set - pre_set`) must be CR-insensitive: strip a trailing `\r` from each line before building `pre_set` and `post_set` (the read path already uses `read_text` + `splitlines`, but ensure no `\r` survives into the set elements). Do not change the function signatures or the return ordering (`sorted(...)`).
- **Commit:** `fix(cleanliness): write snapshot with LF and CR-normalize dirt comparison`

### Card 5: Make formatter-drift detection ignore CR-only diffs

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_implementer_common._is_formatter_drift_only`, the two diff probes run `git diff` and `git diff -w`. `git diff -w` (`--ignore-all-space`) does not ignore carriage-return-at-EOL differences, so a pure CRLF-vs-LF change still shows under `-w` and is misclassified as real content. Add `--ignore-cr-at-eol` to BOTH `git -C <root> diff` invocations (the plain `diff` used to detect any tracked change AND the `diff -w` used to detect non-whitespace content) so a CRLF-only delta is treated as whitespace/formatter drift. Keep the existing untracked-file check and the early-return structure (returns False on any non-zero git exit). Do not touch `_is_benign_windows_cleanup` in this card.
- **Commit:** `fix(implementer): ignore CR-at-eol in formatter-drift detection`

### Card 6: Tighten the Windows benign-cleanup Go failure markers

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_implementer_common._is_benign_windows_cleanup`, the `failure_markers` list is `["fail", "panic:", "build failed"]`; the bare `"fail"` substring over-matches benign Go test output (e.g. an `ok` line for a package whose path contains `failover`), so a benign Windows cleanup-race exit is wrongly classified as a real failure. Replace the bare-substring match against `output_lower` with **line-anchored** matching, keeping case-insensitivity (match against the lowercased output) but using these tokens: `--- fail` (go-test per-test prefix, substring match is safe), the regex `(?m)^fail[\t ]` for the package-summary line `FAIL\tpkg` (a real TAB or space after `fail` at line start — NOT the literal characters backslash-t), `panic:`, and `build failed`. Remove the bare `"fail"` marker. `has_failure_marker` is True if any of these match. Use Python's `re` module for the `^fail[\t ]` line-anchored check (multiline). Update the function docstring's enumerated marker list to match. Benign output such as `ok  \tpkg/failover\t0.1s` must NOT match (its line starts with `ok`, not `fail`, and has no `--- ` prefix); real `--- FAIL:` and `FAIL\tpkg` lines MUST still match. Keep `_has_windows_cleanup_race_signature` and the `return has_cleanup_signature and not has_failure_marker` shape unchanged.
- **Commit:** `fix(verify): line-anchor Go failure markers in benign-cleanup gate`

### Card 7: Add CRLF cleanliness regression test

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a regression test that exercises the live-status CR-only path (not just the snapshot read that test #8 already covers). The test must fail before card 4/5 and pass after. Cover: (a) `capture_snapshot` writes a file whose bytes contain no `\r\n` (assert LF-only on disk); and (b) a CR-only delta between snapshot and live porcelain yields an empty `compute_new_dirt` result. Use the file's existing tempdir/fixture style and register the new test in the file's aggregator (`main()` / runner) consistent with the surrounding tests. Do not weaken existing test #8.
- **Commit:** `test(cleanliness): cover CRLF-only delta in snapshot and dirt compare`

### Card 8: Add benign-Go-output regression case

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a test case asserting `_is_benign_windows_cleanup` returns True (benign) for output that has a Windows cleanup-race signature (e.g. `unlinkat` / `access is denied`) AND go-test output whose only `fail` substring is inside an `ok` line (e.g. `ok  \tpkg/failover\t0.1s` with a real TAB) and which contains no `--- FAIL:` line and no package-summary line starting with `FAIL` + tab/space. Also assert the gate still returns False (real failure) for output combining the cleanup signature with a real `--- FAIL:` line and with a real `FAIL\tpkg` summary line. Keep the existing cases 24/24b/25/26 passing. Follow the existing case-numbering and assertion style in the file and register in its runner.
- **Commit:** `test(verify): cover benign Go output and real FAIL lines in cleanup gate`

## Batch Tests

`verify:` runs `test-cleanliness.py` (card 7 CRLF regression + existing snapshot tests) and `test-implementer-common.py` (card 8 Go-marker regression + existing verify-gate cases 24/24b/25/26 and the no-content/completeness/dirty-tree gates). Both scoped via `run-all.py --only`. `test-implementer-common.py` is the largest file in the suite but is the correct and only home for the `_is_benign_windows_cleanup` / `_is_formatter_drift_only` coverage; scope stays to the two affected files.
