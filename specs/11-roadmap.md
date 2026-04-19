# Implementation Roadmap — explicit build order

```yaml
status: draft
purpose: unambiguous sequence for building v2, with dependencies and gates
```

## How to read this document

Every step has:
- **ID** (M1.1, M1.2, etc.) for reference
- **Depends on:** which earlier steps must be done
- **Delivers:** what's usable after this step
- **Exit criteria:** how you know it's done

You work strictly in order. You may skip within a milestone if independent parallelism is possible, but you do not jump ahead between milestones.

**Stop gates (⛔)** are points where you stop, review what's built, and decide whether to continue as planned or adjust the spec.

---

## M0 — Decision gates (before writing any code)

```yaml
depends-on: none
delivers: signed-off spec
```

Before writing code, confirm these decisions with yourself:

- [ ] Plan format: cards (placeholder) or bundles (likely). If leaning bundles: update `03-orchestration.md` and `05-formats.md` before implementing Layer 03.
- [ ] Gemini-in-v2.0: yes (per current spec) or deferred. Decides Layer 02 scope.
- [ ] Repo name (settled: `millhouse`). Container path (`C:\Code\millhouse\`).
- [ ] Primary-clone folder name (settled: `hub`).
- [ ] `.millhouse/` layout details (dot-prefix `.active` and `.<slug>.slug.md` — settled).

**Exit:** every checkbox is ticked. If any can't be ticked, update the relevant spec until it can.

⛔ **Gate: don't start M1 until M0 is green.**

---

## Layer 01 — Bootstrap

```yaml
depends-on: M0
delivers: working wiki + tasks list + .millhouse/ infrastructure
loc-budget: 450
```

### M1.1 — Lift v1 primitives

**Depends on:** M0.

Carry over, strip, clean:
- `_subprocess_util.py` (from `millpy/core/subprocess_util.py`)
- `_junction.py` (from `millpy/core/junction.py`, incl. Python 3.10 fallback)
- `_wiki.py` (from `millpy/tasks/wiki.py` — lock + commit/push helpers)
- `_render.py` (new, ~20 LOC — template substitution helper)

**Exit criteria:**
- All four files are in `plugins/mill/scripts/`
- No imports reference `millpy.*`
- Each file runs standalone if `python <file>.py` is called (prints a usage message at minimum)
- Hand-test: create a junction, remove it; acquire wiki lock, release it; render a template

### M1.2 — mill-setup skill

**Depends on:** M1.1.

Write `plugins/mill/skills/mill-setup/SKILL.md`. Also write `plugins/mill/templates/config.local.yaml` and `plugins/mill/templates/Home.md`.

The skill tells Claude to:
1. Detect remote URL, derive wiki URL
2. Clone wiki if missing
3. Create `.millhouse/` + junction + config.local.yaml
4. Initialise Home.md if empty
5. Verify end-to-end

**Exit criteria:**
- Running `/mill-setup` from an empty `hub/` produces a working `.millhouse/` + `wiki/` junction
- Running it a second time is a no-op
- Skill file is under 200 lines

### M1.3 — mill-add script

**Depends on:** M1.2.

Write `plugins/mill/scripts/mill-add.py`. Under ~60 LOC. Uses `_wiki.py` for commit/push.

**Exit criteria:**
- `python plugins/mill/scripts/mill-add.py foo --description "do foo"` appends to Home.md
- Wiki gets commit pushed
- Lock acquired/released

### M1.4 — mill-list script

**Depends on:** M1.2 (just needs wiki).

Write `plugins/mill/scripts/mill-list.py`. Under ~30 LOC.

**Exit criteria:**
- `python plugins/mill/scripts/mill-list.py` prints tasks, one per line

### M1.5 — Layer 01 integration test

**Depends on:** M1.1, M1.2, M1.3, M1.4.

Write `plugins/mill/integration_tests/test-bootstrap.ps1`. Sets up fake wiki in temp dir, runs setup + add + list, checks output.

**Exit criteria:**
- Test passes
- Total Python LOC for Layer 01 is under 450

⛔ **Gate 1: stop here and evaluate.** Can you add/list tasks reliably? If yes, Layer 01 is done. Tag `layer-01-done`. If no, fix before continuing.

---

## Layer 02 — Review

```yaml
depends-on: Layer 01
delivers: mill-review with Claude + Gemini providers
loc-budget: 750
```

### M2.1 — Review CLI skeleton + dispatcher

**Depends on:** Layer 01 done.

Write `plugins/mill/scripts/mill-review.py` — arg parsing, template loading, dispatch stub (no providers yet, just raises NotImplementedError). ~80 LOC.

**Exit criteria:**
- `python plugins/mill/scripts/mill-review.py --type plan --file foo.md --model fake-model` exits 2 (unknown model) with clear error
- Config loading works

### M2.2 — Claude provider (stream-json)

**Depends on:** M2.1.

Write `plugins/mill/scripts/providers/claude.py`. Spawn `claude.exe`, parse stream-json, extract verdict. Handle both tool-use and free-text responses. ~200 LOC.

**Exit criteria:**
- `mill-review --type plan --model sonnet --file sample-plan.md` completes
- Verdict extracted correctly from tool-use response
- Timeout handling works (force a hang, verify wrapper kills it)

### M2.3 — Review-prompt templates

**Depends on:** M2.1.

Lift and clean from `millpy/doc/prompts/plan-review.md`, `code-review.md`, `discussion-review.md`:
- `templates/review-prompt-plan.md`
- `templates/review-prompt-code.md`
- `templates/review-prompt-discussion.md`
- `templates/review-output.md`

Plus schemas (only where validation matters — review-output.md).

**Exit criteria:**
- Each template has clear `<PLACEHOLDER>` tokens
- Substitution via `_render.py` works
- No inline prompts in Python

### M2.4 — Gemini provider (tool-use)

**Depends on:** M2.2 (proves provider pattern works first).

Write `plugins/mill/scripts/providers/gemini.py`. API client, tool-use loop, function declarations for Read/Write. ~250 LOC.

Write `plugins/mill/scripts/providers/_tools.py` — shared tool implementations. ~60 LOC.

**Exit criteria:**
- `mill-review --type discussion --model gemini-3-pro --file sample.md` completes via tool-use
- Agent can Read/Write files via declared tools
- Tool-use loop terminates cleanly (max-turns cap works)

### M2.5 — Layer 02 integration tests

**Depends on:** M2.2 and M2.4.

Three test scripts, one per combo:
- `test-review-plan-claude.ps1`
- `test-review-code-claude.ps1`
- `test-review-discussion-gemini.ps1`

**Exit criteria:**
- All three pass
- Total Python LOC for Layer 02 is under 750

⛔ **Gate 2: stop and evaluate.** Can you review a plan file with Claude AND with Gemini? Do the outputs look useful? Tag `layer-02-done`.

---

## Layer 03 — Orchestration

```yaml
depends-on: Layer 02
delivers: mill-spawn + mill-go (linear execution)
loc-budget: 600
decisions-needed-before-start:
  - plan format (cards vs bundles) finalised
```

⛔ **Gate 2.5 — plan format decision.** Before starting Layer 03, decide: cards or bundles? Update `03-orchestration.md` and `05-formats.md` to reflect the decision before writing code.

### M3.1 — mill-spawn

**Depends on:** Layer 02 done, plan format decided.

Write `plugins/mill/scripts/mill-spawn.py`. ~150 LOC.

Uses `_junction.py` and `_wiki.py`. Creates worktree, branch, `.millhouse/` in the worktree, slug file, initial status.md in wiki.

**Exit criteria:**
- `python plugins/mill/scripts/mill-spawn.py <slug>` creates worktree at `../worktrees/<slug>/`
- `.millhouse/.active` junction, `.<slug>.slug.md` file present in worktree
- `wiki/active/<slug>/status.md` committed with `phase: discussing`

### M3.2 — Implementer provider

**Depends on:** M2.2 (uses same claude.py).

Add `implement()` function to `plugins/mill/scripts/providers/claude.py`. ~80 LOC addition. Same stream-json pattern but with different expectations (working-directory mode, expect commits).

**Exit criteria:**
- Can spawn claude.exe in a worktree with a brief
- Commits made by the agent are captured (via `git log`)
- Stream events are logged to stderr

### M3.3 — mill-go skeleton

**Depends on:** M3.1, M3.2.

Write `plugins/mill/scripts/mill-go.py` — main loop over plan units, spawn implementer per unit, check result files. ~250 LOC.

Initially WITHOUT review loop. Just: spawn, wait, check result.

**Exit criteria:**
- Single-unit plan runs end-to-end
- Status.md updated at phase transitions
- Failure stops execution cleanly

### M3.4 — mill-go review loop

**Depends on:** M3.3.

Add review-loop behaviour: on unit-complete, call `mill-review --type code`, iterate on REQUEST_CHANGES up to max rounds.

**Exit criteria:**
- Two-unit plan where unit 1 passes review runs through
- REQUEST_CHANGES triggers re-spawn with findings
- Max-rounds cap works

### M3.5 — Layer 03 integration tests

**Depends on:** M3.1–M3.4.

- `test-spawn.ps1`
- `test-go-single-unit.ps1`
- `test-go-review-loop.ps1`

**Exit criteria:**
- All pass
- Total Python LOC for Layer 03 is under 600
- Total Python LOC across all layers is under 1500

⛔ **Gate 3: stop and evaluate.** Can you spawn a worktree and run mill-go on a real task (even a trivial one)? Tag `layer-03-done`.

**At this point mill is MINIMUM-VIABLE.** You can spawn tasks and execute them. Layer 04 is polish.

---

## Layer 04 — Remaining skills

```yaml
depends-on: Layer 03
delivers: mill-start, mill-plan, mill-merge, mill-cleanup, mill-status, mill-abandon
loc-budget: 800
```

### M4.1 — mill-status (smallest, useful standalone)

**Depends on:** Layer 03 done.

Write `plugins/mill/scripts/mill-status.py`. ~100 LOC. Lists all worktrees, reads status files, prints table.

**Exit criteria:** With 2-3 worktrees present, prints them in a table. Useful.

### M4.2 — mill-cleanup + mill-abandon

**Depends on:** M4.1.

- `mill-cleanup.py` (~60 LOC) — `git worktree remove` + junction teardown
- `mill-abandon.py` (~80 LOC) — restore task to Home.md, delete active/<slug>/ in wiki

**Exit criteria:** Can cleanup after a failed/completed run. Can abandon a task cleanly.

### M4.3 — mill-start skill

**Depends on:** Layer 03 done.

Write `plugins/mill/skills/mill-start/SKILL.md`. No script needed — the skill writes a brief to scratch and tells the user to start Claude Code in the worktree.

Also: `plugins/mill/templates/discussion-brief.md`.

**Exit criteria:** User can invoke `/mill-start`, get a brief, have a productive discussion, end with `discussion.md` written.

### M4.4 — mill-plan

**Depends on:** M4.3 (needs discussion).

Write `plugins/mill/scripts/mill-plan.py` (~150 LOC) and `plugins/mill/skills/mill-plan/SKILL.md`.

Template: `plugins/mill/templates/planner-brief.md`.

**Exit criteria:** Given a discussion.md, produces a valid plan.md. Review loop works if enabled.

### M4.5 — mill-merge

**Depends on:** M4.1 (needs status-reading).

Write `plugins/mill/scripts/mill-merge.py` (~150 LOC). Git sequence: switch to main in hub, merge --no-ff, push, move wiki state.

**Exit criteria:** Can merge a completed task to main. Wiki updated. Worktree left for user to cleanup.

### M4.6 — Layer 04 integration test

**Depends on:** all of Layer 04.

- `test-full-lifecycle.ps1` — mill-add → mill-spawn → mill-start → mill-plan → mill-go → mill-merge → mill-cleanup

**Exit criteria:**
- Test passes
- Total Python LOC across ALL layers is under 1500

⛔ **Gate 4: mill-v2 is DONE.** Tag `v2.0`.

---

## Cross-cutting milestones (done inline during layers)

### Skills index

Carry over `mill-skills-index/SKILL.md` from v1. Run it after adding each new skill file so `SKILLS.md` stays current. Do this at the end of each layer.

### `.gitignore`

At M1.2 (mill-setup), commit `.gitignore` with:
```
**/.millhouse/
**/.env
**/worktrees/
```

(Worktrees are at the container level, not inside hub, so `**/worktrees/` actually won't match anything inside hub. But worth having defensively.)

### `marketplace.json` and cross-plugin setup

When you set up the new repo structure initially, copy `marketplace.json` from v1 and update paths. Link csharp, python, weblens, codeguide plugins via symlinks or subfolders. Do this as part of M1.2 (setup establishes the repo structure) or earlier.

---

## Estimated effort

Very rough. Assumes CC pair-programs with a disciplined user.

| Milestone | Estimate |
|---|---|
| M0 decisions | 30 min |
| M1 (Bootstrap) | 4–6 hours |
| M2 (Review) | 8–12 hours |
| M3 (Orchestration) | 8–12 hours |
| M4 (Extras) | 6–10 hours |
| **Total** | **26–40 hours** of focused work |

If it takes significantly longer, the discipline rules (LOC budget, no abstractions, no tests beyond integration) are being violated somewhere. Stop and audit.

## When to deviate from the roadmap

You may:
- Swap the order within a layer (e.g. M1.3 before M1.2) if dependencies allow
- Skip a milestone if you discover it's not needed (update spec first)
- Insert a new milestone if you find a missing piece (update spec first)

You may NOT:
- Start a layer before the previous one is tagged done
- Write code that contradicts the spec — fix the spec first, then code
- Skip gates to "come back later"

If you find yourself wanting to skip a gate, stop entirely and reconsider whether the plan needs to change.
