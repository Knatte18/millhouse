# Batch: verify-gate-enrichment

```yaml
task: mill-plan/review validation false-positives, hard-fails, and truncated failure reasons
batch: verify-gate-enrichment
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py
depends-on: []
```

## Batch Scope

This batch fixes #731: `_implementer_common.py`'s `_run_verify_gate` truncates verify-command output to its last 2000 characters when reporting a `stuck_type: verify` failure reason, which can silently drop an earlier failing package/test's identity when a later, less-informative failure lands in the kept tail. The fix enriches the truncated `reason` with an omitted-content marker plus up to 20 extracted failure-summary lines (Go subtest/package, pytest, and this repo's own `run-all.py` per-test/summary markers) recovered from the omitted portion. This batch is independent of batches 1 and 2 — no shared `Edits:` targets.

## Cards

### Card 11: Enrich the truncated verify-failure reason

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_run_verify_gate`, replace the current unconditional truncation block:
  ```python
  output_stripped = output.strip()
  reason = (
      output_stripped[-2000:]
      if len(output_stripped) > 2000
      else output_stripped
  )
  ```
  with:
  ```python
  output_stripped = output.strip()
  if len(output_stripped) > 2000:
      tail = output_stripped[-2000:]
      omitted = output_stripped[:-2000]
      fail_lines = [
          line for line in omitted.splitlines()
          if line.startswith((
              "--- FAIL:", "FAIL\t", "FAILED ", "--- FAIL ", "FAIL -- ",
          ))
      ][:20]
      marker = f"[... {len(omitted)} earlier chars omitted"
      if fail_lines:
          marker += "; earlier failures:\n" + "\n".join(fail_lines)
      marker += " ...]\n"
      reason = marker + tail
  else:
      reason = output_stripped
  ```
  The five prefixes match: Go subtest failures (`--- FAIL: <name>`), Go package-level failures (`FAIL\t<package>`), pytest failures (`FAILED <test>`), this repo's own `plugins/mill/unit_tests/run-all.py` per-test failure line (`--- FAIL <name> (<elapsed>s) ---`, printed by `run-all.py`'s own `_run_one`/summary code), and `run-all.py`'s own summary line (`FAIL -- <n> of <m> in <elapsed>s: [...]`). The extracted-line cap is 20 (bounds pathological blowup — do not make this configurable). When `len(output_stripped) <= 2000`, `reason` is `output_stripped` unchanged — no marker, matching current behavior exactly (regression guard).
  The marker string is ASCII-only (`...` literal three dots, no em-dash, no non-ASCII arrow) per CLAUDE.md's `print()`/`_log()` ASCII-only convention — this string ends up in a stuck-dict `reason` that may be surfaced through `print()`/`_log()` elsewhere in the pipeline.
  The function's return-dict shape (`{"status": "stuck", "stuck_type": "verify", "reason": <str>}`) is unchanged — only the `reason` string's content changes when truncation occurs. No caller of `_run_verify_gate`/`_run_verify_gates` needs to change.
- **Commit:** `fix(implementer-common): enrich truncated verify-failure reason with earlier-failure summary (#731)`

### Card 12: Tests for the enriched verify-failure reason

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add five new inline scenario blocks to this file's `main()`, placed near the existing `_run_verify_gate` coverage (see the blocks around "Test A: git_root kwarg selects cwd for the verify subprocess"), following the same `unittest.mock.patch("_implementer_common.subprocess.run")` + `MagicMock(returncode=..., stdout=..., stderr=...)` + `_run_verify_gate(project_root, "echo ok", ...)` + `assert`/`errors += 1` pattern already used there — construct `mock_result.stdout`/`mock_result.stderr` strings directly (no real subprocess execution needed; `_run_verify_gate` only reads `result.returncode`/`result.stdout`/`result.stderr` from the mock).
  Scenarios:
  (a) Combined `stdout`+`stderr` under 2000 chars total, `returncode=1` → returned `reason` equals the exact stripped combined output, no `"[..."` marker present (regression guard for the unchanged short-output path).
  (b) Combined output over 2000 chars: construct a string with an early line `FAIL\tinternal/reedengine\t0.02s` positioned outside the kept last-2000-char tail, and additional filler text before/after so a distinct failure signature is present at the very end (inside the tail) — assert `reason` contains the `"[... N earlier chars omitted; earlier failures:"` marker, the extracted `FAIL\tinternal/reedengine\t0.02s` line, AND the literal tail content.
  (c) Combined output over 2000 chars with no line anywhere in the omitted portion matching any of the five recognized prefixes → `reason` contains the `"[... N earlier chars omitted ...]"` marker (byte-count-only, no `"; earlier failures:"` clause) followed by the tail.
  (d) Combined output over 2000 chars with more than 20 matching failure-marker lines in the omitted portion (e.g. 25 `FAIL\tpkg<i>` lines) → the extracted list in `reason` contains exactly 20 lines, not 25 (cap enforced).
  (e) Combined output over 2000 chars shaped like a `run-all.py` failure: an early `--- FAIL some_test (1.2s) ---` line (outside the tail) plus a `FAIL -- 3 of 10 in 45.6s: [...]` summary line (also outside the tail) → both lines appear in the extracted `reason` (confirms the two `run-all.py`-specific prefixes added by Card 11 work, not just the Go/pytest three).
  Print `PASS`/`FAIL` per this file's existing convention and increment the shared `errors` counter on failure.
- **Commit:** `test(implementer-common): cover enriched verify-failure reason scenarios (#731)`

## Batch Tests

`verify:` runs `run-all.py --only test-implementer-common.py`, covering both the short-output regression guard and all five enrichment scenarios from Card 12 in the same file already covering `_run_verify_gate`'s other behavior.
