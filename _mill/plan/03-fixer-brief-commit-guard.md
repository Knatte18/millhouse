# Batch: fixer-brief-commit-guard

```yaml
task: "Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode"
batch: "fixer-brief-commit-guard"
number: 3
cards: 2
verify: null
depends-on: []
```

## Batch Scope

This batch delivers the #575 fix: add the missing pre-report commit self-check, real-commit `commit_sha` guard, and new-test-required line to both fixer brief templates, mirroring the discipline the implementer brief already carries. It is independent of the #574 work (no code, no shared files) and is a root batch. Both files are prose templates rendered by `millpy-fix.py`; the change does not introduce or remove any `<TOKEN>`, so no render-site change is needed.

## Cards

### Card 9: Add commit self-check and guards to the per-batch fixer brief

- **Context:**
  - `plugins/mill/templates/implementer-brief.md`
- **Edits:**
  - `plugins/mill/templates/fixer-batch-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `fixer-batch-brief.md`, add to the `## Report` section (mirroring `implementer-brief.md`'s "Pre-report self-check" at line ~87 and the "commit_sha MUST be a real content commit" guard at line ~98): (a) a mandatory pre-report self-check instructing the fixer to record `git -C <PROJECT_ROOT> rev-parse HEAD` at the very start of its session (before any edit) as the baseline — this baseline is the current round's housekeeping commit — and before reporting `success` confirm HEAD now differs from that recorded baseline; never report `success` when HEAD equals the baseline (no commit made); (b) a line: "`commit_sha` MUST be a real new content commit distinct from the fix-round housekeeping commit; a fixer that made edits but did not commit must report `status: stuck` (`stuck_type: logic`) instead"; (c) a line requiring that when a finding mandates a NEW test, the fixer MUST add that test and confirm it runs — do not report success having skipped a required new test. Do not add or rename any `<TOKEN>`; use the existing `<PROJECT_ROOT>` and `<SESSION_ID>` spellings. Keep all existing sections.
- **Commit:** `fix(brief): require commit self-check in per-batch fixer brief`

### Card 10: Add commit self-check and guards to the holistic fixer brief

- **Context:**
  - `plugins/mill/templates/implementer-brief.md`
  - `plugins/mill/templates/fixer-batch-brief.md`
- **Edits:**
  - `plugins/mill/templates/fixer-holistic-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Apply the same three additions as Card 9 to `fixer-holistic-brief.md`'s `## Report` section, with the baseline self-check referencing the holistic housekeeping commit (message starts with `mill-go: holistic fix`). Keep the wording consistent with Card 9 (record HEAD at session start as the baseline; confirm HEAD differs before reporting success; `commit_sha` must be a real new commit; a finding mandating a new test must be satisfied by adding and running that test). Do not add or rename any `<TOKEN>`. Keep all existing sections.
- **Commit:** `fix(brief): require commit self-check in holistic fixer brief`

## Batch Tests

`verify: null` — both edited files are prose brief templates with no runnable surface. Per the discussion's `fixer-brief-commit-guard` decision, brief prose is not unit-tested; the change is validated by plan/code review reading the rendered guidance. The existing finalize gate (`HEAD == start_sha` -> `stuck_type: logic`, unchanged in this task) remains the mechanical safety net that catches a false-success at runtime; this batch prevents the false self-report upstream of it.
