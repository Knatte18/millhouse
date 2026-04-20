# Layer 03 — Orchestration

```yaml
status: draft
depends-on: [layer-01-bootstrap, layer-02-review]
delivers: [mill-spawn, mill-go]
loc-budget: 600
```

## Goal

End-to-end task execution: take a plan, implement each card, optionally review, commit. Linear execution. No DAG, no parallel, no cross-card concurrency.

## Why linear

v1's DAG executor (mill-go v3 per-card spawn) had fundamental reliability problems (issues #40, #49, #52, #58). It tried to solve three things at once:
- Parallel execution
- Context isolation (each card spawns its own agent)
- Fire-and-forget orchestration

Each of those is a separate concern. Doing all three together produced unreliable behaviour. v2 starts with linear-sequential and adds concurrency only if we can prove its value with measurements.

## v1 reuse for this layer

From `C:\Code\millhouse-legacy\plugins\mill\scripts\millpy\`:

| v1 source | v2 target | What to take |
|---|---|---|
| `entrypoints/spawn_task.py` lines 260–330 | `mill-spawn.py` | **Reference** — worktree creation sequence (mkdir, junction, config copy, wiki init, slug file). Rewrite cleanly. |
| `entrypoints/worktree.py` | `mill-spawn.py` | **Reference** — the git worktree add flow, branch creation, parent-branch handling. |
| `core/paths.py::slug_from_branch()` | Inline in `mill-spawn.py` | The branch-prefix stripping logic. ~15 LOC. |
| `core/plan_validator.py` | `scripts/_plan_validator.py` | **Simplify and carry.** v1's plan validator is over-specified for v1's multi-batch format. Trim to v2's single-card-list format. |
| `backends/claude.py` (implementer path) | `providers/claude.py::implement()` | **Reference.** The subprocess spawn with stream-json for implementer. Drop v1's cluster/handler dispatch paths. |
| `reviewers/engine.py` | — | **Do NOT carry.** The dispatch engine is over-engineered. v2's orchestration is 30 lines: loop over cards, spawn, check result. |
| `skills/mill-go/SKILL.md` | `skills/mill-go/SKILL.md` | **Reference for the workflow phases.** Drop the DAG-executor and plan-v2/v3 sections. |

See `ref-v1-reuse.md` for the full lifting protocol.

## Deliverables

### 1. `mill-spawn` — create a worktree for a task

**Arguments:**
```
mill-spawn [<slug>] [--from <base-branch>] [--short <task-short-name>]
```

If `<slug>` is omitted, the script runs in **interactive mode**: reads Home.md, prints all tasks numbered, prompts the user to pick one, optionally prompts for a `short-name` override. This is deliberately kept in the script (not in a separate skill) because "pick from numbered list + optional short" is a mechanical prompt, not judgment-heavy work.

`--short` overrides the auto-derived short-name (which defaults to the first kebab-case segment of the slug, capitalised: `python-skills-improvements` → `Python`). Stored in `.millhouse/.<slug>.slug.md` frontmatter as `short-name:`, used by `_vscode.py::worktree_title()` to build `window.title` as `<repo.short-name>: <task-short-name>`.

User can edit `<worktree>/.vscode/settings.json` directly post-spawn if the auto-derived short is wrong — the file is gitignored and the short-name field in slug.md is a hint, not a binding source.

**Behaviour:**

1. Verify slug exists in `wiki/Home.md`
2. Create branch `<slug>` from `<base-branch>` (default: `main`)
3. Create worktree at `../worktrees/<slug>/` (relative to the primary clone directory; `hub/` in the recommended layout)
4. Inside the new worktree:
   - `mkdir .millhouse/`
   - Create `.millhouse/wiki` junction → `../../../wiki`
   - Copy `config.local.yaml` from hub's `.millhouse/`
   - Write `.millhouse/.<slug>.slug.md` with task title and description
5. Initialise task state in wiki:
   - `mkdir wiki/active/<slug>/`
   - Write `wiki/active/<slug>/status.md` from `templates/status.md`
   - Commit + push
6. Create `.millhouse/.active` junction → `../../wiki/active/<slug>/`
7. **VS Code window colour for the worktree** — call `_vscode.write_settings(color_hex, window_title, worktree/'.vscode/settings.json')`:
   - `color_hex`: a deterministic, non-green colour picked per slug (see "Colour pick" below)
   - `window_title`: `<short-name>: <slug>` — example: `millhouse: refactor-parser`. Deliberately short — must read clearly in the Windows 11 taskbar at small sizes. No `${activeEditorShort}` or other VS Code variables.

   The worktree directory is freshly created in step 3, so no existing `.vscode/settings.json` exists — write unconditionally. (mill-setup, the skill, handles the existing-file judgment for the hub; mill-spawn, the script, has no such case.)

8. Print worktree path to stdout

**Colour pick:** ~20 LOC inline in `mill-spawn.py`. Fixed palette of ~10 distinct colours (excluding `#2d7d46` which is reserved for the hub). Pick deterministically by hashing the slug — same slug always gets the same colour, so re-spawning a worktree on another machine matches the colour the operator already mentally associates with it. The "main = green" invariant is preserved by both ends: `mill-setup` always writes green for the hub, `mill-spawn` excludes green from the palette.

**Helper used:** `plugins/mill/scripts/_vscode.py` (`render_settings`, `write_settings`) — same helper that `mill-setup` uses in M1.2's Phase 7. Lifted into a shared module precisely so that the rendering+writing of `.vscode/settings.json` is in one place.

**Exit codes:** 0 success, 1 slug not found in tasks, 2 branch already exists

### 2. `mill-go` — execute a plan

**Arguments:**
```
mill-go [--max-review-rounds N]  # default 1
```

Invoked from inside a worktree directory. Reads plan from `.millhouse/.active/plan.md` (symlinked location).

**Behaviour (linear):**

```
for each card in plan (in order):
  spawn implementer with card brief
  wait for completion
  check card result file
  if result.md has PASS:
    if code-review configured:
      for round in 1..max_review_rounds:
        call mill-review --type code --file <diff>
        if verdict == APPROVE:
          break
        else:
          re-spawn implementer with findings as input
    continue to next card
  else:
    mark status failed, exit with error
```

**Implementer invocation:**

Same pattern as `providers/claude.py` from Layer 02, but for implementation instead of review:
- Spawn Claude CLI with a materialised brief
- Stream-json parsing
- Expect `result.md` written by the agent (or parsed from text)
- Capture the agent's commits on the worktree branch (read via `git log`)

### 3. Implementer provider

**File:** `providers/claude-implementer.py` (or merge into `providers/claude.py` with different function)

**Function signature:**
```python
def implement(brief: str, model: str, effort: str | None, working_dir: Path) -> ImplementResult:
    ...
```

Different from `review()` because:
- Agent is expected to make changes to the working tree
- Result is measured by commits produced + a summary file
- Working directory matters (agent runs from the worktree)

Keep the two functions in the same file if provider logic is shared. Otherwise separate.

### 4. Brief templates

```
plugins/mill/templates/
  implementer-brief.md        (canonical brief shape)
  implementer-brief.schema.md
```

Brief includes:
- Task title + description
- Plan card content (what to build)
- `Reads:` list (files to read first)
- `Modifies:` list (expected files to change)
- `Verify:` command (test script to run)
- `Commit:` message hint

Substitution uses the same helper from Layer 02.

## File layout

```
plugins/mill/
  scripts/
    mill-spawn.py            ← ~150 LOC
    mill-go.py               ← ~250 LOC (main loop + error handling)
  providers/
    claude.py                ← grows slightly (implement() added)
  templates/
    implementer-brief.md
    status.md
    plan.md                  ← canonical plan format
    (schemas for each)
  skills/
    mill-spawn/SKILL.md
    mill-go/SKILL.md
  integration_tests/
    test-spawn.ps1
    test-go-single-card.ps1  ← one-card plan, full flow
    test-go-review-loop.ps1  ← card that fails first review, passes second
```

## Plan format — TENTATIVE, redesigned at Layer 03 build-time

**Status:** The layout below (card-per-step) is a placeholder. The actual unit for v2 is likely **bundles/bolker** — larger scoped groups of changes that a single implementer session handles together, with bundle-scoped tests.

**Why cards may not survive:**

v1's per-card spawning was expensive because each spawn required full context re-ingestion (read codebase, understand conventions, etc.). A plan with 25 cards spawned 25 Sonnet sessions, each paying that context tax.

Bundles amortise the context cost: one Sonnet session handles multiple related changes in one go, running its own bundle-scoped tests, committing coherent chunks. The orchestrator still runs linearly over bundles — just fewer, bigger units.

**This will be redesigned when Layer 03 is built.** The rest of this file uses "card" as the placeholder term; read "card" as "one executable unit in the plan" regardless of which format wins.

---

## Plan format (placeholder — cards per step)

Single flat file: `.millhouse/.active/plan.md` (which is `<wiki>/active/<slug>/plan.md` via junction).

```markdown
---
task: <slug>
created: <iso-8601>
---

# Plan

## Card 1: <title>

**Reads:** path/a, path/b
**Modifies:** path/c
**Verify:** pytest tests/test_c.py
**Commit:** fix: add c

<implementation notes>

## Card 2: <title>

...
```

No batches, no layers, no DAG. One list of cards, executed in order. If a task needs more structure, write a better plan; don't add format features.

## Acceptance criteria

After this layer ships:

1. `mill-spawn fix-bug` from the primary clone creates a worktree at `../worktrees/fix-bug/` with status.md initialised in wiki
2. `mill-go` from inside that worktree reads a plan, executes its single card, commits result
3. If code-review is configured: `mill-go` runs `mill-review` after the card, re-spawns implementer on REQUEST_CHANGES (up to N rounds)
4. Status.md is updated at each phase transition (implementing → reviewing → done)
5. If the plan has 3 cards, they execute sequentially; failure on card 2 stops execution and leaves card 1 committed

## Design decisions locked

- **One plan per task, no batches.** The v1 batch/overview/cards split added complexity. One flat plan is enough.
- **Linear execution only.** Add parallelism later if measured to help.
- **Agent writes result file via Write tool.** Free-text fallback is used for verdicts but the contract is: the agent writes `cards/<n>-result.md` as part of its work.
- **Orchestrator does not read agent stdout.** It reads result files. Prevents context bloat in the orchestrator.
- **Review is optional per invocation.** `--max-review-rounds 0` skips review entirely. Default is 1 round, not 3.

## Non-goals for Layer 03

- DAG parallelism
- Plan format v2 (batches, overview, dependencies)
- Fire-and-forget spawning with notifications
- Resumable orchestration mid-card
- Rollback on failure (Layer 04 or later, if ever)

## Open questions

- [ ] When review says REQUEST_CHANGES, the implementer is re-spawned with findings. Does it re-start from the original brief + findings, or continue from its previous state? (Simplest: fresh session + original brief + findings appended)
- [ ] If the implementer produces no commits (agent decided no changes needed), is that a pass or a failure? Probably pass with a warning.
- [ ] How are implementer timeouts handled? Hard kill after some duration (30 min default?), or let it run?
