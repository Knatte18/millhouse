# Plan: Monitor tool: persistent:true doesn''t exist, entry-gate waits break

```yaml
task: 'Monitor tool: persistent:true doesn''''t exist, entry-gate waits break'
slug: mill-monitor-persistent-true-unsupported
approved: true
started: 20260921-150808
parent: main
root: ""
verify: null
discussion_sha: 748118a2c99ed5dbe92f7a05431e3586299aae56
```

## Batch Index

```yaml
batches:
  - number: 1
    name: entry-gate-wait-expiry-branch
    file: 01-entry-gate-wait-expiry-branch.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: keep `persistent: true`, add a defensive fourth outcome branch instead of reverting

- **Decision:** All three edits in this plan (mill-plan/SKILL.md, mill-go-base/SKILL.md,
  harness-tool-contracts.md) preserve the existing `Monitor(command=cmd, persistent: true, ...)` call
  as the primary mechanism. None of them remove `persistent: true` or restructure the wait around a
  bounded `timeout_ms` + mandatory re-arm loop as the normal path. Each of the two entry-gate wait
  sections instead gains one new sibling bullet recording a wall-clock `wait_started_epoch`, and one
  new sibling sub-bullet under "Branch on the `<event>` content:" that re-arms the wait — recomputing
  the remaining budget from elapsed wall-clock time — only if a notification ever arrives that is
  neither `READY` nor `TIMEOUT after ...`.
- **Rationale:** see `_mill/discussion.md`'s "Keep `persistent: true`, do not revert to a bounded
  re-arm loop as the primary mechanism" and "Add a fourth documented outcome: unexpected/early expiry,
  with re-arm" Decisions — this plan implements those two Decisions verbatim, in the exact scope
  `_mill/discussion.md`'s Scope section defines.
- **Applies to:** all batches (this plan has exactly one batch).

### Decision: single batch, no `verify:`

- **Decision:** This plan has one batch with `verify: null` at both the batch and module-wide level.
- **Rationale:** All three edits are markdown prose in `SKILL.md`/`docs/*.md` files — no Python source
  changes, no new or altered test surface. `plugins/mill/unit_tests/test-phase-wait.py` (the one test
  file that references "Entry-gate wait" text) exercises `_phase_wait.py`'s `build_wait_command`/
  `matches_wait_trigger` functions directly, never the SKILL.md prose itself — confirmed by reading
  that test file during discussion — so nothing in this plan's scope has runnable test coverage to
  point a `verify:` command at. Correctness here is a careful read-through (see the batch's own
  `## Batch Tests` section), not an automated run.
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/docs/harness-tool-contracts.md`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
