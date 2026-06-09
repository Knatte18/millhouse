# Batch: Core fix: emit_prepare + millpy-fix.py

```yaml
task: Fix agent-pipeline reliability gaps in finalize/success contract
batch: "'Core fix: emit_prepare + millpy-fix.py'"
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: []
```

## Batch Scope

This batch fixes Gaps A and B in `millpy-fix.py`: `start_sha` was never persisted from prepare to finalize (Gap A), and `session_id` was regenerated as a fresh UUID in finalize instead of reusing the prepare-stage value (Gap B). The fix has two parts: (1) extend `emit_prepare()` in `_implementer_common.py` with an optional `start_sha` kwarg so fixer prepare calls can include it in the envelope, and (2) add `--start-sha` and `--session-id` args to `millpy-fix.py` so finalize can receive them from the prepare envelope.

Batch 3 (SKILL.md) and Batch 4 (tests) both consume this batch's API.

## Cards

### Card 1: Add start_sha kwarg to emit_prepare in _implementer_common.py

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add `start_sha: str | None = None` as a new last parameter (after `session_id`) to `emit_prepare()`. The full new signature is: `emit_prepare(briefs_dir, role, scope, round_n, prompt_text, model_tier, session_id, start_sha=None)`.
  - When `start_sha is not None`, add `"start_sha": start_sha` to the `envelope` dict immediately before `print(json.dumps(envelope))`. When `start_sha is None`, omit the key entirely — do NOT emit `"start_sha": null`.
  - No other changes: `emit_prepare_no_dispatch`, `finalize_from_output`, and `_forward_output` are NOT changed.
  - All existing callers pass positional args and omit `start_sha`, so they remain backward-compatible.
- **Commit:** `feat(pipeline): add start_sha kwarg to emit_prepare`

### Card 2: Fix millpy-fix.py prepare->finalize boundary (Gaps A and B)

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add `--start-sha` argument to the argparser: `parser.add_argument("--start-sha", default=None, help="SHA captured at prepare stage (from prepare envelope).")`. This arg is optional (used only in finalize stage).
  - Add `--session-id` argument to the argparser: `parser.add_argument("--session-id", default=None, help="Session ID from prepare envelope (for finalize stage).")`. This arg is optional (used only in finalize stage).
  - In the `args.stage == "finalize"` branch (the early-return block that calls `finalize_from_output`): replace `start_sha=None` with `start_sha=args.start_sha` and replace `session_id=session_id` with `session_id=args.session_id`. Do NOT change the `snapshot_path` logic. The local `session_id = str(uuid.uuid4())` at line 172 of `main()` is NOT removed — it is still used for prepare and full stages.
  - In the `args.stage == "prepare"` early-return block (after the shared dispatch tail computes `start_sha` and `prompt_text`): change the `emit_prepare(...)` call to pass `start_sha=start_sha` as a keyword argument. The call becomes: `emit_prepare(briefs_dir, "fix", scope_label, args.round, prompt_text, model_tier, session_id, start_sha=start_sha)`.
  - **Ordering invariant preserved:** `start_sha` is captured via `git rev-parse HEAD` in the shared dispatch tail BEFORE the `args.stage == "prepare"` early-return. Do not move the rev-parse after the early-return.
  - The full stage (`_forward_output(output, project_root, start_sha=start_sha, session_id=session_id)`) is NOT changed.
  - No new imports needed — `_subprocess_util` is already imported.
- **Commit:** `fix(pipeline): thread start_sha and session_id through fix finalize (Gaps A/B)`

## Batch Tests

`verify:` runs `test-implementer-common.py`, which tests `emit_prepare` (including envelope shape) and `_forward_output` (including the inferred-success branch that requires `start_sha`). These tests cover the Card 1 change directly. Card 2 (CLI wiring in `millpy-fix.py`) is tested end-to-end in Batch 4's `test-fix-finalize.py`. The existing `test-implementer-common.py` suite is focused and fast (no LLM calls, real git fixtures via tempfile).
