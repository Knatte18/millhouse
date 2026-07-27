# Batch: finalize-output-missing-file-error

```yaml
task: 'Agent-dispatch boundary gaps: source-read guidance, fork directive-echo, and raw FileNotFoundError on missing agent-output'
batch: finalize-output-missing-file-error
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: []
```

## Batch Scope

This batch fixes GitHub issue #704: `_implementer_common.py`'s `finalize_from_output` crashes with a raw, unhandled `FileNotFoundError` traceback when the `--agent-output` path it is given does not exist on disk, instead of a clean, actionable error. `finalize_from_output` is a shared helper called from three CLIs (`millpy-fix.py`, `millpy-implement.py`, `millpy-merge-in-subagent.py`), so fixing it once fixes all three call sites — no call-site changes are needed. Card 1 (global card 3) makes the fix; Card 2 (global card 4) adds the regression test. The external interface Card 2 depends on is Card 1's new behavior: a non-zero return code and a stderr message naming the missing path — no other batch consumes this batch's output. Per `_mill/discussion.md`'s "finalize_from_output error handling" Decision, the fix uses a plain stderr print + return code, matching the implementer-family CLIs' existing plain-stderr-print convention (contrast: NOT `_review_cli.print_error_envelope`, which is review-CLI-specific — see the overview's "stderr + non-zero return code, not a JSON error envelope" Shared Decision).

## Cards

### Card 3: Clean error instead of raw FileNotFoundError in finalize_from_output

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_implementer_common.py`'s `finalize_from_output` function, immediately before the existing line `output = html.unescape(Path(agent_output_path).read_text(encoding="utf-8"))`, insert a guard: coerce `agent_output_path` to a `Path` (it already is typed `Path` in the signature, but the call sites pass it via `Path(args.agent_output)` — normalize with `agent_output_path = Path(agent_output_path)` for safety), then check `if not agent_output_path.exists():`. When the path does not exist, `print(f"ERROR: --agent-output file not found: {agent_output_path} -- for implementer/fixer/merge-in dispatches the orchestrator must write the notification message to this path before calling --stage finalize", file=sys.stderr)` and `return 1` immediately — do not proceed to the `html.unescape(...)`/`read_text(...)` call or to the `_forward_output(...)` delegation. `sys` is already imported at module scope (line 9) — no new import needed. Do not change the existing HTML-unescape comment or behavior for the file-exists path; the fix only adds the existence check ahead of the read.
- **Commit:** `fix(implementer-common): clean error instead of raw FileNotFoundError when --agent-output file is missing`

### Card 4: Regression test for finalize_from_output's missing-agent-output-file path

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new "Case 67" test to `plugins/mill/unit_tests/test-implementer-common.py`, appended immediately after the existing "Case 66g" block and before the trailing `if errors:` / `print("All _implementer_common unit tests passed.")` / `return 0` block that ends `main()`. Follow the file's existing conventions exactly: build a `project_root` via `tempfile.TemporaryDirectory()` and `_setup_fixture(project_root)` (same helper used by Case 13 and others); construct a path to a file that is never created, e.g. `agent_output_path = project_root / "_mill" / "missing-agent-output.txt"`; capture stderr using `io.StringIO()` + `contextlib.redirect_stderr(...)` (the same pattern as Case 66c); call `finalize_from_output(agent_output_path, project_root, session_id="test-session-67")` inside a `try`/`except Exception as exc` block matching the file's existing `print(f"FAIL: case 67 ({exc})", file=sys.stderr); errors += 1` error-handling style. Inside the `try`, assert: (a) the returned value equals `1` (`assert rc == 1, f"case 67: expected rc=1, got {rc}"`); (b) the captured stderr text contains the literal string `str(agent_output_path)` (confirming the missing path is named); (c) the captured stderr text contains the case-insensitive substring `"agent-output"` (confirming the actionable message fired, not a generic error). On success, `print("PASS: case 67 - finalize_from_output reports a clean error for a missing --agent-output file")`. The test must NOT expect or catch a `FileNotFoundError` — the whole point of the assertion is that `finalize_from_output` no longer raises one; if the fix (Card 3) is missing or incomplete, this test's `try` block will itself raise `FileNotFoundError`, which the surrounding `except Exception` catches and reports as `FAIL: case 67`, correctly failing the test.
- **Commit:** `test(implementer-common): cover finalize_from_output's missing-agent-output-file error path`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py` — runs the single test file both cards touch (Card 3's fix is exercised directly by Card 4's new Case 67, and the full file's existing ~66 cases act as a regression guard that the new existence-check guard in `finalize_from_output` does not change behavior for any pre-existing file-exists code path, e.g. Case 13 and Case 63).
