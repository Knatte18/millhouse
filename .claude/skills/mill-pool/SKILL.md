---
name: mill-pool
description: Drive a fixed-size pool of mill task pipelines against this repo's own wiki backlog in parallel, unattended, until the backlog is empty. Invoked as /mill-pool [--count N]. Local to this repo — not part of the mill plugin, not portable to other repos.
argument-hint: "[--count N]"
---

# mill-pool

> Repo-local skill. Lives in `.claude/skills/`, not `plugins/mill/skills/` — this drains millhouse's own wiki backlog and has no reason to exist in a repo that merely consumes the `mill` plugin. Never move this into `plugins/mill/`.

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

Keeps `--count` (default 8) mill task pipelines running in parallel — each a full `mill-spawn` → `mill-start` → `mill-plan` → `mill-go` cycle in its own worktree — continuously pulling the next ready backlog task into a freed slot, until the wiki backlog has none left to claim.

This skill dispatches Agent-tool calls; it does not itself write code or run implementer/reviewer work. Unattended: no operator is present once this starts, so every phase's own halt/prompt handling below matters — this is not the skill to invoke when you want to watch and steer each decision.

All Bash snippets below assume the current working directory is this repo's hub root (`/home/knatte/Code/millhouse/wts/millhouse`) unless stated otherwise, and reference the mill plugin's scripts by the repo-relative path `plugins/mill/scripts/` — not `${CLAUDE_PLUGIN_ROOT}`. That variable resolves to the *invoking* plugin's own root and is only reliable inside a skill that plugin ships; this skill isn't shipped by any plugin, so it would resolve to the wrong thing (or nothing). Since this skill only ever runs inside the millhouse repo itself — where `plugins/mill/scripts/` is real, checked-out source, not a cache — the repo-relative path is both correct and simpler here.

---

## Hard constraint — never claim a task whose dependency isn't done

**A task is only claimable when its wiki `layer` is `"A"`.** Layer A means every entry in that task's `depends_on` (if any) is already `status: done` — the wiki computes this for you via `_client.list_tasks_brief`. A task with an unmet dependency sits at Layer B or deeper and **must not** be claimed, spawned, or passed to `mill-spawn`, no matter how idle the pool is.

`mill:mill-spawn --slug <slug>` only checks that the task is unclaimed (`status is None`) — it does **not** check dependency readiness. Passing it a Layer-B-or-deeper slug will happily claim a task whose prerequisite work hasn't landed yet. **This skill's own task-selection step (below) is the only place this is enforced — never skip it, never claim by any other means.**

## Entry

**Step 0: Load `mill:prose`, then `mill:conversation`.**
Load both skills via the Skill tool, unconditionally, immediately — before any other Entry step. `mill:conversation` builds on `mill:prose`, so load it first.

**Step 0.5 — Parse arguments.**
Read `$ARGUMENTS`. `--count <N>` sets the pool size; a bare positive integer with no flag is accepted as shorthand for the same thing. Default `POOL_SIZE = 8` when omitted. Halt with a usage error on a non-positive or non-integer value.

**Step 1 — Resolve paths.**
`git_root = _paths.resolve_git_root()`, `wiki_path = _paths.resolve_wiki_path(git_root)`. This skill runs from the hub — the same invariant `mill-cleanup` and `mill-spawn` rely on. `git_root` should equal this repo's own root; if it doesn't (this skill got invoked from some other checkout), halt — it has nothing to drain there.

## Picking a task

Re-run this query fresh every single time a slot needs a new task — never reuse a stale list, since layers shift as other tasks complete (a Layer B task is promoted to Layer A the moment its dependency's `mill-cleanup` sweep flips it to `done`):

```bash
PYTHONPATH="plugins/mill/scripts" "$MILL_PYTHON" -c "
import json, _paths
from wiki import _client
wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
print(json.dumps(_client.list_tasks_brief(wiki_path), indent=2))
"
```

A task is ready to claim only if `status is None` **and** `layer == "A"` (see Hard constraint above). If no such task exists, there is nothing to claim right now — see "Winding down."

Never invoke `mill:mill-spawn` without `--slug`. The bare (no-slug) form drops into an interactive numbered picker reading from stdin — with no operator present, that call hangs forever. Always resolve a specific slug yourself first, then pass it explicitly.

## Per-slug lifecycle

For each pool slot, cycle through:

1. **Claim + spawn worktree.** From the hub: `mill:mill-spawn --slug <slug>` (creates the worktree, branch, junctions, and `_mill/status.md`).
2. **Dispatch a fresh subagent** (Agent tool, `subagent_type: "general-purpose"`) using the "Phase prompt: mill-start + mill-plan" template below, `{SLUG}` filled in. Wait for it to report back.
   - Halt reported: log the outcome, leave the worktree exactly as-is (an operator needs to look at it), free this slot, go to step 5 — claim a new task into a **different**, fresh worktree. Never auto-retry the same slug.
   - Success (phase: planned): continue to step 3.
3. **Dispatch a second, fresh subagent** (new Agent-tool call, no memory of step 2) using the "Phase prompt: mill-go" template below, same slug. Deliberately a separate dispatch from step 2 — `mill-go`'s own batch/review loop can run long and dispatches its own implementer/reviewer subagents internally; it must not share a context window with the mill-start/mill-plan run that preceded it. Wait for it to report back.
4. **Sweep.** From the hub (never from inside a task worktree):
   ```bash
   PYTHONPATH="plugins/mill/scripts" "$MILL_PYTHON" "plugins/mill/scripts/millpy-cleanup.py"
   ```
   Safe, global, idempotent — it only touches tasks actually marked `[done]` or `[pr-pending]` in Home.md, so it never disturbs other pool slots' in-progress worktrees. Run it after every slug's mill-go dispatch reports back, regardless of outcome (merged, PR opened, or halted): it tears down what's actually done and leaves the rest untouched. A PR-pending slug isn't torn down yet — a later sweep (after the PR merges) finishes it. Don't special-case that here.
5. **Refill.** This slot is now free regardless of step 2/3's outcome. Re-query the task list (per "Picking a task") and claim the next Layer-A task into a fresh worktree. If none is available, this slot stays idle — don't busy-loop; move on to whichever other slot reports back next.

## Winding down

Done when a re-query finds no Layer-A unclaimed tasks **and** every active slot has finished its current pipeline (nothing left to report back from). Do one final sweep from the hub, write the final report (below), and stop.

## Phase prompt: mill-start + mill-plan (fill in `{SLUG}`)

```
You are driving mill-start and then mill-plan to completion for one mill v2 task, unattended, in its own git worktree. No human operator is present -- every decision that would normally go to an operator prompt is yours to make and document, not to halt on, unless it matches the "genuine halt" list below.

## Your worktree

Slug: {SLUG}
Worktree path: /home/knatte/Code/millhouse/wts/{SLUG}

All work happens inside that worktree. Do not touch /home/knatte/Code/millhouse/wts/millhouse (the hub/parent) or any other task worktree -- this repo enforces worktree isolation (see its CLAUDE.md and the mill:conversation skill, which mill-start loads itself as its own first step; it bans editing, committing, or cd-ing into the parent from a child worktree).

The worktree was already created by mill-spawn: branch, junctions, and _mill/status.md already exist. Do not re-run mill-spawn or mill-claim.

**Never call the EnterWorktree or ExitWorktree tools.** This path is already a real git worktree in millhouse's own container layout (`wts/<slug>`, created by mill-spawn) -- not one of the harness's own `.claude/worktrees/` sandboxes. EnterWorktree creates a brand-new worktree under `.claude/worktrees/` whenever it sees phrasing like "work in your own worktree," and creating one needs an approval no operator is present to give. Just run a plain `cd /home/knatte/Code/millhouse/wts/{SLUG}` via Bash (never compound it with a git command -- use `git -C <path> <command>` for one-off git calls per this repo's CLAUDE.md) as your first action, then treat that as your cwd for every subsequent Read/Write/Edit/Bash call.

## What to run, in order

1. Invoke mill:mill-start (Skill tool) from inside {SLUG}'s worktree, and let it run to completion (phase: discussed, discussion.md committed and pushed).
2. Then invoke mill:mill-plan (Skill tool), same worktree, and let it run to completion (phase: planned). mill-plan reads discussion.md cold from disk -- that's its normal mode, nothing special needed from you here.

## Handling mill-start's Discuss phase without an operator

mill-start's Phase: Discuss is normally a live conversation with a human to shape discussion.md. You have no human to talk to. Instead:

1. Read this task's full body/brief from the wiki before starting Discuss -- it already contains the original source report(s) this task was created from (reproduction steps, root-cause analysis, suggested fix, in most cases). Read .wiki/Home.md (or use the wiki _client.get_task helper) for the {SLUG} entry.
2. Treat that body as the requirements source a human would otherwise have given you in conversation. Where it already names a concrete fix, use it as your discussion's technical approach unless you find, while reading the actual current code, that it's wrong or outdated -- reading the real code takes priority over trusting the task body.
3. Where the task bundles several source items, cover each one's fix in the discussion -- don't silently drop any.
4. Where a genuine design decision is open, make the most defensible call yourself, state it plainly as an assumption in discussion.md, and proceed. Do not halt waiting for a human to resolve it.
5. Any operator-facing prompt mill-start's or mill-plan's phases would normally raise (per the mill:conversation numbered-options convention): resolve it by picking option 1 (the recommended option) yourself, and note that you did so autonomously.

## Genuine halts -- stop and report, don't push through

If mill-start or mill-plan reaches one of its own documented halt states (a non-progress halt, max-rounds exhaustion, a blocked-resume state) rather than an ordinary operator-choice prompt, respect it -- don't retry blindly, don't force past it, don't edit skill files to work around it. Capture the exact halt message and stop.

## Reporting back

Write your run log to /home/knatte/Code/millhouse/wts/{SLUG}/.scratch/mill-start-plan-result.md: phase reached in each of mill-start and mill-plan, any autonomous decisions you made in place of an operator prompt (with reasoning), final outcome (planned / halted-with-reason).

Your final message back to the caller must be only: the path to that result file, plus one sentence (final state, needs-attention or not). Do not paste the full log inline.
```

## Phase prompt: mill-go (fill in `{SLUG}`)

```
You are driving mill-go to completion for one mill v2 task, unattended, in its own git worktree. No human operator is present. mill-go itself dispatches implementer and reviewer subagents per batch as part of its own normal operation -- that's expected and is mill-go's own job, not something you need to manage yourself.

## Your worktree

Slug: {SLUG}
Worktree path: /home/knatte/Code/millhouse/wts/{SLUG}

Do not touch /home/knatte/Code/millhouse/wts/millhouse (the hub/parent) or any other task worktree. This is a fresh dispatch with no memory of the mill-start/mill-plan run that preceded it -- that's expected; mill-go reads the approved plan cold from disk.

**Never call the EnterWorktree or ExitWorktree tools.** This path is already a real git worktree in millhouse's own container layout (`wts/<slug>`, created by mill-spawn) -- not one of the harness's own `.claude/worktrees/` sandboxes. EnterWorktree creates a brand-new worktree under `.claude/worktrees/` whenever it sees phrasing like "work in your own worktree," and creating one needs an approval no operator is present to give. Just run a plain `cd /home/knatte/Code/millhouse/wts/{SLUG}` via Bash (never compound it with a git command -- use `git -C <path> <command>` for one-off git calls per this repo's CLAUDE.md) as your first action, then treat that as your cwd for every subsequent Read/Write/Edit/Bash call.

## What to run

Invoke mill:mill-go (Skill tool) from inside {SLUG}'s worktree, and let it run every batch in the plan's DAG to completion. mill-go hands off to mill-finalize at the end per the hub's pipeline.auto_merge config (PR or direct merge) -- let that run through too, it's part of the normal pipeline.

This can take a while (multiple batches, multiple review rounds per batch) -- that's normal, not a problem to work around.

Do **not** run mill-cleanup yourself -- the coordinator handles that after you report back.

## Genuine halts -- stop and report, don't push through

If mill-go (or mill-finalize) halts -- a stuck-escalation halt, a done-gate failure, a non-progress halt, a PR-pending state -- respect it. Don't retry blindly, don't force an approval past it, don't edit skill files to work around it. A PR-pending halt is a normal successful outcome for PR-mode hubs, not a failure -- report it as such.

## Reporting back

Write your run log to /home/knatte/Code/millhouse/wts/{SLUG}/.scratch/mill-go-result.md: batches completed, review rounds per batch, final outcome (merged / PR opened / halted-with-reason), commit SHAs or PR URL.

Your final message back to the caller must be only: the path to that result file, plus one sentence (final state, needs-attention or not). Do not paste the full log inline.
```

## Reporting (this skill's own)

Keep a running tally as slugs complete — don't wait until the very end to start writing this. After each slug's cycle finishes (Per-slug lifecycle step 4/5), append a section to `/home/knatte/Code/millhouse/wts/millhouse/.scratch/coordinator-summary.md`: slug, final outcome (merged / PR opened / halted-with-reason), and a one-line pointer to anything needing human attention (a halt, an autonomous design decision worth double-checking, a failed verify gate).

When winding down, do a final pass over that file to make sure every slug claimed this run has an entry, then report to the operator: only the path to `coordinator-summary.md`, plus a short list of which slugs (if any) need human attention and why. Do not paste the full per-slug logs inline.
