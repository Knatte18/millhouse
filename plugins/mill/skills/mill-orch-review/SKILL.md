---
name: mill-orch-review
description: Write an orchestrator-authored discussion review for a dispatched mill-start --auto agent that is paused awaiting review (mill-start-orch-review's round-1 wait), signaling it to resume.
argument-hint: "<slug>"
---

# mill-orch-review

Companion skill to `mill:mill-start-orch-review`. That skill dispatches a worker agent to run `/mill-start --auto` but pauses it before round 1's automated reviewer dispatch, waiting for a file named `orch-review.md` to appear next to `discussion.md`. This skill is what **this session** (the orchestrator/driver, not the worker) loads to actually write that file — it is the human-in-the-loop substitute for round 1's automated reviewer.

This skill never dispatches an agent, never touches `_mill/reviews/`, and never commits or pushes anything — it only writes one ephemeral file. The waiting worker consumes it and is solely responsible for turning it into the canonical, committed review artifact.

## Step 1 — Resolve the target worktree

The argument is the task slug (the same slug the worker was dispatched into).

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import _paths
git_root = _paths.resolve_git_root()
container = _paths.resolve_container_path(git_root)
print(_paths.resolve_canonical_worktree_path(container, '<slug>'))
"
```

If the printed path does not exist, halt: `"<slug>: no worktree found at <path> — was it spawned, and is the worker actually running mill-start-orch-review there?"`

## Step 2 — Read the discussion in full

Read `<worktree>/_mill/discussion.md` in full — do not skim. If `<worktree>/_mill/orch-review.md` already exists, halt and ask whether to overwrite (a stale file from a prior round may still be awaiting pickup).

## Step 3 — Review it

Apply the same rubric `plugins/mill/templates/review-discussion.md` gives an automated reviewer — read that template's "## Criteria" section and apply each bullet (undecided items, scope, constraint coverage, tooling/validator claims, failure modes, testing, ambiguity, feasibility, decisions). Ground every finding in an actual quote or section reference from `discussion.md` — never fabricate. Explore the codebase as needed to verify claims, exactly as an automated reviewer would.

Severity and class vocabulary are closed, per `plugins/mill/templates/review-output.schema.md`: severity is `BLOCKING` or `NIT` only (default ambiguous findings to `BLOCKING`); class is `design`, `scope`, `decision`, or `consistency`, always supplied.

## Step 4 — Write `orch-review.md`

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

## Step 5 — Report

Tell the user:

```
Wrote _mill/orch-review.md for <slug>. The waiting worker polls every few seconds and will
pick this up, apply the mill-start review-fix decision tree, and resume mill-start --auto
on its own — no further action needed here.
```

## Rules

- **One file, one purpose.** This skill's entire footprint is writing `_mill/orch-review.md`. It does not read or write `status.md`, `_mill/reviews/`, or anything under the wiki.
- **Never used for round 2+.** The paired `mill-start-orch-review` skill only waits for this file on discussion-review round 1; any later round in the same task reverts to the normal configured automated reviewer. Re-running this skill against a task past round 1 has no effect (nothing is waiting for the file).
- **Ground every finding.** Same source-grounding rule the automated reviewer prompt carries: never fabricate file contents or discussion.md sections not actually read.
