# Batch: mill-pause-agent-dispatch

```yaml
task: "mill-go: done-gate halt path and cleanliness-gate recovery are under-documented"
batch: "mill-pause-agent-dispatch"
number: 5
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Adds an explicit third case to `mill-pause/SKILL.md`'s "When invoked" section for an in-flight Agent-mode dispatch (implementer/reviewer/fixer), closing the gap #962 reported: the two existing documented cases (`millpy-bg` poll in progress / no poll in progress) have no match for Agent-mode dispatch, which is now the default, so an operator's `/mill-pause` wrongly `TaskStop`s a running reviewer and loses an unresumable round. Independent of every other batch — a standalone file, touched nowhere else in this plan.

## Cards

### Card 9: Add the in-flight Agent-mode dispatch case to mill-pause

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-pause/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## When invoked` section, add a third bullet after the existing "**If no poll is in progress**" bullet: "**If an Agent-mode dispatch (implementer/reviewer/fixer) is in flight:** wait for its `<task-notification>` to arrive, then run the CLI's `--stage finalize` call so the round is correctly recorded in status.md/reviews, then stop cleanly — do not dispatch the next round or batch. Calling `TaskStop` on a running Agent-mode dispatch is **forbidden**: the round is not resumable from a kill, and `discover_round` would just re-run it from scratch on the next `/mill-go` or `/mill-plan`, silently discarding the in-flight work." Do not alter the two existing bullets ("If a `millpy-bg` poll is in progress" / "If no poll is in progress") or the "## On stopping" section below — this card only adds the new third case.
- **Commit:** `docs(mill-pause): add in-flight Agent-mode dispatch case, forbid TaskStop`

## Batch Tests

`verify: null` — this batch edits only `mill-pause/SKILL.md`, an orchestrator-prose skill file with no runnable Python surface. Per `_mill/discussion.md`'s Testing section, this prose addition is verified via holistic-review scrutiny of the new bullet's wording (is the "never TaskStop" prohibition unambiguous) rather than an automated test.
