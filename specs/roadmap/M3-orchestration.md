# Layer 03 — Orchestration

```yaml
depends-on: Layer 02
delivers: mill-spawn + mill-go (linear execution)
loc-budget: 600
status: not started
decisions-needed-before-start:
  - plan format (cards vs bundles) finalised
```

End-to-end task execution: take a plan, implement each unit, optionally review, commit. Linear execution. No DAG, no parallel, no cross-card concurrency.

**Full layer spec (v1 reuse, deliverables, design decisions, acceptance criteria):** [../layer-03-orchestration.md](../layer-03-orchestration.md). Read it before starting any milestone below.

⛔ **Gate 2.5 — plan format decision.** Before starting Layer 03, decide: cards or bundles? Update `layer-03-orchestration.md` and `ref-formats.md` to reflect the decision before writing code.

- [ ] Plan-format decision made and specs updated

## Progress

| ID | Milestone | Status |
|---|---|---|
| M3.1 | `mill-spawn` | [ ] not started |
| M3.2 | Implementer provider | [ ] not started |
| M3.3 | `mill-go` skeleton | [ ] not started |
| M3.4 | `mill-go` review loop | [ ] not started |
| M3.5 | Layer 03 integration tests | [ ] not started |

---

## M3.1 — mill-spawn

**Depends on:** Layer 02 done, plan format decided.

Write `plugins/mill/scripts/mill-spawn.py`. ~150 LOC.

Uses `_junction.py` and `_wiki.py`. Creates worktree, branch, `.millhouse/` in the worktree, slug file, initial status.md in wiki.

### Exit criteria

- [ ] `python plugins/mill/scripts/mill-spawn.py <slug>` creates worktree at `../worktrees/<slug>/`
- [ ] `.millhouse/.active` junction, `.<slug>.slug.md` file present in worktree
- [ ] `wiki/active/<slug>/status.md` committed with `phase: discussing`

---

## M3.2 — Implementer provider

**Depends on:** M2.2 (uses same `claude.py`).

Add `implement()` function to `plugins/mill/scripts/providers/claude.py`. ~80 LOC addition. Same stream-json pattern but with different expectations (working-directory mode, expect commits).

### Exit criteria

- [ ] Can spawn `claude.exe` in a worktree with a brief
- [ ] Commits made by the agent are captured (via `git log`)
- [ ] Stream events are logged to stderr

---

## M3.3 — mill-go skeleton

**Depends on:** M3.1, M3.2.

Write `plugins/mill/scripts/mill-go.py` — main loop over plan units, spawn implementer per unit, check result files. ~250 LOC.

Initially WITHOUT review loop. Just: spawn, wait, check result.

### Exit criteria

- [ ] Single-unit plan runs end-to-end
- [ ] status.md updated at phase transitions
- [ ] Failure stops execution cleanly

---

## M3.4 — mill-go review loop

**Depends on:** M3.3.

Add review-loop behaviour: on unit-complete, call `mill-review --type code`, iterate on `REQUEST_CHANGES` up to max rounds.

### Exit criteria

- [ ] Two-unit plan where unit 1 passes review runs through
- [ ] `REQUEST_CHANGES` triggers re-spawn with findings
- [ ] Max-rounds cap works

---

## M3.5 — Layer 03 integration tests

**Depends on:** M3.1–M3.4.

- [ ] `test-spawn.ps1`
- [ ] `test-go-single-unit.ps1`
- [ ] `test-go-review-loop.ps1`

### Exit criteria

- [ ] All pass
- [ ] Total Python LOC for Layer 03 is under 600
- [ ] Total Python LOC across all layers is under 1500

⛔ **Gate 3:** stop and evaluate. Can you spawn a worktree and run `mill-go` on a real task (even a trivial one)? Tag `layer-03-done`.

**At this point mill is MINIMUM-VIABLE.** You can spawn tasks and execute them. Layer 04 is polish.
