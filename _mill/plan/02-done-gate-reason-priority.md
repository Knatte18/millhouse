# Batch: done-gate-reason-priority

```yaml
task: "millpy-implement.py / _done_gate.py: Windows baseline teardown, truncated failure reason, ignored --start-sha"
batch: done-gate-reason-priority
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-done-gate.py
depends-on: []
```

## Batch Scope

Fixes GitHub #1020: `_done_gate.run_preflight` and `_done_gate.run_gate` both truncate a failed gate's captured output to a blind last-2000-characters tail (`out[-2000:]`). For a `go test ./...`-style gate whose output is dominated by alphabetically-earlier passing-package `ok` lines, this pushes the actual failure (`--- FAIL:`/`FAIL` lines from an early-sorting package) out of the kept tail, leaving `reason` useless. `plugins/mill/scripts/_implementer_common.py`'s `_run_verify_gate` already solved this exact problem for verify-gate output: on truncation it builds an omitted-content marker naming how many characters were dropped, plus up to 20 extracted failure-marker lines recovered from the omitted portion (via `_extract_failure_signatures`), followed by the tail. This batch reuses that exact helper and shape in `_done_gate.py` instead of duplicating a second failure-marker detector. No external interface changes: `run_preflight`/`run_gate`'s return-dict shape (`{"result": ..., "reason": ...}`) and never-raise contract are unchanged — only how `reason` is derived from the captured output when it exceeds 2000 characters.

## Cards

### Card 3: Prioritize failure lines over blind tail-truncation in captured reason

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/_done_gate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. Add `from _implementer_common import _extract_failure_signatures` to `_done_gate.py`'s import block (after the existing `from pathlib import Path` line).
  2. Add a new module-level function `_build_truncated_reason(out: str) -> str` in `_done_gate.py`, placed after the imports and before `run_preflight`. It reproduces `_implementer_common._run_verify_gate`'s existing truncation-enrichment shape (mirroring its own inline logic, not calling into `_run_verify_gate` itself — `_run_verify_gate` runs a subprocess and does far more than build this one string): if `len(out) <= 2000`, return `out` unchanged. Otherwise: `tail = out[-2000:]`; `omitted = out[:-2000]`; `fail_lines = _extract_failure_signatures(omitted)[:20]`; `marker = f"[... {len(omitted)} earlier chars omitted"`; when `fail_lines` is non-empty, append `"; earlier failures:\n" + "\n".join(fail_lines)` to `marker`; append `" ...]\n"` to `marker` unconditionally; return `marker + tail`. Docstring: explains this mirrors `_implementer_common._run_verify_gate`'s existing enrichment (cite that function by name) so a failure-marker line pushed out of a blind tail-truncation by later passing-noise is still recoverable in `reason`, per GitHub #1020.
  3. In `run_preflight`, the current truncation block (`out = (result.stdout + result.stderr).strip(); reason = out[-2000:] if len(out) > 2000 else out`) — replace only the `reason = out[-2000:] if len(out) > 2000 else out` line with `reason = _build_truncated_reason(out)`. The `out = (result.stdout + result.stderr).strip()` line is unchanged.
  4. In `run_gate`, the current truncation block (identically shaped: `out = (result.stdout + result.stderr).strip(); reason = out[-2000:] if len(out) > 2000 else out`) — apply the identical replacement: `reason = _build_truncated_reason(out)`, leaving `out = (result.stdout + result.stderr).strip()` unchanged.
  5. Update `run_preflight`'s and `run_gate`'s docstrings — both currently state "a non-zero exit is reported as `blocked` with the captured output" and both `Returns:` sections currently read `{"result": "blocked", "reason": <captured output, tail-truncated to 2000 chars>}`. Change both `Returns:` descriptions to state that on truncation, `reason` is an omitted-content marker (naming the omitted character count, plus up to 20 extracted failure-marker lines recovered from the omitted portion when any exist) followed by the last 2000 characters — not a bare tail. Both functions' shared "so both call sites treat the same `gate_cmd` identically" docstring language (already present in both) is still accurate and needs no further change, since this card keeps both functions calling the identical `_build_truncated_reason` helper.
  6. Do not change `run_gate`'s Windows/dotnet build-server-shutdown success-path cleanup, either function's exception-handling (`except Exception as exc: return {"result": "blocked", "reason": str(exc)}`), or the `"skipped"` result case in `run_preflight` — none of that is affected by this fix.
- **Commit:** `fix(done-gate): prioritize failure lines over blind tail-truncation in captured reason (#1020)`

### Card 4: Cover failure-line-prioritized truncation for run_preflight and run_gate

- **Context:**
  - `plugins/mill/scripts/_done_gate.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-done-gate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. Update Case 4 ("mocked exit 1 with output longer than 2000 chars" for `run_preflight`, `long_output = "x" * 3000`, no failure markers anywhere in it). Since `_build_truncated_reason` now always prepends an omitted-content marker on any truncation (matching `_implementer_common._run_verify_gate`'s existing shape, even when no failure line is found), the current assertions `assert len(result["reason"]) == 2000` and `assert result["reason"] == long_output[-2000:]` no longer hold. Replace both with: `assert result["reason"].startswith("[... 1000 earlier chars omitted")`, `assert "; earlier failures:" not in result["reason"]` (no failure-marker lines exist anywhere in an all-`"x"` string, so the marker must omit the "earlier failures" suffix), and `assert result["reason"].endswith(long_output[-2000:])`. Update the case's inline comment (currently describing bare tail-truncation to exactly 2000 chars) to describe the new marker-plus-tail shape, and update the `print("PASS: ...")` message text to match.
  2. Apply the identical assertion and comment changes to Case 9 (`run_gate`'s mirror of Case 4, same `long_output = "x" * 3000` input, same current bare-tail assertions).
  3. Add a new Case 10, placed immediately after Case 9 and before the `if errors:` block at the end of `main()`: mocked exit 1 for `run_preflight` with output shaped so a Go per-test failure-marker line sits in the omitted (non-tail) portion — `long_output = "--- FAIL: TestEarly (0.01s)\n" + ("ok  \tpkg/passing\t0.01s\n" * 150)` (long enough in total that the leading `"--- FAIL: TestEarly (0.01s)"` line falls outside the kept last-2000-character tail; verify this with a length check in the test itself, e.g. `assert len(long_output) > 2000 + len("--- FAIL: TestEarly (0.01s)\n")` before asserting on the result, so the test is self-checking against its own fixture). Assert `result["result"] == "blocked"` and assert `"--- FAIL: TestEarly (0.01s)" in result["reason"]` — proving the earlier failure line survived truncation instead of being silently dropped by a blind tail-keep. This is the direct regression case for #1020. Print `"PASS: run_preflight surfaces an earlier failure-marker line pushed out of the tail by later passing noise"` on success.
  4. Add a new Case 11, identical scenario to Case 10 but invoking `run_gate` instead of `run_preflight` (same `long_output` construction, same assertions), confirming both call sites share the identical enriched-reason shape per their docstrings' "both call sites treat the same `gate_cmd` identically" promise. Use a `gate_cmd` string without `"dotnet"` in it (e.g. `"false"`, matching the existing Case 9's `gate_cmd`) so the Windows dotnet-build-server-shutdown branch does not interfere with this case. Print `"PASS: run_gate surfaces an earlier failure-marker line pushed out of the tail by later passing noise"` on success.
  5. Wrap Cases 10 and 11 in the file's existing `try:`/`except AssertionError as exc: print(f"FAIL: ...", file=sys.stderr); errors += 1` pattern, incrementing the same `errors` accumulator used by every other case.
  6. Do not modify Cases 1, 2, 3, 5, 6, 7, or 8 — none of them involve truncation (Case 3 is under the 2000-char threshold and stays a bare-output pass-through; Cases 6-8 are the dotnet-shutdown-branch cases and exit-0 cases, unaffected by this fix).
- **Commit:** `test(done-gate): cover failure-line-prioritized truncation for run_preflight and run_gate (#1020)`

## Batch Tests

`verify:` runs `test-done-gate.py` in full (already scoped to exactly the module this batch edits — every case in the file, both existing and this batch's new ones, mocks `subprocess.run`/`platform.system`, so no real shell command ever executes).
