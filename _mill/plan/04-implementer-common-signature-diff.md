# Batch: implementer-common-signature-diff

```yaml
task: Improve diagnosability of plan-validate errors and finalize verify-replay failures
batch: implementer-common-signature-diff
number: 4
cards: 7
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py
depends-on: []
```

## Batch Scope

Builds the shared failure-signature extraction/normalization primitives and the subset-diff waiver logic that both the per-batch baseline computation (batch 5) and finalize's verify-replay gate rely on. All work in this batch lives inside `_implementer_common.py` and its test file — `_run_verify_gate`'s existing FAIL-marker-prefix scan (today used only for the >2000-char truncation excerpt) becomes a shared, uncapped helper; a new normalization helper strips volatile per-run duration substrings so a genuinely pre-existing failure string-matches across runs; `_run_verify_gates` gains the actual subset-diff waiver decision; and the new `batch_verify_baseline` parameter is threaded through `finalize_from_output`/`_forward_output` to all four of `_forward_output`'s internal `_run_verify_gates` call sites. This batch is independent of every other batch — it does not read or write `status.md`'s new field itself; it only accepts whatever baseline value its caller (batch 6) eventually passes in.

## Cards

### Card 7: Extract `_extract_failure_signatures` helper

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_run_verify_gate` (`_implementer_common.py:690`), extract the existing inline FAIL-marker-prefix scan (`_implementer_common.py:792-797`: `fail_lines = [line for line in omitted.splitlines() if line.startswith((...))][:20]`, matching the fixed prefix tuple `"--- FAIL:", "FAIL\t", "FAILED ", "--- FAIL ", "FAIL -- "`) into a new module-level function `_extract_failure_signatures(output: str) -> list[str]` that scans EVERY line of the given `output` via `output.splitlines()` against the same fixed prefix tuple and returns ALL matching lines, UNCAPPED (no `[:20]` slice inside the helper itself — see `_mill/discussion.md`'s `gap2-failure-signature-extraction` Decision). At the truncation call site (`_implementer_common.py:792-797`), replace the inline list comprehension with `fail_lines = _extract_failure_signatures(omitted)[:20]` — the `[:20]` slice moves to this call site, preserving today's truncation-excerpt display behavior byte-for-byte.
- **Commit:** `refactor(implementer-common): extract _extract_failure_signatures helper`

### Card 8: Add `_normalize_failure_signature` helper

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new module-level function `_normalize_failure_signature(line: str) -> str` near `_extract_failure_signatures`, applying three regex substitutions in sequence (each matching anywhere in the line, not anchored to line-end — see `_mill/discussion.md`'s `gap2-signature-normalization-strips-duration` Decision): (1) `re.sub(r"\(\d+(\.\d+)?m?s\)", "", line)` — strips a parenthetical duration, covering both Go's `--- FAIL: TestFoo (0.00s)` and mill's own `run-all.py` per-test shape `--- FAIL some_test (1.2s) ---` (identical parenthetical shape, position-independent); (2) `re.sub(r"\t\d+(\.\d+)?s\b", "", line)` — strips a trailing tab-separated duration field, covering Go's package-summary shape `FAIL\tgithub.com/pkg\t0.123s`; (3) `re.sub(r"\s+in\s+\d+(\.\d+)?s", "", line)` — strips an ` in <duration>s` token, covering mill's own `run-all.py` summary shape `FAIL -- 3 of 10 in 45.6s: [...]`. Apply all three substitutions in sequence and return the result. A pytest `FAILED tests/test_x.py::test_y` line (no embedded duration) must pass through unchanged since none of the three patterns match it.
- **Commit:** `feat(implementer-common): add _normalize_failure_signature helper`

### Card 9: Add `signatures` field to `_run_verify_gate`'s verify-failure stuck dict

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_run_verify_gate`'s non-zero-exit-code branch (`_implementer_common.py:778`, `if result.returncode != 0:`), after `output = result.stdout + result.stderr` is computed (line 779), call `_extract_failure_signatures(output)` against that FULL, untruncated `output` (not `output_stripped`, not the truncation-only `omitted` variable) and add its return value as a new `"signatures"` key on the stuck dict returned at `_implementer_common.py:805-809`, alongside the existing `"status"`, `"stuck_type"`, and `"reason"` keys. These are the RAW (unnormalized) extracted lines. Do NOT add a `signatures` key to the separate `except Exception as e:` path's stuck dict (`_implementer_common.py:810-817`) — that path never ran the subprocess to completion, so there is no real output to derive a signature set from; its dict shape stays exactly `{status, stuck_type, reason}`. Update the function's docstring to note the new field on the non-zero-exit return path.
- **Commit:** `feat(implementer-common): add signatures field to verify-gate stuck dict`

### Card 10: Subset-diff waiver logic in `_run_verify_gates`

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new keyword parameter `batch_verify_baseline: list[str] | None = None` to `_run_verify_gates` (`_implementer_common.py:822-831`), parallel to the existing `module_verify_baseline` parameter. Immediately after `batch_result = _run_verify_gate(...)` (line 885), replace the unconditional `if batch_result is not None: return batch_result` (line 888-889) with subset-diff logic: when `batch_result is not None`, read `replay_signatures = batch_result.get("signatures")`. If `batch_verify_baseline` is a non-empty list AND `replay_signatures` is a non-empty list, apply `_normalize_failure_signature` to every entry of both lists and test whether `set(<normalized replay>).issubset(set(<normalized baseline>))`; when that subset check is true, treat the batch-level gate as PASSED — do not return `batch_result`; instead fall through exactly as the `batch_result is None` path already does (continue on to the module-wide gate below). In every other case — `batch_verify_baseline` absent/`None`/empty, OR `replay_signatures` absent/`None`/empty — return `batch_result` unchanged exactly as today; this is the non-vacuous-subset, fail-safe-to-strict rule from `_mill/discussion.md`'s `gap2-subset-diff-semantics` Decision (an empty extracted-signature set is mathematically a subset of any set, so it must never be treated as eligible for waiver). Update the function's docstring to document the new parameter and this waiver rule, mirroring the existing `module_verify_baseline` paragraph's structure and placement.
- **Commit:** `feat(implementer-common): subset-diff batch verify failures against baseline`

### Card 11: Thread `batch_verify_baseline` through `finalize_from_output`/`_forward_output`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new keyword parameter `batch_verify_baseline: list[str] | None = None` to both `finalize_from_output` (`_implementer_common.py:1324-1344`) and `_forward_output` (`_implementer_common.py:1459-1479`), documented in each docstring alongside the existing `module_verify_baseline` paragraph. `finalize_from_output` forwards it unchanged to its own `_forward_output(...)` call (`_implementer_common.py:1406-1425`). `_forward_output` forwards it, unchanged, as `batch_verify_baseline=batch_verify_baseline` to EVERY ONE of its four `_run_verify_gates(...)` call sites (`_implementer_common.py:1546`, `1774`, `1886`, `1997`) — an identical mechanical addition at each of the four call sites, no other logic change to any of them.
- **Commit:** `feat(implementer-common): thread batch_verify_baseline through finalize/forward paths`

### Card 12: Unit tests for `_extract_failure_signatures` and `_normalize_failure_signature`

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add tests for `_extract_failure_signatures`: empty string input yields an empty list; a Go-style sample containing both `"--- FAIL: TestFoo (0.00s)"` and `"FAIL\tgithub.com/pkg\t0.123s"` lines mixed with non-matching lines yields exactly those two lines, in order; a pytest sample containing `"FAILED tests/test_x.py::test_y"` yields that line; output with no recognized markers yields an empty list (not an exception). Add tests for `_normalize_failure_signature`: `"--- FAIL: TestFoo (0.00s)"` and `"--- FAIL: TestFoo (1.23s)"` normalize to the same value; `"FAIL\tgithub.com/pkg\t0.123s"` and `"FAIL\tgithub.com/pkg\t0.456s"` normalize to the same value; `"FAILED tests/test_x.py::test_y"` (no embedded duration) is unchanged by normalization; `"--- FAIL some_test (1.2s) ---"` and `"--- FAIL some_test (3.4s) ---"` (mill's own `run-all.py` per-test shape) normalize to the same value; `"FAIL -- 3 of 10 in 45.6s: [...]"` and `"FAIL -- 3 of 10 in 12.0s: [...]"` (`run-all.py` summary shape) normalize to the same value. Follow this file's existing per-case test-function style, PASS/FAIL print-and-return-code convention (see the "Test H" truncation fixture around `test-implementer-common.py:2193-2232` for the `run-all.py` FAIL-marker line shapes already exercised in this file).
- **Commit:** `test(implementer-common): cover failure-signature extraction and normalization`

### Card 13: `_run_verify_gates` subset-diff matrix tests

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add tests for `_run_verify_gates`'s new `batch_verify_baseline` parameter, using this file's existing mocking convention (mocking the underlying subprocess call, or `_run_verify_gate` directly, to control the batch-level gate's returned stuck dict) to cover: (a) replay `signatures` is a non-empty list that is a strict or exact subset of a non-empty `batch_verify_baseline` — the gate returns `None` (passed); (b) replay `signatures` contains one entry absent from `batch_verify_baseline` — the gate returns the stuck dict unchanged with `stuck_type: "verify"`; (c) `batch_verify_baseline` is `None` (not yet computed) — falls back to today's strict behavior (any batch-level verify failure blocks), matching the existing fail-safe direction documented for `module_verify_baseline`; (d) replay `signatures` is an EMPTY list while `batch_verify_baseline` is non-empty — still blocks (the non-vacuous-subset rule: an empty set is never treated as eligible for waiver); (e) the stuck dict has NO `signatures` key at all (simulating `_run_verify_gate`'s exception path) while `batch_verify_baseline` is non-empty — still blocks.
- **Commit:** `test(implementer-common): cover verify-gates baseline subset-diff matrix`

## Batch Tests

`verify:` runs `run-all.py --only test-implementer-common.py`, the sole test file covering every function this batch modifies (`_extract_failure_signatures`, `_normalize_failure_signature`, `_run_verify_gate`, `_run_verify_gates`, `finalize_from_output`, `_forward_output`).
