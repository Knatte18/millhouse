# Batch: review-cli-error-envelope

```yaml
task: 60 (A) — Branch/slug/claim fixes
batch: review-cli-error-envelope
number: 2
cards: 3
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Introduce a new `print_error_envelope(review_type: str, msg: str) -> None` helper in `_review_cli.py` that emits an ERROR-shaped JSON envelope on stdout and the human-readable error on stderr (D2). Wire the helper into all three review CLIs (`millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py`) at every startup-failure path — both the existing `try/except` handlers and the currently-unprotected `resolve_wiki_path` / `load_config` top-level calls. Extend `test-review-cli.py` with envelope-shape tests and per-CLI startup-failure assertions.

The batch's `verify:` runs the unit-test suite. No external interface other than the JSON envelope shape, which downstream consumers (batch 5's `mill-start` and `mill-go` SKILL changes) depend on.

## Cards

### Card 4: Add `print_error_envelope` helper to `_review_cli.py` (D2 part 1)

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_review_cli.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new function `print_error_envelope(review_type: str, msg: str) -> None` to `_review_cli.py`. The function: (a) prints `f"ERROR: {msg}"` to `sys.stderr` (same shape as the existing `print_error`); (b) builds the dict `{"type": review_type, "round": 0, "verdict": "ERROR", "blocking_count": 0, "reviews": [{"scope": "holistic", "verdict": "ERROR", "error": msg}]}` and prints `json.dumps(envelope)` on a single line to `sys.stdout`. Order: stderr first, then stdout (so log files keep the human message ahead of the machine line). Import `json` at module top. Do not modify the existing `print_error` function — it stays for callers that emit only stderr. Update the module docstring (line 1-4) to mention the new helper alongside `print_error`.
- **Commit:** `feat(review-cli): add print_error_envelope helper (#298)`

### Card 5: Wire `print_error_envelope` into all three review CLIs (D2 part 2)

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In each of the three review CLI scripts, wire startup-failure paths to `print_error_envelope`. The `review_type` literal is `"discussion"` / `"plan"` / `"code"` matching the script. Two kinds of call site:

  **(a) Existing try/except handlers — replace, do not add.** In `millpy-review-discussion.py` lines 47-50 (`_reviewers.ReviewerError`) and lines 57-59 (`ReviewError`): keep the `try`/`except`, but replace each handler body's `print(str(exc), file=sys.stderr); return 1` (or `print_error(exc); return 1`) with `print_error_envelope("discussion", str(exc)); return 1`. Same shape for `millpy-review-plan.py` lines 84-86, 95-99 (validator-failure JSON branch — keep that branch emitting validator errors as today; do NOT route through envelope) and lines 112-114; and `millpy-review-code.py` lines 74-76, 84-85 (extra-file not found — also route through envelope), and 102-104. The plan-CLI's validator-failure branch (the path that prints `{"errors": [...], "summary": ...}`) keeps its existing shape — that envelope is intentionally validator-specific and mill-plan step 1.5 already parses it; do NOT replace it with `print_error_envelope`. The `--extra-file not found` path in code-CLI (lines 84-85) does get routed through envelope.

  **(b) Currently un-protected calls — wrap in NEW try/except.** Wrap the three top-level startup calls in each CLI with a NEW `try/except (ReviewError, ValueError, SystemExit)` block: `resolve_wiki_path(project_root)`, `load_config(project_root, mill_dir)`, and (since `Path.cwd()` itself does not raise but `resolve_git_root` inside `resolve_wiki_path` raises) the import-time aliases. Concretely, restructure each CLI's `main()` so the lines:

  ```python
  project_root = Path.cwd()
  mill_dir = project_root / ".millhouse"
  wiki_root = resolve_wiki_path(project_root)
  cfg = load_config(project_root, mill_dir)
  ```

  are wrapped in a single try block; the except catches `ReviewError`, `ValueError`, `SystemExit` and calls `print_error_envelope("<discussion|plan|code>", str(exc)); return 1`. The existing `try` blocks below (for reviewers/slug) stay separate. Do NOT widen the existing `try` blocks to swallow the new exceptions — that would conflate handler scopes.

  ASCII-only message strings. `import` lines stay grouped at the top of each CLI's `main()` body as today. **Drop the `print_error` import.** After replacing every handler body with `print_error_envelope`, the `from _review_cli import print_error` line in each of the three CLIs is no longer referenced. Remove `print_error` from each CLI's `from _review_cli import ...` line (it currently appears in `millpy-review-discussion.py`, `millpy-review-plan.py`, and `millpy-review-code.py`). `print_error` itself stays defined in `_review_cli.py` — only the imports drop.
- **Commit:** `fix(review-cli): emit ERROR envelope on startup failure (#298)`

### Card 6: Extend `test-review-cli.py` with envelope-shape and startup-failure tests (D9 part for D2)

- **Context:**
  - `plugins/mill/scripts/_review_cli.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-cli.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Extend the existing `test-review-cli.py` (do not create a new file; the file already imports `print_error` and `ReviewError` and has a `main()` runner). Add four new test functions:

  1. `test_print_error_envelope_shape()` — call `print_error_envelope("plan", "some error message")` with stdout captured via `contextlib.redirect_stdout(io.StringIO())` and stderr captured via `contextlib.redirect_stderr(io.StringIO())`. Assert: stderr contains `ERROR: some error message`; stdout contains exactly one line; `json.loads(stdout_line)` returns a dict with `type == "plan"`, `round == 0`, `verdict == "ERROR"`, `blocking_count == 0`, `reviews[0]["scope"] == "holistic"`, `reviews[0]["verdict"] == "ERROR"`, `reviews[0]["error"] == "some error message"`. Repeat the shape assertion with `review_type` set to `"discussion"` and `"code"` to confirm the type field flows through.

  2. `test_review_cli_emits_envelope_on_config_failure()` — for each of the three CLIs (`millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py`), drive the CLI's `main([])` (in-process import) with a `Path.cwd()` that does not resolve to a valid wiki sibling (use `unittest.mock.patch` to make `resolve_wiki_path` raise `ValueError("no sibling wiki")`). Capture stdout, assert exit code 1, parse stdout as JSON, assert `verdict == "ERROR"` and the error message contains `"no sibling wiki"`. Use the per-script `type` value to assert the `type` field.

  3. `test_review_cli_emits_envelope_on_reviewer_load_failure()` — similar shape, but patch `_reviewers.load` to raise `_reviewers.ReviewerError("registry missing")`. Assert stdout JSON envelope shape with the matching error.

  4. `test_review_cli_emits_envelope_on_slug_failure()` — patch `find_active_slug` to raise `ReviewError("branch not present in Home.md")`. Assert stdout JSON envelope shape.

  Call all four new test functions from `main()` at the bottom of `test-review-cli.py` (note: `test-review-cli.py` uses a monolithic inline `main()` — add direct calls, not list entries). Use `subprocess.run([sys.executable, "<script-path>"], ...)` if in-process patching is impractical (the existing fixtures pattern from `test-millpy-claim.py` may be reused — its `_load_claim_module` shows how to stub modules before import). For the validator-failure path (plan-CLI line 95-99) — explicitly add a comment in the test asserting that path is NOT covered here (it has its own `{"errors": ...}` envelope, not the `print_error_envelope` shape). One narrow test guarding that the validator path still emits `{"errors": [...]}` and not the error envelope is welcome but optional.

  All test strings ASCII-only.
- **Commit:** `test(review-cli): cover print_error_envelope + per-CLI startup failures`

## Batch Tests

`python plugins/mill/unit_tests/run-all.py` exercises `test-review-cli.py`. The new tests must pass without requiring real claude calls or real LLM access — all reviewer/LLM machinery is shortcut by the early `print_error_envelope` exit. Network and CI-friendly: no `_review_common.load_config` real-filesystem dependency in the new tests beyond standard tempfile patterns.
