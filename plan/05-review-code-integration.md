# Batch: review-code-integration

```yaml
task: 'review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure'
batch: review-code-integration
cards: 4
verify: uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"
depends-on: [content-helpers]
```

## Batch Scope

Mirrors the `_review_plan` integration in `_review_code.run`: ERROR-handling parity (no-raise pattern), `deletes_union` plumbing, `## Intentionally deleted` surface, and timeout plumbing for both per-batch and holistic calls. No mid-round resume here — code review is single-scope per call (one batch OR holistic, not both) so there's no in-call resume window. Independent of `review-plan-integration` — both consume the same `content-helpers` foundation.

## Cards

### Card 19: ERROR-handling parity in `_review_code.run`

- **Reads:**
  - `plugins/mill/scripts/_review_code.py`
- **Modifies:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace both `raise ReviewError(...)` sites in the dispatch path with structured ERROR returns. (a) The initial-call handler at line 240–242 (`except LLMError as exc: raise ReviewError(f"Code reviewer failed: {exc}") from exc`) — replace with: build and return `ReviewResult(type="code", round=round_n, verdict="REQUEST_CHANGES", blocking_count=0, reviews=[{"scope": scope_label, "verdict": "ERROR", "file": None, "error": str(exc), "session_id": None}])`. (b) The NEED_CONTEXT resume-retry handler at line 267–268 (`except LLMError as exc: raise ReviewError(f"Code reviewer failed on resume: {exc}") from exc`) — replace with the same shape, but the `error` field is `f"resume retry failed: {exc}"` so the fix-pass can tell which call failed. Other `ReviewError` raises in the function (e.g. invalid `batch_name`, `Plan overview not found`, `Round N exceeds max M`) stay unchanged — those are config / structural errors, not LLM failures.
- **Commit:** `fix(review-code): record verdict=ERROR instead of raising on LLM failure (#84)`

### Card 20: `deletes_union` + `## Intentionally deleted` in `_review_code.run`

- **Reads:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_common.py`
- **Modifies:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Compute `deletes_union = compute_deletes_union(plan_dir)` near the existing `creates_union = compute_creates_union(plan_dir)` line. Pass `deletes_union=deletes_union` keyword to the `resolve_ref_paths(...)` call (line ~186-189). Extend `_build_artefact_section` (or its caller) so when `deletes_union` is non-empty, append `\n\n` followed by `build_deletes_section(sorted(deletes_union))` to the returned artefact-section string. The cleanest split: pass `deletes_union: set[str]` as a new positional argument to `_build_artefact_section` (after `ancestors_on_disk`); inside the function, after building the existing manifest + artefact body, append the deletes section if non-empty. Apply the surface to both the per-batch (`batch_name="<name>"`) and holistic (`batch_name=None`) modes — the function is shared, so the change is in one place. Sorting keeps the prompt stable.
- **Commit:** `feat(review-code): surface intentional deletes to reviewer prompts`

### Card 21: Plumb `bulk_timeout` / `holistic_timeout` in `_review_code.run`

- **Reads:**
  - `plugins/mill/scripts/_review_code.py`
  - `wiki/config.yaml`
- **Modifies:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** After `reviewer_name = cfg["review"]["code"]["reviewer"]` and `reviewer = load_reviewer(reviewer_name)`, compute the effective timeout: `timeout = cfg["llm"]["holistic_timeout"] if batch_name is None else cfg["llm"]["bulk_timeout"]`. Pass `timeout=timeout` to both reviewer.run calls — the initial dispatch (line ~239 today) and the NEED_CONTEXT resume retry (line ~264 today). The reviewer module already accepts `timeout` per Card 7. No other behaviour change.
- **Commit:** `feat(review-code): plumb bulk_timeout / holistic_timeout from config`

### Card 22: Tests for `_review_code.run` integration

- **Reads:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add tests covering each of cards 19–21. Reuse the existing fixture helpers in `test-review-code-flow.py`; extend `_make_batch_file` (if a local copy lives there) to accept a `deletes:` argument, or use the same shape as `test-review-plan-flow.py`. (a) ERROR-handling parity — seed the stub to raise `LLMError` on first call; call `_review_code.run` once with `batch_name="<batch>"` and once with `batch_name=None`; assert each returns `ReviewResult(verdict="REQUEST_CHANGES", reviews=[{"scope": ..., "verdict": "ERROR", "file": None, "error": "...", "session_id": None}])` rather than raising `ReviewError`. (b) ERROR on resume — seed two stub responses: first a NEED_CONTEXT verdict that triggers the resume retry, then an `LLMError` raise on the retry; assert the resulting ReviewResult has `verdict: REQUEST_CHANGES` with the single ERROR entry whose `error` field starts with `"resume retry failed:"`. (c) deletes surface — fixture batch declares `Deletes:` token `\`legacy/x.py\``; assert the captured prompt contains `## Intentionally deleted` and `legacy/x.py`. (d) timeout plumbing — set `cfg["llm"]["bulk_timeout"] = 900` and `cfg["llm"]["holistic_timeout"] = 1800`; call `_review_code.run` with `batch_name="<batch>"` and assert `captured_prompts()[0][1]["timeout"] == 900`; call again with `batch_name=None` and assert `captured_prompts()[0][1]["timeout"] == 1800`. Existing tests in the file must continue to pass.
- **Commit:** `test(review-code): cover ERROR parity, deletes, timeouts`

## Batch Tests

`uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"` — `test-review-code-flow.py` covers Cards 19–22. The full suite must be green at end of batch.
