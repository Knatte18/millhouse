---
name: orch-review
description: Wait (via Monitor, in this session) for a mill-start --orch worker's discussion.md, then fork just the read/review/write work per slug so it doesn't clutter the orchestrator's own context.
argument-hint: "<slug> [<slug>...]"
---

# orch-review

Companion to `mill-start`'s `--orch` flag. A worker running `/mill-start --orch` pauses before discussion-review round 1's automated reviewer dispatch, waiting for a file named `orch-review.md` to appear at `.scratch/orch-review.md`. This skill is what **this session** (the orchestrator/driver, not the worker) loads to actually write that file — it is the human-in-the-loop substitute for round 1's automated reviewer.

**The `discussion.md` wait runs in this session, not in a fork.** A fork that arms a `Monitor` wait and then produces no further output is treated as finished and torn down — the monitor trigger has nothing left to wake up, so a fork left waiting on one never resumes. Only this top-level session reliably survives an armed `Monitor` wait and gets woken back up when it fires. So: **this session owns every `Monitor` wait, one per slug; a fork is only launched per slug after that slug's `discussion.md` is already confirmed to exist** — the fork only ever does the (non-blocking) read/review/write work, which is what still needs to stay out of this session's own context.

This skill (neither the top-level turn nor any fork it spawns) ever dispatches a non-fork agent, touches `_mill/reviews/`, or commits/pushes anything — its entire footprint is writing one ephemeral file per slug. Each waiting worker consumes its own file and is solely responsible for turning it into the canonical, committed review artifact.

## Orchestrator-side steps (run here, in this session)

### Step 1 — Parse slugs and resolve each worktree

The argument is one or more task slugs (whitespace-separated), each the same slug its worker was dispatched into. For each slug, resolve its worktree path here (not in a fork — the path is needed to arm this session's own wait in Step 2):

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import _paths
git_root = _paths.resolve_git_root()
container = _paths.resolve_container_path(git_root)
print(_paths.resolve_canonical_worktree_path(container, '<slug>'))
"
```

If the printed path does not exist for a slug, do not arm a wait for it — report `"<slug>: no worktree found at <path> — was it spawned, and is the worker actually running mill-start --orch there?"` and drop that slug from the remaining steps (other slugs proceed independently).

### Step 2 — Arm a `Monitor` wait per slug, in this session

For each remaining slug, start the blocking wait for `<worktree>/_mill/discussion.md` to exist **in this session**: same idiom as `orch-wait`'s own wait (persistent background bash poll, not a fixed `sleep`, polling every 30 seconds), armed via the `Monitor` tool so this turn ends and this session resumes when the file appears — giving up after the same configured `pipeline.entry_wait_timeout_minutes` `orch-wait` reads (load config the same way — do not hardcode). When there is more than one slug, arm all of their waits before ending this turn, so they proceed concurrently rather than one-at-a-time.

Tell the user once, e.g.:

```
Watching for discussion.md for <slug>[, <slug2>, ...] -- will fork the review write-up for
each as soon as its file appears. Not blocking this session; you'll be notified per slug.
```

### Step 3 — On each slug's trigger: timeout, or fork

When a given slug's `Monitor` wait fires:

- **Timeout:** halt for that slug only and report `"<slug>: discussion.md not written after <N>h -- is the worker still running mill-start --orch?"`. Make no `status.md` writes of any kind — the worker owns all `status.md` mutations; if it is actually stuck, that is diagnosed and fixed on the worker side, not here. Other slugs' waits are unaffected.
- **`discussion.md` now exists:** launch a fork (`Agent` tool, `subagent_type: "fork"`) for that slug only, right now — do not batch it with other slugs' triggers, since they fire independently. The fork's prompt names the slug and its already-resolved worktree path, and tells it to skip straight to "Fork-side steps" below (this skill's own Orchestrator-side steps do not apply inside the fork — it is already the fork), e.g.:

```
You are the forked orch-review worker for slug <slug> at worktree <worktree_path>.
discussion.md is already confirmed to exist -- do not wait for it. Skip this skill's
"Orchestrator-side steps" entirely and execute "Fork-side steps" below for <slug> only.
Report back per Fork-side Step 4.
```

### Step 4 — Relay each fork's completion

When a fork's completion notification arrives (a later turn, not this one), relay a short summary to the user per this session's own Agent-tool convention — which slug, whether `orch-review.md` was written or the fork hit an error, one line each. Do not `Read` or tail the fork's `output_file`; trust the notification.

## Fork-side steps (run entirely inside each forked session — no waiting here)

### Step 1 — Read the discussion in full

Read `<worktree>/_mill/discussion.md` in full — do not skim. If `<worktree>/.scratch/orch-review.md` already exists, halt and ask whether to overwrite (a stale file from a prior round may still be awaiting pickup).

### Step 2 — Review it

Apply the same rubric `plugins/mill/templates/review-discussion.md` gives an automated reviewer — read that template's "## Criteria" section and apply each bullet (undecided items, scope, constraint coverage, tooling/validator claims, failure modes, testing, ambiguity, feasibility, decisions). Ground every finding in an actual quote or section reference from `discussion.md` — never fabricate. Explore the codebase as needed to verify claims, exactly as an automated reviewer would.

Severity and class vocabulary are closed, per `plugins/mill/templates/review-output.schema.md`: severity is `BLOCKING` or `NIT` only (default ambiguous findings to `BLOCKING`); class is `design`, `scope`, `decision`, or `consistency`, always supplied.

### Step 3 — Write `orch-review.md`

Write `<worktree>/.scratch/orch-review.md` (gitignored ephemeral scratch space per `mill:conversation`'s convention — never inside `_mill/` at all, and specifically never inside `_mill/reviews/`, which is reserved for the canonical, timestamped files the worker's `finalize()` call produces) in the exact format `plugins/mill/templates/review-output.schema.md` documents:

```markdown
# Review: <task title>

```yaml
verdict: APPROVE | REQUEST_CHANGES
reviewer_model: orchestrator
reviewed_file: _mill/discussion.md
date: <UTC YYYY-MM-DD>
```

## Findings

### [BLOCKING|NIT][:design|scope|decision|consistency] <finding title>
**Section:** ...
**Issue:** ...
**Suggested fix:** ...

## Verdict

APPROVE | REQUEST_CHANGES
<one-sentence summary>
```

Omit `## Findings` entirely (write `(no findings)`) if there are none. `duration_s`/`tool_calls`/`cost_usd` are absent — this review has no such metadata, same as any review file written before that feature existed (see the schema doc).

### Step 4 — Report back

End with a short final message this fork's own turn — this becomes the text the orchestrator's Step 4 relays as a summary, e.g.:

```
Wrote .scratch/orch-review.md for <slug>. The waiting worker polls every few seconds and will
pick this up, apply the mill-start review-fix decision tree, and resume mill-start --orch
on its own — no further action needed here.
```

## Rules

- **This session owns every `Monitor` wait — never a fork.** A fork that ends its turn on an armed `Monitor` wait with nothing left to do is torn down as "finished" before the monitor ever fires; only this session survives that. Forking happens only after a slug's `discussion.md` is already confirmed present.
- **One file, one purpose, per fork.** Each fork's entire footprint is writing its own `.scratch/orch-review.md`. No fork reads or writes `status.md`, `_mill/reviews/`, or anything under the wiki. No fork waits on anything.
- **Never used for round 2+.** `mill-start --orch` only waits for this file on discussion-review round 1; any later round in the same task reverts to the normal configured automated reviewer. Re-running this skill against a task past round 1 has no effect (nothing is waiting for the file).
- **Ground every finding.** Same source-grounding rule the automated reviewer prompt carries: never fabricate file contents or discussion.md sections not actually read.
- **Don't peek.** The orchestrator never reads a fork's transcript/output_file mid-flight — trust the completion notification per this session's own fork guidance.
