# Batch: nits-only-envelope-threading

```yaml
task: Fix nit-enforcement gate marker gaps, NIT-dispatch wording, implementer liveness probe, and Haiku false-completion
batch: nits-only-envelope-threading
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-fix.py
depends-on: []
```

## Batch Scope

Root-cause fix for #619 (and, incidentally, #612's reported symptom): under Agent-mode dispatch, `millpy-fix.py`'s `--stage prepare` and `--stage finalize` are two separate process invocations, so `argparse`'s `args.nits_only` does not survive between them unless the orchestrator explicitly re-passes `--nits-only` at finalize. This batch makes the *value* survive the process boundary by threading `nits_only` through the prepare-stage JSON envelope (mirroring the existing `start_sha`-omitted-when-`None` pattern in `emit_prepare`), so that a subsequent SKILL.md instruction (batch 2, which depends on this batch) can read the envelope field and re-pass the flag correctly. This batch is purely script + test — no SKILL.md changes here. External interface batch 2 depends on: the prepare-stage JSON envelope from `millpy-fix.py --stage prepare --nits-only` now includes `"nits_only": true`; the field is entirely absent when `--nits-only` was not passed (do not emit `"nits_only": false`).

## Cards

### Card 1: Add `nits_only` optional parameter to `emit_prepare`

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_implementer_common.emit_prepare` (signature `emit_prepare(briefs_dir, role, scope, round_n, prompt_text, model_tier, session_id, start_sha=None)`, currently ~line 750), add a new keyword-only-by-convention parameter `nits_only: bool = False` after the existing `start_sha: str | None = None` parameter. Mirror the existing `start_sha` envelope-omission pattern exactly: the function body currently has
  ```python
      if start_sha is not None:
          envelope["start_sha"] = start_sha
      print(json.dumps(envelope))
      return 0
  ```
  Add, immediately after the `start_sha` block and before `print(json.dumps(envelope))`:
  ```python
      if nits_only:
          envelope["nits_only"] = True
  ```
  So the envelope key `"nits_only"` is present (value `True`) only when the caller passed `nits_only=True`; it must be entirely absent from the dict otherwise — do not add `envelope["nits_only"] = False` in an else branch. Update the function's docstring to document the new parameter, following the existing style of the `start_sha` docstring line (e.g. "`nits_only`: when True, the envelope includes `"nits_only": true`, signalling that any finalize call re-invoking this scope/round must re-pass `--nits-only`.").
- **Commit:** `fix(implementer-common): thread nits_only through emit_prepare envelope (#619)`

### Card 2: Test `emit_prepare`'s new `nits_only` envelope field

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** This test file uses a manual case-counter convention (`# Case N: <description>` comments, `_capture_stdout` helper, an `errors` counter incremented on `FAIL`, `print("PASS: ...")` / `print(f"FAIL: ... ", file=sys.stderr)`). The existing `emit_prepare` test is "Case 12: emit_prepare writes brief and prints prepare JSON" (~line 480-515). Add a new case immediately after it (renumber as **Case 64**, following on from the file's current highest case number 63 at ~line 3131) that: (a) calls `emit_prepare(briefs_dir, "fix", "test-batch", 1, "prompt text", "haiku", "session-abc", nits_only=True)` and asserts the parsed JSON output contains `data["nits_only"] is True`; (b) calls `emit_prepare(briefs_dir, "fix", "test-batch", 2, "prompt text", "haiku", "session-abc")` (parameter omitted — default `False`) and asserts `"nits_only" not in data` (key must be absent, not merely falsy) — use two separate `tempfile.TemporaryDirectory()` blocks (or two distinct `briefs_dir` subpaths within one) so the two `emit_prepare` calls don't collide on the same brief file path (round numbers 1 and 2 already keep the brief filenames distinct: `fix-test-batch-r1.md` / `fix-test-batch-r2.md`). Follow the exact try/except/print(PASS or FAIL)/errors-increment structure used by every other case in this file.
- **Commit:** `test(implementer-common): cover emit_prepare nits_only envelope field (#619)`

### Card 3: Wire `millpy-fix.py`'s `--stage prepare` to pass `nits_only`

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `millpy-fix.py`'s `if args.stage == "prepare":` branch (~line 503-516), the current call is:
  ```python
      return emit_prepare(
          briefs_dir,
          "fix",
          scope_label,
          args.round,
          prompt_text,
          model_tier,
          session_id,
          start_sha=start_sha,
      )
  ```
  Add `nits_only=args.nits_only,` as an additional keyword argument (after `start_sha=start_sha,`). `args.nits_only` is already parsed by the existing `--nits-only` `argparse` flag (`action="store_true"`, default `False`) — no argparse changes needed, only the call-site wiring. Do not touch the `--stage finalize` branch (~line 281-324) — it already does `nits_only=args.nits_only` correctly at line 319; this card only fixes the prepare side, which previously dropped the flag entirely.
- **Commit:** `fix(millpy-fix): pass nits_only through to emit_prepare at prepare stage (#619)`

### Card 4: Test `millpy-fix.py --stage prepare --nits-only` envelope shape

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** This file uses `unittest.TestCase` style with a `self._run_main([...])` helper. The existing pattern to follow is `test_stage_prepare_batch_scope` (~line 555-576), which mocks `millpy_fix._render.render` and `millpy_fix._implementer_claude.run`, calls `self._run_main([...])`, asserts `rc == 0`, `mock_run.assert_not_called()`, and inspects the parsed JSON envelope. Add a new test method `test_stage_prepare_batch_scope_with_nits_only` (placed immediately after `test_stage_prepare_batch_scope`) that: passes `"--nits-only"` in the args list alongside `"--scope", "batch", "--batch-name", "test-batch", "--review-file", str(self.review_file), "--stage", "prepare"`; asserts `rc == 0`; asserts the parsed JSON envelope has `data["nits_only"] is True`. Add a second test method `test_stage_prepare_batch_scope_without_nits_only_omits_field` (immediately after) that runs the same args WITHOUT `"--nits-only"` and asserts `"nits_only" not in data` (key absent). Both tests confirm the prepare-stage envelope now correctly reflects whether `--nits-only` was passed, closing the gap that caused #619.
- **Commit:** `test(millpy-fix): cover --stage prepare --nits-only envelope field (#619)`

## Batch Tests

`verify:` runs `test-implementer-common.py` and `test-millpy-fix.py` via `run-all.py --only` — the two files touched by cards 2 and 4, plus the existing regression suites for both files (marker-writing tests at `test-implementer-common.py` case 56-58 and `test-millpy-fix.py`'s `test_nits_only_flag_appends_marker_and_flag` / `test_nits_only_all_pushback_zero_commit_is_success_not_stuck`) run alongside the new cases as regression coverage that this batch does not disturb the existing finalize-stage marker-writing contract (which was never broken — only the prepare-stage envelope was incomplete).
