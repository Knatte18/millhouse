# Batch: effort-tier-review-cli

```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
batch: effort-tier-review-cli
number: 3
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-prepare-envelope.py
depends-on: [2]
```

## Batch Scope

This batch completes closing #628/#633 by surfacing `effort` through the three review backends' `prepare()` functions and their CLI wrappers, and documents the Agent-tool limitation in `mill-go/SKILL.md`. It depends on the previous batch (`effort-tier-implementer`) because both were originally one batch that exceeded `pipeline.max_batch_context_tokens`; splitting on the implementer/fixer-vs-review-CLI boundary — rather than any file this batch touches — is what the dependency reflects (no shared file with the previous batch; the dependency exists only to preserve the discussion's intended sequencing group). External interface the next batch (`reviewer-model-audit-trail-backend`) consumes: this batch's `mill-go/SKILL.md` step-3 edit (Card 11) introduces the instruction to record the model value actually passed to each Agent tool call as a local Builder variable — the audit-trail batches' step-6 edit threads that same recorded variable into finalize calls as `--actual-model`.

## Cards

### Card 7: `_review_code.py` surfaces `effort` from the resolved spec

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_code.prepare` (`plugins/mill/scripts/_review_code.py:194-381`), the returned dict at line 375-381 currently has keys `prompt_text`, `model`, `round`, `reviews_dir`, `scope`. Add `"effort": spec.get("effort")` to that dict — `spec` is already resolved at line 336 (`spec = _reviewers.resolve(registry, reviewer_name)`) and, for the holistic scope, potentially re-resolved by `maybe_switch_spec_for_large_prompt` at line 371-373 (assign the returned dict's `effort` key from whichever `spec` is bound at the point of the `return` statement, i.e. after the large-prompt switch has already run for holistic scope, so a switched spec's effort is what's surfaced — consistent with how `model` at line 377 already reflects the post-switch spec).
- **Commit:** `feat(review-code): surface effort field from resolved reviewer spec (#628, #633)`

### Card 8: `_review_plan.py` surfaces `effort` from both batch and holistic resolved specs

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** `_review_plan.prepare` (`plugins/mill/scripts/_review_plan.py:313+`) has two scope-specific return sites, each returning a dict with a `"model": <spec>.get("model")` key: the batch-scope path (around line 447, using `batch_spec`) and the holistic-scope path (around line 538, using `holistic_spec`, after `maybe_switch_spec_for_large_prompt` reassigns it at line 533-535). Add `"effort": batch_spec.get("effort")` to the batch-scope return dict and `"effort": holistic_spec.get("effort")` to the holistic-scope return dict, mirroring Card 7's approach for `_review_code.py` — each using whichever spec variable is bound at that return site (post-switch for holistic, matching how `model` is already sourced there).
- **Commit:** `feat(review-plan): surface effort field from resolved batch and holistic reviewer specs (#628, #633)`

### Card 9: `_review_discussion.py` surfaces `effort` from the resolved spec

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_discussion.prepare` (`plugins/mill/scripts/_review_discussion.py:44+`), find the returned dict (parallel in shape to `_review_code.prepare`'s, with a `"model"` key sourced from the spec that `maybe_switch_spec_for_large_prompt` reassigns at line 116). Add `"effort": <spec>.get("effort")` to that dict using the same post-switch spec variable that already supplies `"model"`.
- **Commit:** `feat(review-discussion): surface effort field from resolved reviewer spec (#628, #633)`

### Card 10: the three review CLIs forward `effort` into their prepare envelopes

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/unit_tests/test-review-prepare-envelope.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In each of the three CLIs' `--stage prepare` envelope-construction blocks (`millpy-review-code.py:156-167`, `millpy-review-plan.py` — the analogous envelope dict around line 162's `"model"` key, `millpy-review-discussion.py:115-126`), add `"effort": prepare_result.get("effort")` as an envelope key only when `prepare_result.get("effort")` is not `None` — mirror the conditional-inclusion pattern the previous batch's `emit_prepare` uses for `start_sha`/`effort` (i.e. `if prepare_result.get("effort") is not None: envelope["effort"] = prepare_result["effort"]`, placed after the `envelope = {...}` dict literal and before `print(json.dumps(envelope))`), rather than always including the key with a possible `null` value — this matches the existing convention the implement/fix CLIs' `emit_prepare` establishes where the key is omitted, not nulled, when absent. In `plugins/mill/unit_tests/test-review-prepare-envelope.py`, extend the file's existing per-CLI envelope fixtures (the same pattern that already builds discussion/plan/code prepare envelopes and asserts `envelope["model"]`) with cases asserting `envelope["effort"]` matches the configured reviewer's non-null effort tier for all three review types, and that `"effort"` is absent from the envelope when the configured reviewer's spec has no effort key.
- **Commit:** `feat(review-cli): forward effort field into prepare envelopes for code/plan/discussion review (#628, #633)`

### Card 11: document the effort-tier envelope field and its harness limitation in `mill-go/SKILL.md`

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the "## Agent-mode dispatch" section: (1) in step 2's field-extraction list (currently `plugins/mill/skills/mill-go/SKILL.md:111-116`, ending "...`output_path`..."), add `effort` to the list of fields extracted from the envelope, worded like the existing `start_sha` entry ("`effort` (string or null — present only when the resolved spec has a non-null effort tier, e.g. `\"high\"`)"). (2) In step 3 ("Call Agent tool", currently lines 118-125), add an instruction directly after the existing `agentId`-recording instruction: record the `model` value actually passed to this Agent tool call into a local Builder variable (ordinarily identical to the envelope's `model` field, copied through unchanged; only differs when the operator explicitly instructs a different tier for this specific dispatch) — this recorded value is consumed by a later batch's step-6 edit. Immediately after, add a sentence stating explicitly that the envelope's `effort` field (from step 2) has no corresponding Agent-tool parameter to forward it to — the Agent tool call takes only `subagent_type`, `model`, `prompt`, and optionally `isolation`; `effort` is extracted for `subprocess`/`psmux` dispatch parity and audit visibility only, and is a documented, intentional gap under `dispatch: agent`, not a silent one.
- **Commit:** `docs(mill-go): document effort envelope field and its agent-mode dispatch limitation (#628, #633)`

## Batch Tests

`verify:` runs `test-review-prepare-envelope.py` (extend with cases asserting the `effort` key appears in the discussion/plan/code prepare envelopes when the configured reviewer's spec has a non-null effort, and is absent when it doesn't — this file already builds envelopes for all three review CLIs in one place per its `test_*_prepare_envelope_has_output_path` naming pattern). Cards 7-9's backend `prepare()` changes and Card 11's `mill-go/SKILL.md` documentation edit have no dedicated unit-test file of their own — they are exercised transitively through `test-review-prepare-envelope.py`'s CLI-level envelope assertions (backends) and verified by direct reading (docs-only Markdown change, no runnable surface).
