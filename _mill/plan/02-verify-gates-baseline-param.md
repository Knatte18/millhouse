# Batch: verify-gates-baseline-param

```yaml
task: "Fix agent-mode dispatch races and pipeline gaps"
batch: verify-gates-baseline-param
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py
depends-on: []
```

## Batch Scope

Make `_run_verify_gates` (`_implementer_common.py:642-696`) read-only-baseline-aware: it gains a `module_verify_baseline: str | None` parameter and, when the module-wide gate would otherwise run, consults this value instead of always running the module-wide command unconditionally. `_run_verify_gates` never computes or persists this value itself (per `_mill/discussion.md`'s Decision: "`_run_verify_gates` itself only ever reads this cached value... never computes or persists it") — the caller (batch 3's `--stage baseline`) owns computation and persistence; this batch only teaches the gate to trust a value it's handed. `module_verify_baseline` is threaded as a new optional kwarg through `_forward_output` and `finalize_from_output` (the two callers that already thread `module_wide_verify_cmd` through to `_run_verify_gates`) so every one of the four existing call sites picks it up uniformly — mirroring the exact pattern `#541` used to add `module_wide_verify_cmd` in the first place. This batch has no dependency on batch 1 (`status-baseline-field`): the tests here pass the baseline value directly as a parameter, with no `_status.py` I/O — reading the real cached value from `status.md` is millpy-implement.py's job (batch 3), not this function's.

## Cards

### Card 3: _run_verify_gates baseline-aware short-circuit

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. Add `module_verify_baseline: str | None = None` as a new keyword-only parameter to `_run_verify_gates` (`_implementer_common.py:642-648`) — `module_wide_verify_cmd` sits before the `*` (a positional-or-keyword parameter), so "keyword-only" is the binding constraint here: place the new parameter after the `*`, alongside the existing `git_root` parameter (`:646-647`), not immediately after `module_wide_verify_cmd`.
  2. Change the module-wide gate branch (currently `_implementer_common.py:683-696`: "Batch gate passed (or was skipped); run the module-wide gate if configured") to consult `module_verify_baseline` before running the module-wide command: if `module_verify_baseline == "pre-existing-failures"`, skip the module-wide gate entirely and return `None` (same as `module_wide_verify_cmd is None`) — do NOT run `module_wide_verify_cmd` at all in this branch. In every other case (`module_verify_baseline` is `"clean"` or `None`), run the module-wide gate exactly as it does today (unchanged behavior when `module_verify_baseline is None`, since `None` is the "not yet computed, behave strictly" fallback per `_mill/discussion.md`'s Decision).
  3. Update `_run_verify_gates`'s docstring (`_implementer_common.py:649-677`) to document the new parameter and its three-way behavior (`"clean"`/`None` → run the gate as before; `"pre-existing-failures"` → skip it).
  4. Add `module_verify_baseline: str | None = None` to both `_forward_output` (`_implementer_common.py:863-879`) and `finalize_from_output` (`_implementer_common.py:772-788`), in each case placed adjacent to the existing `module_wide_verify_cmd` parameter, and update both docstrings' Args sections to describe it (mirror the existing `module_wide_verify_cmd` Args entries in shape and tone). `finalize_from_output` forwards its `module_verify_baseline` argument to its `_forward_output` call (`_implementer_common.py:814-829`) exactly like it already forwards `module_wide_verify_cmd`.
  5. Thread `module_verify_baseline` from the new `_forward_output` parameter into all four existing `_run_verify_gates(...)` call sites inside `_forward_output` (`_implementer_common.py:914-916`, `:1097-1100`, `:1190-1193`, `:1279-1282`) — add `module_verify_baseline=module_verify_baseline` as a new keyword argument at each call site, alongside the existing `module_wide_verify_cmd` argument.

  Every parameter defaults to `None` so `millpy-fix.py`'s existing calls to `finalize_from_output`/`_forward_output` (which never pass `module_wide_verify_cmd` or will never pass `module_verify_baseline`) are completely unaffected — this batch changes no observable behavior for any caller that doesn't pass the new parameter.
- **Commit:** `feat(_implementer_common): thread module_verify_baseline through the verify-gate chain`

### Card 4: unit tests for the baseline-aware verify gate

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Append new cases after the existing Case 58 (end of file), following the file's `# Case N:` comment-then-assert style (see Cases 30/31/32, which cover the original `#541` `module_wide_verify_cmd` two-gate sequence, as the closest structural template):
  - Case 59: `module_verify_baseline="pre-existing-failures"` with a failing `module_wide_verify_cmd` — assert the module-wide gate is skipped entirely (the batch gate's own pass/fail is unaffected; overall result is `success`, not `stuck/verify`) and that the module-wide command is never invoked (mock/stub the subprocess call and assert it was not called with the module-wide command, mirroring how Case 30/31/32 stub verify execution).
  - Case 60: `module_verify_baseline="clean"` — assert the module-wide gate runs exactly as in Case 30 (batch passes, module-wide fails → `stuck/verify` with `"[module-wide verify]"`-prefixed reason) and Case 31 (module-wide passes → overall success), i.e. behavior is unchanged from the pre-baseline-param cases when `"clean"`.
  - Case 61: `module_verify_baseline=None` (the default, not yet computed) — assert identical behavior to Case 60 (`"clean"`): the module-wide gate still runs strictly. This is the fail-safe-toward-strict default the discussion decided on.
  - Case 62: backward-compatibility guard — calling `_forward_output`/`finalize_from_output` without passing `module_verify_baseline` at all (positional/kwarg omitted) behaves identically to Case 61 (defaults to `None`, gate runs strictly) — confirms no existing caller (e.g. `millpy-fix.py`) changes behavior from this batch alone.
- **Commit:** `test(_implementer_common): cover module_verify_baseline gate short-circuit`

## Batch Tests

`verify:` runs `test-implementer-common.py` only. The new cases are additive to the existing `#541` module-wide-gate coverage in that same file; no other test file exercises `_run_verify_gates`.
