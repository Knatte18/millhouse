# Batch: review-warning-ascii

```yaml
task: "Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize"
batch: "review-warning-ascii"
number: 1
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py
depends-on: []
```

## Batch Scope

Fixes GitHub issue #475: the parse-divergence warning in `_review_common.py`
prints a U+2014 em dash to stderr, which mojibakes on Windows cp1252 consoles.
Replace the em dash with the ASCII ` -- ` separator and scan the file's other
runtime-output paths for the same hazard. Add a regression test asserting the
warning is ASCII-only. Self-contained; no external interface for later batches.

## Cards

### Card 1: ASCII-safe parse-divergence warning + regression test

- **Context:**
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_review_common.py`, in `_warn_if_prose_diverges`, change
  the `print(..., file=sys.stderr)` warning string so the U+2014 em dash (`—`)
  before "check review file for missing heading" becomes the ASCII ` -- `
  separator. Audit every other runtime `print(...)`/`_log(...)` call in
  `_review_common.py` (not docstrings or comments) and convert any non-ASCII
  glyph (em dash, arrows) to its ASCII form per the `ascii-console-output`
  shared decision. In `test-review-common.py`, add a test that invokes
  `_warn_if_prose_diverges` (or its public caller) with diverging heading vs
  prose counts, captures stderr, and asserts every character satisfies
  `ord(c) < 128`. Follow the existing test harness style in the file (pass/fail
  counters, `if __name__ == "__main__": sys.exit(main())`).
- **Commit:** `fix(review): ASCII-safe parse_blocking_count divergence warning (#475)`

## Batch Tests

`verify:` runs `test-review-common.py` only (the file that gains the ASCII
regression test and already exercises `_review_common` parsing). Scope is a
single file because the change is local to `_review_common.py`.
