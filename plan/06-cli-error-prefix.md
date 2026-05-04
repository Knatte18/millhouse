# Batch: cli-error-prefix

```yaml
task: 'review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure'
batch: cli-error-prefix
cards: 3
verify: uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"
depends-on: [content-helpers]
```

## Batch Scope

Adds an `ERROR:` uppercase prefix to every `ReviewError` surfaced by the three review CLI scripts, plus a one-line hint pointing at the new `Deletes:` mechanism when the message is from `resolve_ref_paths`. Closes #104. The hint references the `Deletes:` field that B01 documented in `plan-batch.md` — that's why this batch depends on `content-helpers`. New helper module `_review_cli.py` keeps the logic out of three CLI scripts and gets one focused unit test (`test-review-cli.py`).

## Cards

### Card 23: Add `_review_cli.print_error` helper

- **Reads:**
  - `plugins/mill/scripts/_review_common.py`
- **Modifies:** none
- **Creates:**
  - `plugins/mill/scripts/_review_cli.py`
- **Deletes:** none
- **Requirements:** Create a new module `plugins/mill/scripts/_review_cli.py`. Module docstring: `"""Shared CLI helpers for the review subsystem. Today exposes one helper: print_error(exc) — formats a ReviewError with an uppercase ERROR: prefix and an optional one-line hint when the message is from resolve_ref_paths. Used by millpy-review-discussion.py, millpy-review-plan.py, millpy-review-code.py."""`. Public API: `print_error(exc: ReviewError) -> None`. Implementation: import `sys` and `from _review_common import ReviewError`; write `f"ERROR: {exc}\n"` to `sys.stderr`; if `str(exc).startswith("[resolve_ref_paths]")`, additionally write `"Hint: check the plan card referencing this file; if the file is intentionally deleted, list it under Deletes: in that card.\n"` to `sys.stderr`. Use `print(..., file=sys.stderr)` rather than direct `sys.stderr.write` for trailing-newline consistency. No `if __name__ == "__main__":` block (per CLAUDE.md). No other public symbols.
- **Commit:** `feat(review-cli): add print_error helper for ERROR: prefix and hint`

### Card 24: Wire the three review CLI scripts to use `_review_cli.print_error`

- **Reads:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/_review_cli.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In each of the three CLI scripts, locate the `except ReviewError as exc:` block at the bottom of `main()`. Replace `print(str(exc), file=sys.stderr)` with `from _review_cli import print_error; print_error(exc)`. Keep `return 1` immediately after. The `from _review_cli import print_error` import lives inside the `except` block (or at the top of the file alongside the existing lazy imports) — match the file's existing style. Do not change anything else in the CLIs (argparse, run() invocation, exit codes, validator gate in millpy-review-plan.py). Specifically for `millpy-review-plan.py`: the validator-failure JSON envelope path (`return 1` after `print(json.dumps({"errors": ...}))`) is unchanged — that path doesn't catch `ReviewError`.
- **Commit:** `fix(review-cli): use ERROR: prefix and hint for ReviewError surfacing (#104)`

### Card 25: Tests for `_review_cli.print_error`

- **Reads:**
  - `plugins/mill/scripts/_review_cli.py`
  - `plugins/mill/scripts/_review_common.py`
- **Modifies:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-review-cli.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-review-cli.py` following the project's standard test-file shape (`HUB = Path(__file__)...; sys.path.insert(0, ...)`; module-level `from _review_cli import print_error`; `def main() -> int:` returning 0/1; `if __name__ == "__main__": sys.exit(main())`). Test cases — capture stderr via `contextlib.redirect_stderr` against an `io.StringIO`: (a) plain message — `print_error(ReviewError("plain message"))` → captured stderr starts with `"ERROR: plain message"` and contains a trailing newline; the hint substring is NOT present. (b) `[resolve_ref_paths]` prefix — `print_error(ReviewError("[resolve_ref_paths] referenced path not found: 'foo.py'"))` → captured stderr contains `"ERROR: [resolve_ref_paths] referenced path not found: 'foo.py'"` AND the substring `"Hint: check the plan card"` AND `"list it under Deletes:"`. (c) hint NOT triggered for messages that have `[resolve_ref_paths]` somewhere internal but not at the start (e.g. `"some prefix [resolve_ref_paths] inner"`) — only the prefix case adds the hint. CLI subprocess-level tests (running `millpy-review-*.py` against a tempfile fixture and asserting `ERROR:` on stderr) are deferred to integration tests; add a TODO comment in this test file referencing `integration_tests/`.
- **Commit:** `test(review-cli): cover print_error formatter and hint`

## Batch Tests

`uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"` — `test-review-cli.py` covers Cards 23–25. `run-all.py` discovers test files automatically; the new file is picked up without further configuration.
