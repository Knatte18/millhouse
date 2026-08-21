# Batch: entry-gate-discussion-phases

```yaml
task: 'mill-go-base/mill-merge: documented step behavior diverges from underlying script capability'
batch: entry-gate-discussion-phases
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-phase-wait.py
depends-on: [1]
```

## Batch Scope

Implements #873: `mill-go-base/SKILL.md`'s Entry phase table and its "Entry-gate wait for upstream
mill-plan" `_phase_wait.matches_wait_trigger` call are widened to also recognize mill-start's
`discussion-fix-r{N}` / `discussion-gap-fix-r{N}` phases as "still waiting on upstream", instead of
falling through to the generic any-other-phase halt. One batch because both cards touch the same
file/section and are trivially small; depends on batch 1 (`detached-head-branch-detection`) only
because that batch also edits `mill-go-base/SKILL.md` (a different, unrelated section — Entry Step
1's halt handler, not the Entry phase table) — the dependency exists purely to give both edits a
stable, non-conflicting sequential base in the same file, not because of any functional
relationship between the two changes.

No external interface — this batch only widens two literal pattern lists already embedded in
`mill-go-base/SKILL.md`'s prose; `_phase_wait.matches_wait_trigger` itself is untouched (it is
already fully generic and already handles arbitrary regex patterns correctly, confirmed via its
existing test coverage in `test-phase-wait.py`).

## Cards

### Card 10: widen the Entry-gate wait for `discussion-fix-r{N}` / `discussion-gap-fix-r{N}`

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Make three coordinated edits to `mill-go-base/SKILL.md`, all widening the same
  logical trigger set — leaving any one out would desynchronize the table's classification from the
  wait procedure's own re-check: (1) In the Entry
  phase table row (currently line 119, reading: `` `discussed` / `discussing` / `planning`, or
  matching `^plan-review-r\d+$` / `^plan-fix-r\d+$` `` ), extend the matched-pattern text to also
  list `^discussion-fix-r\d+$` and `^discussion-gap-fix-r\d+$` alongside the two existing
  `plan-review`/`plan-fix` patterns — the row's action column (wait for `phase: planned`, per
  `pipeline.entry_wait`) is unchanged. (2) In the "Entry-gate wait for upstream mill-plan" section's
  opening prose sentence (currently line 161: "Whenever the phase-table lookup above lands on the
  widened `discussed`/`discussing`/`planning`/`plan-review-r{N}`/`plan-fix-r{N}` row, run this
  procedure instead of jumping straight to its listed action:"), extend the named phase list to also
  include `discussion-fix-r{N}` and `discussion-gap-fix-r{N}`. (3) In the `matches_wait_trigger` call
  (currently lines 171-173: `` matches_wait_trigger(phase, {"discussed", "discussing", "planning"},
  [r"^plan-review-r\d+$", r"^plan-fix-r\d+$"]) `` ), add `r"^discussion-fix-r\d+$"` and
  `r"^discussion-gap-fix-r\d+$"` to the regex-patterns list (the third positional argument), so it
  reads `[r"^plan-review-r\d+$", r"^plan-fix-r\d+$", r"^discussion-fix-r\d+$",
  r"^discussion-gap-fix-r\d+$"]`. Do not change the exact-match set `{"discussed", "discussing",
  "planning"}` in any of the three edits — only the regex-pattern lists and their prose
  descriptions gain the two new entries.
- **Commit:** `docs(mill-go-base): widen entry-gate wait to cover mill-start's discussion-fix-rN/discussion-gap-fix-rN (#873)`

### Card 11: regression-test the two new patterns against `matches_wait_trigger`

- **Context:**
  - `plugins/mill/scripts/_phase_wait.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-phase-wait.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new test case to `plugins/mill/unit_tests/test-phase-wait.py`, following
  the existing style of the "Case 9: matches_wait_trigger — regex full-match" block (currently
  around lines 82-93) — this doesn't test any changed code in `_phase_wait.py` itself (untouched by
  this batch), but documents/regression-guards the exact pattern set `mill-go-base/SKILL.md`'s Entry
  phase table now embeds (card 10), catching a typo in that markdown text (which no test otherwise
  exercises, since markdown prose isn't executed). Assert
  `matches_wait_trigger("discussion-fix-r3", {"discussed", "discussing", "planning"},
  [r"^plan-review-r\d+$", r"^plan-fix-r\d+$", r"^discussion-fix-r\d+$",
  r"^discussion-gap-fix-r\d+$"])` is `True`, and the same for
  `matches_wait_trigger("discussion-gap-fix-r12", ...)` with the identical pattern-set arguments.
  Also assert a value the widened set must still reject, e.g.
  `not matches_wait_trigger("discussion-fixed-r3", ...)` (a near-miss string that must not
  accidentally match `^discussion-fix-r\d+$`), mirroring the existing "Case 12: no accidental prefix
  widening" test's spirit (currently around lines 112-116).
- **Commit:** `test(phase-wait): regression-guard mill-go-base's widened discussion-fix-rN/discussion-gap-fix-rN patterns (#873)`

## Batch Tests

`verify:` runs `test-phase-wait.py` via `run-all.py --only` — the only test file this batch's card
11 edits. Card 10 edits SKILL.md prose only, with no automated test harness of its own (mill's
prose-driven orchestration steps are not executable code); card 11's regression test is the closest
automated guard available for the exact regex text card 10 embeds in that prose.
