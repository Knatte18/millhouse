# Batch: reviewer-model-audit-trail-backend

```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
batch: reviewer-model-audit-trail-backend
number: 4
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py
depends-on: [3]
```

## Batch Scope

This batch adds the backend half of closing #644: a shared `apply_actual_model_override` helper in `_review_common.py` that rewrites or injects the `reviewer_model:` line in a reviewer's raw output before it's written to disk, threaded through all three review backends' `finalize()` functions via a new `actual_model` keyword parameter. It depends on the previous batch (`effort-tier-review-cli`) because the two were originally one oversized batch (`pipeline.max_batch_context_tokens`); the backend/CLI split here mirrors the same split already made for the effort-tier work. The next batch (`reviewer-model-audit-trail-cli`) consumes this batch's `actual_model` parameter by adding the CLI-level `--actual-model` flag that supplies it.

## Cards

### Card 12: shared `reviewer_model` override helper in `_review_common.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new function `apply_actual_model_override(raw_text: str, actual_model: str | None) -> str` to `plugins/mill/scripts/_review_common.py`, placed near `finalize_scope` (`_review_common.py:1664`). Behavior: if `actual_model` is `None`, return `raw_text` unchanged. Otherwise, search `raw_text` for a line matching `reviewer_model:\s*\S.*` (the YAML-block line the review-prompt templates instruct the reviewer to echo, e.g. `review-code-batch.md:53`'s `<REVIEWER_MODEL>` token substitution) using a line-anchored regex; if found, replace that line's value with `reviewer_model: {actual_model}` in place; if not found (the reviewer omitted or malformed the line), inject a new `reviewer_model: {actual_model}` line immediately after the line matching `` ```yaml `` that opens the same fenced block the reviewer's YAML header lives in (fall back to inserting immediately after the first `` ```yaml `` occurrence in `raw_text` if no better anchor is found). Then extend `finalize_scope` (`_review_common.py:1664-1693`) with a new keyword parameter `actual_model: str | None = None`, calling `raw_text = apply_actual_model_override(raw_text, actual_model)` as the first line of the function body, before `parse_verdict(raw_text)` and `write_review_file(...)` — so the override applies once, upstream of both verdict parsing and disk write, and both operate on the corrected text. Absent `actual_model`, `finalize_scope`'s behavior is byte-for-byte unchanged from today. In `plugins/mill/unit_tests/test-review-common.py`, add cases for `apply_actual_model_override`: rewrites an existing well-formed `reviewer_model:` line to the passed value; injects a `reviewer_model:` line right after the opening `` ```yaml `` fence when the input text has no such line; returns `raw_text` completely unchanged (identity) when `actual_model` is `None`; and a case confirming `finalize_scope(..., actual_model="sonnet")` produces a written review file whose content reflects the override while `finalize_scope(...)` with `actual_model` omitted reproduces today's unmodified behavior.
- **Commit:** `feat(review-common): add reviewer_model override helper to finalize_scope (#644)`

### Card 13: `_review_code.py` threads `actual_model` through its `finalize`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_code.finalize` (`plugins/mill/scripts/_review_code.py:513-590`), add a new keyword parameter `actual_model: str | None = None` to the function signature, and pass `actual_model=actual_model` through to the `finalize_scope(...)` call at line 553-555 (the success path — the exception-handling fallback path that calls `write_review_file` directly on a `ReviewError` does not need the override, since a parse failure means no valid `reviewer_model:` line exists to correct anyway).
- **Commit:** `feat(review-code): thread actual_model override into finalize (#644)`

### Card 14: `_review_plan.py` threads `actual_model` through its `finalize`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_plan.finalize` (`plugins/mill/scripts/_review_plan.py:546+`), add a new keyword parameter `actual_model: str | None = None` to the function signature, and pass `actual_model=actual_model` through to the `finalize_scope(...)` call (the success path, mirroring Card 13's approach for `_review_code.py`; the `ReviewError`-fallback path that calls `write_review_file` directly is left unchanged for the same reason).
- **Commit:** `feat(review-plan): thread actual_model override into finalize (#644)`

### Card 15: `_review_discussion.py` threads `actual_model` through its `finalize`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_discussion.finalize` (`plugins/mill/scripts/_review_discussion.py:129+`), add a new keyword parameter `actual_model: str | None = None` to the function signature, and pass `actual_model=actual_model` through to the `finalize_scope(...)` call at its success path (mirroring Cards 13 and 14; the `ReviewError`-fallback path is left unchanged).
- **Commit:** `feat(review-discussion): thread actual_model override into finalize (#644)`

## Batch Tests

`verify:` runs `test-review-common.py` (extend with cases for the new `apply_actual_model_override` helper: rewrites an existing well-formed `reviewer_model:` line; injects a `reviewer_model:` line when the reviewer's raw text omits or malforms it; leaves `raw_text` byte-for-byte unchanged when `actual_model` is `None`; and a `finalize_scope(..., actual_model=...)` end-to-end case). Cards 13-15's per-backend `finalize()` threading have no dedicated unit-test file of their own at this batch's layer — they are exercised end-to-end by the next batch's `test-review-finalize.py`/`test-review-cli.py` cases, which drive `finalize()` through the CLI's `--actual-model` flag once it exists.
