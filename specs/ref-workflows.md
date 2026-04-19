# Key Workflows — how mill-start / mill-plan / mill-go work from the user's perspective

```yaml
status: draft
depends-on: [layer-01-bootstrap, layer-02-review, layer-03-orchestration, layer-04-extras]
```

## Purpose

The layer specs describe what each component delivers. This file describes how a user actually uses mill — the full journey from adding a task to merging the result. It's the contract between "what you run" and "what happens".

## The lifecycle

```
mill-add      → creates task in wiki
mill-spawn    → creates worktree + branch + status.md
mill-start    → discussion phase (Claude explores, discusses approach)
mill-plan     → planning phase (Claude writes plan, optionally reviewed)
mill-go       → execution phase (Claude implements cards)
mill-merge    → merges to main, moves task to archive
mill-cleanup  → removes worktree (optional, can be deferred)
```

Each step is a separate command. The user decides when to proceed. Claude does NOT auto-advance between phases.

---

## mill-start — Discussion phase

### What the user does

```powershell
cd C:\Code\millhouse\worktrees\my-task
# (you're now in the worktree, on branch: my-task)
```

Then invoke the skill. In Claude Code:
```
/mill-start
```

Or directly:
```
python plugins/mill/scripts/mill-start.py
```

### What happens

1. **Script checks state:** Confirms worktree is on a task branch, reads `.millhouse/.my-task.slug.md` for task title/description, reads `wiki/active/my-task/status.md` for current phase.

2. **If phase is already past discussing:** warn, offer to continue or re-do.

3. **Writes a discussion brief** (materialised from `plugins/mill/templates/discussion-brief.md`) to `.millhouse/scratch/discussion-brief.md`. The brief tells Claude:
   - What the task is
   - Where the codebase lives
   - To write findings to `.millhouse/.active/discussion.md`
   - To discuss openly with the user — this is not autonomous

4. **User invokes Claude themselves.** The script prints:
   ```
   Discussion brief written to .millhouse/scratch/discussion-brief.md
   Start a Claude Code session in this worktree and read that file to begin.
   ```

   This is deliberate. `mill-start` does NOT spawn a Claude subprocess. The discussion is an interactive session between the USER and Claude, in the user's own Claude Code window.

5. **Claude (interactively):**
   - Reads the brief
   - Explores codebase (Glob, Grep, Read)
   - Asks clarifying questions to the user
   - Discusses approach options
   - Writes `.millhouse/.active/discussion.md` as the session progresses

6. **User ends the discussion** when they're satisfied. Tells Claude: "write final discussion and stop". Claude finalises `discussion.md`.

7. **User commits wiki side-effects:**
   ```powershell
   python plugins/mill/scripts/mill-status.py --phase planning
   ```
   This updates `status.md` and commits/pushes the wiki state.

### Why not autonomous

Discussion is where most value gets lost if it's autonomous. You want to push back on Claude's first instincts, bring domain knowledge, correct wrong assumptions. Automated discussion produces plausible-but-wrong plans.

### What Claude has access to

Full Claude Code toolset: Read, Write, Edit, Glob, Grep, Bash. Can explore the entire codebase. Can run tests if useful for investigation.

---

## mill-plan — Planning phase

### What the user does

```powershell
/mill-plan
# or
python plugins/mill/scripts/mill-plan.py [--max-review-rounds 1]
```

### What happens

1. **Script checks state:** Confirms `wiki/active/my-task/discussion.md` exists. Phase must be `planning` or later (discussion complete).

2. **Writes a planner brief** (from `plugins/mill/templates/planner-brief.md`) to `.millhouse/scratch/planner-brief.md`. Brief tells Claude:
   - Read `discussion.md` as authoritative input
   - Write plan to `wiki/active/my-task/plan.md` following `plan.schema.md`
   - One flat card list (no batches, no DAG)
   - Specific cards with Reads/Modifies/Verify/Commit fields

3. **Unlike mill-start, mill-plan CAN be autonomous** — the user has already decided approach during discussion. Planning is structured transcription.

4. **Script offers two modes:**
   - **Interactive:** prints brief path, user invokes Claude themselves (same as mill-start)
   - **Headless:** spawns a Claude subprocess (via `providers/claude.py::implement()`), waits for completion, reads the written plan
   
   Default is interactive for first use, but headless becomes attractive when you trust the flow.

5. **After plan is written:** script runs format validator against `plan.schema.md`. If violations: reports them, offers to re-run.

6. **Review loop (optional):**
   - If `--max-review-rounds > 0`: calls `mill-review --type plan --file wiki/active/my-task/plan.md`
   - On REQUEST_CHANGES: prints findings, user decides whether to iterate (no auto-retry — explicit)
   - On APPROVE: marks plan approved in frontmatter

7. **Commits plan to wiki.** Updates `status.md` to `phase: planned`.

### What Claude has access to

- Read (discussion.md, any source file)
- Write (plan.md only — enforced by validator after the fact, not by tool permissions)
- Grep/Glob for codebase exploration

---

## mill-go — Execution phase

### What the user does

```powershell
/mill-go
# or
python plugins/mill/scripts/mill-go.py [--max-review-rounds 1]
```

### What happens

This is where the mill-v2 architecture differs most from v1. **mill-go runs linearly — no DAG, no parallelism.**

1. **Script reads plan** from `wiki/active/my-task/plan.md`. Validates format.

2. **For each card in order:**

   a. **Materialise implementer brief** from `plugins/mill/templates/implementer-brief.md`. Brief contains:
      - Task + card content (copied from plan)
      - Reads, Modifies, Verify, Commit hints
      - Output contract: "write `wiki/active/my-task/cards/card-N-result.md` with `status: PASS | FAIL`"

   b. **Spawn implementer subprocess** (`providers/claude.py::implement()`):
      - `claude.exe -p "<brief>" --output-format stream-json --model <implementer-model>`
      - Working directory is the worktree
      - Claude has full tool access (it's a full CC session in subprocess form)
      - Stream events are logged to stderr so user can watch progress
      - Times out after 30 min by default

   c. **Wait for completion.** Orchestrator does NOT read agent output beyond stream parsing — it reads the RESULT FILE (`cards/card-N-result.md`) once the subprocess exits.

   d. **Check result:**
      - `status: PASS` → proceed to review (if configured)
      - `status: FAIL` → stop entire run, mark status.md failed, exit

   e. **Optional review loop:**
      - If code-review configured: call `mill-review --type code --file <card-N-diff>`
      - On APPROVE: proceed to next card
      - On REQUEST_CHANGES: re-spawn implementer with findings appended to brief. Up to `--max-review-rounds` attempts.
      - After max rounds without APPROVE: stop, mark failed, exit

   f. **Update status.md** with card completion timestamp.

3. **After all cards pass:** update `status.md` to `phase: done`. Print summary. Exit 0.

### What the user sees

```
[mill-go] Plan has 3 cards. Starting linear execution.
[card 1/3] Spawning implementer...
  [stream] reading plan.md
  [stream] reading src/foo.py
  [stream] writing src/foo.py
  [stream] running: pytest tests/test_foo.py
  [stream] all tests pass
[card 1/3] PASS (took 4m 12s, 2 commits)
[card 2/3] Spawning implementer...
...
```

User can interrupt with Ctrl-C. The orchestrator handles cleanup (kill subprocess, mark status).

### Why linear

v1's DAG orchestrator accumulated thread output in the orchestrator's context, hit context overflow on 25-card plans, and had race conditions between cards that were supposedly independent. Linear execution is slower but predictable. If you want parallel, run multiple `mill-go` in different worktrees.

### What Claude (implementer) has access to

Full tool access: Read, Write, Edit, Glob, Grep, Bash, WebFetch. The implementer is a full Claude Code session in subprocess form. It can run tests, commit, push, read/write any file in the worktree.

Not accessible:
- The wiki (implementer doesn't need to touch wiki — orchestrator updates status.md)
- Other worktrees
- The primary clone (`hub/`)

---

## Orchestration patterns across the skills

| Skill | Runs as | Claude's role | User's role |
|---|---|---|---|
| mill-add | Thin script | — | Provides task slug/description |
| mill-spawn | Thin script | — | Gets a new worktree to cd into |
| mill-start | Brief-generator → **interactive Claude session** | Explorer + discussant | Active participant |
| mill-plan | Brief-generator → interactive OR subprocess | Transcriber + structurer | Reviews output |
| mill-go | **Orchestrator** → spawns N implementer subprocesses | Each subprocess: autonomous implementer | Watches + intervenes on failure |
| mill-review | Subprocess spawner | Subprocess: independent reviewer | Reads verdict |
| mill-merge | Git wrapper | — | Confirms |

### The two modes of Claude invocation

**Mode A: Interactive (user's own CC session)**
- User runs script → script writes brief → script tells user to open CC
- Claude runs in the user's main window, full interaction
- Good for: discussion, complex planning, anything requiring pushback

**Mode B: Subprocess (orchestrator spawns)**
- Script runs → script spawns `claude.exe -p ...` → waits for result
- No user interaction during the run; user can only monitor stream
- Good for: execution, review — well-defined scope, deterministic outcome

The split is deliberate. Mode A keeps the human in the loop for judgment-heavy tasks. Mode B runs off to complete well-defined work without context pollution.

### How state flows through the lifecycle

```
mill-add    → wiki/Home.md
mill-spawn  → wiki/active/<slug>/status.md (phase: discussing)
              .millhouse/.<slug>.slug.md
mill-start  → wiki/active/<slug>/discussion.md
mill-plan   → wiki/active/<slug>/plan.md
mill-go     → wiki/active/<slug>/cards/card-N-result.md (one per card)
              + commits on worktree branch
mill-merge  → wiki/active/<slug>/ → wiki/archive/<slug>/
              + merge commit on main in hub/
```

Everything lives in the wiki or in the worktree. Nothing important lives only in `.millhouse/scratch/` (that's ephemeral).

---

## When things go wrong

### Discussion produces bad output

User stops the session, deletes `discussion.md`, re-runs `mill-start` from scratch. No orchestrator state to unwind.

### Plan review keeps saying REQUEST_CHANGES

User reads findings, either:
- Edits plan.md directly and re-runs validator + review
- Iterates with `mill-plan` (which will spawn Claude again with the findings)
- Decides the task is under-specified, goes back to `mill-start`

### Implementer fails on card 2 of 5

`mill-go` stops. Cards 1's commits are preserved. Status marked as failed. User:
- Reads card-2-result.md for what went wrong
- Fixes the plan (maybe the card was over-specified)
- Re-runs `mill-go --from-card 2` (future feature — for v2.0, re-run from scratch and accept wasted card 1 time)

### Review loop ping-pongs

Default `--max-review-rounds 1` prevents this. If user set higher and hit the cap, treat as failure and investigate.

### Worktree gets corrupted

User runs `mill-cleanup my-task`, then `mill-spawn my-task` again. State in wiki is preserved; local worktree is rebuilt.

---

## What the skill files actually contain

Each `SKILL.md` (at `plugins/mill/skills/mill-{start,plan,go}/`) is the runtime instruction set Claude reads when invoked. Structure:

```markdown
---
name: mill-start
description: Discussion phase for a task
---

# mill-start

## When the user invokes me

They have a worktree, a slug, a task description. They want to explore the approach.

## What I do

1. Read .millhouse/.<slug>.slug.md for the task title
2. Read wiki/active/<slug>/status.md for current phase
3. If phase != discussing: confirm with user before proceeding
4. Read relevant source files (use Grep to find them)
5. Ask the user clarifying questions about scope, constraints, approach
6. As we converge, write findings to wiki/active/<slug>/discussion.md
7. When the user says "done", finalise discussion.md and print next steps
```

Keep skills under ~150 lines. They're the program Claude executes. Code primitives do the mechanical work.
