# Batch: full-suite-regression

```yaml
task: 'Unit test suite: hangs, unmocked-path errors, and stuck/success envelope bug found in piecewise sweep'
batch: 'full-suite-regression'
number: 4
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: [1, 2, 3]
```

## Batch Scope

This task's acceptance bar (`_mill/discussion.md` Scope: "Verify by running the full suite via
plain `run-all.py` ... and confirming zero failures/errors/hangs — this is the real regression
check, since the original discovery was that a single hang silently stalls the entire parallel
batch") is not covered by any single earlier batch's own scoped `verify:` — each of batches 1-3
runs only the specific files it touches. This final batch is a single verification-only card,
depending on all three fix batches, that runs the complete, unscoped suite exactly once to confirm
the original discovery symptom (one hanging/erroring file silently stalling or corrupting the whole
parallel batch) no longer reproduces anywhere in the suite.

## Cards

### Card 9: Full-suite regression check

- **Context:** none
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Run the full unit test suite via plain `run-all.py` (default parallel mode, no
  `--only`/`--sequential` flags) from the repo root and confirm it completes with zero failures,
  zero errors, and no hang. If any regression is found, this card does not fix it — a failure here
  means one of batches 1-3 is incomplete or introduced a new regression, and the finding must be
  routed back to the responsible batch rather than patched ad hoc in this verification-only card.
- **Commit:** none

## Batch Tests

This batch's `verify:` command IS the acceptance bar itself: the unbounded, full `run-all.py` run
(no `--only`, no `--sequential`) is intentional here — the entire purpose of this batch is to
execute the complete regression check described in `_mill/discussion.md`'s Scope, not to verify a
narrow code change. This is the one batch in this plan where the default per-batch scoping
guidance (verify only what the batch's own `Edits:`/`Creates:` touch) does not apply, since the
card touches no files at all and exists solely to run this check.
