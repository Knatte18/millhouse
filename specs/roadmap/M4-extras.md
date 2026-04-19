# Layer 04 — Remaining skills

```yaml
depends-on: Layer 03
delivers: mill-start, mill-plan, mill-merge, mill-cleanup, mill-status, mill-abandon, mill-groom
loc-budget: 900
status: not started
```

Round out the workflow: bookend skills (start a task, write a plan, merge the result, clean up).

**Full layer spec (v1 reuse, deliverables, design decisions, acceptance criteria):** [../layer-04-extras.md](../layer-04-extras.md). Read it before starting any milestone below.

## Progress

| ID | Milestone | Status |
|---|---|---|
| M4.1 | `mill-status` (smallest, useful standalone) | [ ] not started |
| M4.2 | `mill-cleanup` + `mill-abandon` | [ ] not started |
| M4.3 | `mill-start` skill | [ ] not started |
| M4.4 | `mill-plan` | [ ] not started |
| M4.5 | `mill-merge` | [ ] not started |
| M4.6 | Layer 04 integration test | [ ] not started |

---

## M4.1 — mill-status (smallest, useful standalone)

**Depends on:** Layer 03 done.

Write `plugins/mill/scripts/mill-status.py`. ~100 LOC. Lists all worktrees, reads status files, prints table.

### Exit criteria

- [ ] With 2–3 worktrees present, prints them in a table. Useful.

---

## M4.2 — mill-cleanup + mill-abandon

**Depends on:** M4.1.

- [ ] `mill-cleanup.py` (~60 LOC) — `git worktree remove` + junction teardown
- [ ] `mill-abandon.py` (~80 LOC) — restore task to Home.md, delete `active/<slug>/` in wiki

### Exit criteria

- [ ] Can cleanup after a failed/completed run
- [ ] Can abandon a task cleanly

---

## M4.3 — mill-start skill

**Depends on:** Layer 03 done.

Write `plugins/mill/skills/mill-start/SKILL.md`. No script needed — the skill writes a brief to scratch and tells the user to start Claude Code in the worktree.

Also: `plugins/mill/templates/discussion-brief.md`.

### Exit criteria

- [ ] User can invoke `/mill-start`, get a brief, have a productive discussion, end with `discussion.md` written

---

## M4.4 — mill-plan

**Depends on:** M4.3 (needs discussion).

Write `plugins/mill/scripts/mill-plan.py` (~150 LOC) and `plugins/mill/skills/mill-plan/SKILL.md`.

Template: `plugins/mill/templates/planner-brief.md`.

### Exit criteria

- [ ] Given a `discussion.md`, produces a valid `plan.md`
- [ ] Review loop works if enabled

---

## M4.5 — mill-merge

**Depends on:** M4.1 (needs status-reading).

Write `plugins/mill/scripts/mill-merge.py` (~150 LOC). Git sequence: switch to main in hub, merge --no-ff, push, move wiki state.

### Exit criteria

- [ ] Can merge a completed task to main
- [ ] Wiki updated
- [ ] Worktree left for user to cleanup

---

## M4.6 — Layer 04 integration test

**Depends on:** all of Layer 04.

- [ ] `test-full-lifecycle.ps1` — `mill-add` → `mill-spawn` → `mill-start` → `mill-plan` → `mill-go` → `mill-merge` → `mill-cleanup`

### Exit criteria

- [ ] Test passes
- [ ] Total Python LOC across ALL layers is under 1500

⛔ **Gate 4:** mill-v2 is DONE. Tag `v2.0`.
