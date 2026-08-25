---
name: orch-review
description: Fork one background worker per slug to wait for a mill-start --orch worker's discussion.md and write an orchestrator-authored discussion review, keeping the blocking wait and review work out of the orchestrator's own context.
argument-hint: "<slug> [<slug>...]"
---

# orch-review

Companion to `mill-start`'s `--orch` flag. A worker running `/mill-start --orch` pauses before discussion-review round 1's automated reviewer dispatch, waiting for a file named `orch-review.md` to appear next to `discussion.md`. This skill is what **this session** (the orchestrator/driver, not the worker) loads to actually write that file — it is the human-in-the-loop substitute for round 1's automated reviewer.

**This skill forks itself, once per slug, before doing anything else.** The wait for `discussion.md` and the review work both belong entirely inside each fork — an orchestrator that dispatches many `--orch` workers and calls this skill for each one accumulates a lot of polling/reading/reviewing noise if any of that runs inline, so none of it does. The fork inherits this skill's full text plus everything else already in the orchestrator's conversation (no re-briefing needed) but keeps its own tool calls out of the orchestrator's context; only a completion notification comes back.

This skill (neither the top-level turn nor any fork it spawns) ever dispatches a non-fork agent, touches `_mill/reviews/`, or commits/pushes anything — its entire footprint is writing one ephemeral file per slug. Each waiting worker consumes its own file and is solely responsible for turning it into the canonical, committed review artifact.

## Orchestrator-side steps (run here, in this session)

### Step 1 — Parse slugs and fork, one per slug

The argument is one or more task slugs (whitespace-separated), each the same slug its worker was dispatched into. For each slug, launch a fork immediately via the `Agent` tool with `subagent_type: "fork"` — when there is more than one slug, launch all of them in a single message (multiple `Agent` tool-use blocks) so they run in parallel, per this session's own "user asks for parallel work" rule.

Each fork's prompt must be self-contained enough to name its one target slug and tell it to skip straight to the "Fork-side steps" section below (this skill's own Step 0/forking logic does not apply inside the fork — it is already the fork), e.g.:

```
You are the forked orch-review worker for slug <slug>. Skip this skill's
"Orchestrator-side steps" entirely -- that's already done, you are the fork it produced.
Execute the "Fork-side steps" section below for <slug> only, ignoring any other slug
mentioned elsewhere in your inherited context. Report back per Fork-side Step 6.
```

Do not resolve any path, wait on any file, or read `discussion.md` directly in this top-level turn — all of that is Fork-side work.

### Step 2 — Report launch, then return control

Immediately after Step 1, tell the user, e.g.:

```
Forking orch-review for <slug>[, <slug2>, ...] -- each will write orch-review.md once its
discussion.md exists. Not blocking this session; you'll be notified as each one finishes.
```

Do not wait for any fork to finish in this turn — continue the conversation normally.

### Step 3 — Relay each fork's completion

When a fork's completion notification arrives (a later turn, not this one), relay a short summary to the user per this session's own Agent-tool convention — which slug, whether `orch-review.md` was written or the fork hit an error/timeout, one line each. Do not `Read` or tail the fork's `output_file`; trust the notification.

## Fork-side steps (run entirely inside each forked session)

### Step 1 — Resolve the target worktree

The target slug is the one named in this fork's own dispatch prompt.

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import _paths
git_root = _paths.resolve_git_root()
container = _paths.resolve_container_path(git_root)
print(_paths.resolve_canonical_worktree_path(container, '<slug>'))
"
```

If the printed path does not exist, halt: `"<slug>: no worktree found at <path> — was it spawned, and is the worker actually running mill-start --orch there?"`

### Step 2 — Blocking wait for `discussion.md`

This fork can start waiting as soon as it's launched — it does not require confirmation that the worker has reached Phase: Discussion Review. Block until `<worktree>/_mill/discussion.md` exists: same idiom as `orch-wait`'s own wait (`Monitor` tool, persistent bash poll, not a fixed `sleep`), polling every 30 seconds, giving up after the same configured `pipeline.entry_wait_timeout_minutes` `orch-wait` reads (load config the same way — do not hardcode). This entire wait — including every `Monitor` poll — runs inside this fork; none of it reaches the orchestrator's own context.

On timeout: halt and report `"<slug>: discussion.md not written after <N>h -- is the worker still running mill-start --orch?"`. This fork makes no `status.md` writes of its own even on timeout — the worker owns all `status.md` mutations; if it is actually stuck, that is diagnosed and fixed on the worker side, not here.

### Step 3 — Read the discussion in full

Read `<worktree>/_mill/discussion.md` in full — do not skim. If `<worktree>/_mill/orch-review.md` already exists, halt and ask whether to overwrite (a stale file from a prior round may still be awaiting pickup).

### Step 4 — Review it

Apply the same rubric `plugins/mill/templates/review-discussion.md` gives an automated reviewer — read that template's "## Criteria" section and apply each bullet (undecided items, scope, constraint coverage, tooling/validator claims, failure modes, testing, ambiguity, feasibility, decisions). Ground every finding in an actual quote or section reference from `discussion.md` — never fabricate. Explore the codebase as needed to verify claims, exactly as an automated reviewer would.

Severity and class vocabulary are closed, per `plugins/mill/templates/review-output.schema.md`: severity is `BLOCKING` or `NIT` only (default ambiguous findings to `BLOCKING`); class is `design`, `scope`, `decision`, or `consistency`, always supplied.

### Step 5 — Write `orch-review.md`

Write `<worktree>/_mill/orch-review.md` (next to `discussion.md`, never inside `_mill/reviews/` — that directory is reserved for the canonical, timestamped files the worker's `finalize()` call produces) in the exact format `plugins/mill/templates/review-output.schema.md` documents:

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

### Step 6 — Report back

End with a short final message this fork's own turn — this becomes the text the orchestrator's Step 3 relays as a summary, e.g.:

```
Wrote _mill/orch-review.md for <slug>. The waiting worker polls every few seconds and will
pick this up, apply the mill-start review-fix decision tree, and resume mill-start --orch
on its own — no further action needed here.
```

## Rules

- **Fork first, always.** The top-level turn never resolves a worktree path, waits on a file, or reads/writes anything under `_mill/` itself — every Fork-side step runs only inside a fork, one per slug.
- **One file, one purpose, per fork.** Each fork's entire footprint is writing its own `_mill/orch-review.md`. No fork reads or writes `status.md`, `_mill/reviews/`, or anything under the wiki.
- **Never used for round 2+.** `mill-start --orch` only waits for this file on discussion-review round 1; any later round in the same task reverts to the normal configured automated reviewer. Re-running this skill against a task past round 1 has no effect (nothing is waiting for the file).
- **Ground every finding.** Same source-grounding rule the automated reviewer prompt carries: never fabricate file contents or discussion.md sections not actually read.
- **Don't peek.** The orchestrator never reads a fork's transcript/output_file mid-flight — trust the completion notification per this session's own fork guidance.
