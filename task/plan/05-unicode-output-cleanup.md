# Batch: unicode-output-cleanup

```yaml
task: 33 (A) -- Working-dir rename + portals redesign + junction cleanup
batch: unicode-output-cleanup
number: 5
cards: 3
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [4]
```

## Batch Scope

Replaces all non-ASCII characters in `print()` and `_log()` output strings with ASCII equivalents, so the scripts run without encoding errors on Windows cp1252 terminals. Rule: em-dash U+2014 (`—`) becomes ` -- `; right-arrow U+2192 (`->`) becomes ` -> `. Docstrings and comments are exempt. Four files are affected.

## Cards

### Card 28: Fix unicode in `millpy-migrate-layout.py` output strings

- **Context:**
  - `plugins/mill/scripts/millpy-migrate-layout.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-migrate-layout.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-migrate-layout.py`, find every `_log(...)` and `print(...)` call whose string argument contains `→` (U+2192) or `—` (U+2014). Replace:
  - `→` (or the escape `→`) with ` -> ` in those strings.
  - `—` (or `—`) with ` -- ` in those strings.
  Affected lines include (but confirm by reading the file): lines 119, 121 (`→` in `_log` move messages), line 210 (`—` in DRY-RUN `_log`), line 411 (`—` in DRY-RUN `print`), lines 475, 487 (`→` in move `_log`), lines 527, 545 (`→` in portal creation `_log`). Docstrings and inline comments in the file are exempt.
- **Commit:** `fix(migrate-layout): replace unicode arrows and em-dashes in output strings`

### Card 29: Fix unicode in `_inplace.py` and `millpy-terminal.py` output strings

- **Context:**
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/scripts/millpy-terminal.py`
- **Edits:**
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/scripts/millpy-terminal.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `_inplace.py` (around lines 82-83): find the two `print(..., file=sys.stderr)` calls that contain `—` in their string arguments (the "Treat as in-place" and "Treat as worktree" option labels). Replace each `—` with ` -- `.
  In `millpy-terminal.py` (around lines 82 and 88): find the `print(...)` call on line 82 that contains `—` in an f-string (`Auto-selecting: {slug} — {title}`), and any similar label string on line 88 (`f"{slug} — {title}"`). Replace `—` with ` -- ` in these strings. The line 88 string may be used as a display label in a picker — replace `—` with ` -- ` regardless of whether it passes through `print` directly.
- **Commit:** `fix(inplace,terminal): replace em-dashes in output strings`

### Card 30: Fix unicode in `millpy-cleanup.py` output strings

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-cleanup.py`, find every `print(...)`, `to_report.append(...)`, and similar output-bearing call whose string argument contains `—` (U+2014) or `→` (U+2192, or `→`). Replace:
  - `→` / `→` with ` -> `.
  - `—` / `—` with ` -- `.
  Affected lines include (confirm by reading the file before editing): lines 125, 144, 151, 160, 168 (`—` in `to_report.append` strings), line 217 (`→` in `_print_plan` abandoned line), line 442 (`—` in PR-reap OPEN print), line 448 (`—` in PR-reap CLOSED print), line 533 (`—` in skipping print). The module-level docstring on line 2 and any inline comments are exempt.
- **Commit:** `fix(cleanup): replace unicode arrows and em-dashes in output strings`

## Batch Tests

Run `python plugins/mill/unit_tests/run-all.py`. All tests from batches 01-04 must pass. The unicode replacements are output-string-only changes and do not affect test logic; tests should be unaffected.
