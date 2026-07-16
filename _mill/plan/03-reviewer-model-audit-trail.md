# Batch: reviewer-model-audit-trail

```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
batch: reviewer-model-audit-trail
number: 3
cards: 6
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-finalize.py test-review-cli.py test-review-prepare-envelope.py
depends-on: [2]
```

## Batch Scope

This batch closes #644: the review file's `reviewer_model` field is currently a value the reviewer subagent itself echoes into its own YAML block from a prompt-time token (baked in at prepare time from the config-resolved reviewer name), so it never reflects a manual operator model override or an automatic large-prompt spec switch. This batch adds a `--actual-model` override channel threaded from the Builder's step-3-recorded actually-dispatched model (introduced in the previous batch) through each review CLI's `--stage finalize` and down into a new shared `_review_common.py` helper that rewrites or injects the `reviewer_model:` line in the reviewer's raw output before it's written to disk. No implementer-side equivalent exists to fix (confirmed absent during discussion — `finalize_from_output` writes no model-related field).

## Cards

### Card 12: shared `reviewer_model` override helper in `_review_common.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new function `apply_actual_model_override(raw_text: str, actual_model: str | None) -> str` to `plugins/mill/scripts/_review_common.py`, placed near `finalize_scope` (`_review_common.py:1664`). Behavior: if `actual_model` is `None`, return `raw_text` unchanged. Otherwise, search `raw_text` for a line matching `reviewer_model:\s*\S.*` (the YAML-block line the review-prompt templates instruct the reviewer to echo, e.g. `review-code-batch.md:53`'s `<REVIEWER_MODEL>` token substitution) using a line-anchored regex; if found, replace that line's value with `reviewer_model: {actual_model}` in place; if not found (the reviewer omitted or malformed the line), inject a new `reviewer_model: {actual_model}` line immediately after the line matching `` ```yaml `` that opens the same fenced block the reviewer's YAML header lives in (fall back to inserting immediately after the first `` ```yaml `` occurrence in `raw_text` if no better anchor is found). Then extend `finalize_scope` (`_review_common.py:1664-1693`) with a new keyword parameter `actual_model: str | None = None`, calling `raw_text = apply_actual_model_override(raw_text, actual_model)` as the first line of the function body, before `parse_verdict(raw_text)` and `write_review_file(...)` — so the override applies once, upstream of both verdict parsing and disk write, and both operate on the corrected text (and the `[reviewer_model corrected]` value ends up on disk verbatim). Absent `actual_model`, `finalize_scope`'s behavior is byte-for-byte unchanged from today.
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

### Card 16: the three review CLIs gain an `--actual-model` finalize flag

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In each of the three CLIs' `argparse.ArgumentParser` setup, add a new optional argument `--actual-model` (`default=None`, help text: "Model tier actually dispatched via the Agent tool for this round, when it diverges from the prepare envelope's `model` field (e.g. an operator-directed override); threaded into the review file's `reviewer_model` field. Omit to leave today's config-derived value untouched."). In each CLI's `elif args.stage == "finalize":` branch (`millpy-review-code.py:172-202`, `millpy-review-plan.py:173+`, `millpy-review-discussion.py:131-171`), pass `actual_model=args.actual_model` through to the corresponding `finalize(...)` call.
- **Commit:** `feat(review-cli): add --actual-model finalize flag for code/plan/discussion review (#644)`

### Card 17: document actual-dispatched-model recording and threading in `mill-go/SKILL.md`

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In step 6 ("Run finalize stage", `plugins/mill/skills/mill-go/SKILL.md:153-157`), after the existing sentence about threading `--session-id`/`--start-sha`/`--nits-only`/`--round`, add: for the three review CLIs specifically, additionally pass `--actual-model <value>` using the model value the previous batch's step-3 edit recorded as actually passed to this round's Agent tool call — this keeps the finalized review file's `reviewer_model` field accurate even when the Builder dispatched a different tier than the prepare envelope's `model` field named (a manual override) or the prepare-stage's own large-prompt auto-switch already changed it before the envelope was read. Implement/fix/merge-in CLIs' finalize calls do not take this flag (no `reviewer_model`-equivalent field exists on their side, per this task's earlier confirmed-absent decision).
- **Commit:** `docs(mill-go): document --actual-model threading into review finalize calls (#644)`

## Batch Tests

`verify:` runs `test-review-common.py` (extend with cases for the new `apply_actual_model_override` helper: rewrites an existing well-formed `reviewer_model:` line; injects a `reviewer_model:` line when the reviewer's raw text omits or malforms it; leaves `raw_text` byte-for-byte unchanged when `actual_model` is `None`), `test-review-finalize.py` and `test-review-cli.py` (extend for the audit-trail fix end-to-end: a `--stage finalize` call with `--actual-model <tier>` produces a review file whose `reviewer_model:` line matches the passed tier regardless of what the reviewer echoed; omitting the flag reproduces today's config-derived value unchanged), and `test-review-prepare-envelope.py` (re-run as a regression check since it already covers all three review CLIs' envelope shape end-to-end and this batch touches the same CLI files as the previous one).
