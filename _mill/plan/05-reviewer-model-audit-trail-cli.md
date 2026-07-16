# Batch: reviewer-model-audit-trail-cli

```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
batch: reviewer-model-audit-trail-cli
number: 5
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-finalize.py test-review-cli.py
depends-on: [4]
```

## Batch Scope

This batch completes closing #644 by adding the `--actual-model` CLI flag to all three review CLIs' `--stage finalize` and documenting the recording/threading contract in `mill-go/SKILL.md`. No implementer-side equivalent exists to fix (confirmed absent during discussion — `finalize_from_output` writes no model-related field). It depends on the previous batch for the `actual_model` parameter each `finalize()` function now accepts.

## Cards

### Card 16: the three review CLIs gain an `--actual-model` finalize flag

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/unit_tests/test-review-finalize.py`
  - `plugins/mill/unit_tests/test-review-cli.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In each of the three CLIs' `argparse.ArgumentParser` setup, add a new optional argument `--actual-model` (`default=None`, help text: "Model tier actually dispatched via the Agent tool for this round, when it diverges from the prepare envelope's `model` field (e.g. an operator-directed override); threaded into the review file's `reviewer_model` field. Omit to leave today's config-derived value untouched."). In each CLI's `elif args.stage == "finalize":` branch (`millpy-review-code.py:172-202`, `millpy-review-plan.py:173+`, `millpy-review-discussion.py:131-171`), pass `actual_model=args.actual_model` through to the corresponding `finalize(...)` call. In `plugins/mill/unit_tests/test-review-finalize.py`, extend coverage for all three review types' `finalize()` functions with a case asserting a passed `actual_model` value ends up in the written review file's `reviewer_model:` line regardless of what the raw reviewer text originally echoed, and that omitting it reproduces today's unmodified value. In `plugins/mill/unit_tests/test-review-cli.py`, extend the CLI-level `--stage finalize` invocation coverage (subprocess or in-process `main(argv)` call, matching the file's existing pattern) with a case for each of the three CLIs passing `--actual-model <tier>` and asserting the resulting review file reflects it.
- **Commit:** `feat(review-cli): add --actual-model finalize flag for code/plan/discussion review (#644)`

### Card 17: document actual-dispatched-model recording and threading in `mill-go/SKILL.md`

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In step 6 ("Run finalize stage", `plugins/mill/skills/mill-go/SKILL.md:153-157`), after the existing sentence about threading `--session-id`/`--start-sha`/`--nits-only`/`--round`, add: for the three review CLIs specifically, additionally pass `--actual-model <value>` using the model value the `effort-tier-review-cli` batch's step-3 `mill-go/SKILL.md` edit recorded as actually passed to this round's Agent tool call — this keeps the finalized review file's `reviewer_model` field accurate even when the Builder dispatched a different tier than the prepare envelope's `model` field named (a manual override) or the prepare-stage's own large-prompt auto-switch already changed it before the envelope was read. Implement/fix/merge-in CLIs' finalize calls do not take this flag (no `reviewer_model`-equivalent field exists on their side, per this task's earlier confirmed-absent decision).
- **Commit:** `docs(mill-go): document --actual-model threading into review finalize calls (#644)`

## Batch Tests

`verify:` runs `test-review-finalize.py` and `test-review-cli.py` (extend for the audit-trail fix end-to-end: a `--stage finalize` call with `--actual-model <tier>` produces a review file whose `reviewer_model:` line matches the passed tier regardless of what the reviewer echoed; omitting the flag reproduces today's config-derived value unchanged). Card 17's `mill-go/SKILL.md` documentation edit has no runnable surface — verified by direct reading.
