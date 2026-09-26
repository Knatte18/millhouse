---
name: orch-wait
description: Loaded by mill-start when invoked with --orch -- waits for an orchestrator-authored orch-review.md and substitutes it for discussion-review round 1's automated reviewer dispatch.
argument-hint: ""
---

# orch-wait

Loaded by `mill-start`'s `## Orch mode (--orch)` section, only for discussion-review round 1, in place of that phase's normal Step 2 dispatch. Companion skill: `orch-review`, loaded separately by the orchestrator (the session that dispatched this worker) to write the file this skill waits for.

This skill assumes `mill-start`'s Entry and Path Setup have already run — `slug`, `cfg`, `git_root`, `worktree_root`, `status_path`, `reviews_dir` are already bound. It performs one round's worth of work, then hands back to `mill-start`'s own Phase: Discussion Review at step 3.

## Step 1 — Announce the wait and notify the orchestrator

Report to the log/status: `"Waiting for orchestrator review -- write _mill/orch-review.md next to discussion.md to resume."` No operator is present in this worker's own conversation to prompt.

Then send the orchestrator one notification, so it need not have armed `/orch-review <slug>` beforehand.
`discussion.md` is already written and committed at this point.

1. Read `parent_thread = _status.read_parent_thread(status_path)`.
   When it is `None`, skip the notification.
2. Load `SendMessage` with `ToolSearch` (`select:SendMessage`) if its schema is not loaded.
3. Call `SendMessage(to: <parent_thread>, message: "discussion.md for <slug> is ready for your review at <worktree_root>/_mill/discussion.md -- run /orch-review <slug>")`, with `parent_thread` verbatim (never case-folded) and the message plain ASCII.

This is a one-way notification: no `ask-id`, no reply parsing, no retry.
A missing `parent_thread`, a `ToolSearch` miss, or a `SendMessage` error (session not listed in `ListAgents`, renamed, closed) is logged as `"orch-wait: parent notify skipped -- <reason>"` and never aborts the run.
Continue to Step 2 in every case; if nobody acts on the message, the orchestrator can still arm `/orch-review <slug>` by hand before the timeout.

## Step 2 — Blocking wait for the file

The wait uses the `Monitor` tool as in the "Entry-gate wait for upstream mill-plan" section of `mill-go-base/SKILL.md`, called as `Monitor(command=cmd, timeout_ms: 1800000, description=...)`.
`giveup_s` is `pipeline.entry_wait_timeout_minutes * 60`, read from config the same way that `mill-go-base` section does (default 240 when absent), not hardcoded.
Before the first arm, record `wait_started_epoch` from `date +%s` once, and record the `task_id` the `Monitor` call returns.
`cmd` is this inline file-exists poll, with `<orch_review_path>` being the orch-review file under `<worktree_root>/_mill/` and `<giveup_s>` substituted:

```bash
elapsed=0
while true; do
  if [ -f "<orch_review_path>" ]; then
    echo "READY"
    exit 0
  fi
  if [ "$elapsed" -ge <giveup_s> ]; then
    echo "TIMEOUT after ${elapsed}s waiting for orch-review.md"
    exit 2
  fi
  sleep 30
  elapsed=$((elapsed + 30))
done
```

Branch on the `<event>` content with the same rules as the `mill-go-base` section.
`READY` continues to Step 3.
A `TIMEOUT after <N>s ...` line takes the `On timeout:` block below.
Any other event content is an unexpected early expiry: run `date +%s` and compute `remaining_s = giveup_s - (now - wait_started_epoch)`.
When `remaining_s <= 0`, take the `On timeout:` block.
Otherwise re-issue the same `Monitor` call with the poll script's `<giveup_s>` replaced by `remaining_s`, record the new `task_id`, and wait again.
The second, event-less `<status>completed</status>` notification needs no branch;
see `plugins/mill/docs/harness-tool-contracts.md` for the two-notification contract.

On timeout: `_status.set_blocked(status_path, "auto: awaiting orchestrator review (orch-review.md) timed out after <N>h", timestamp=_timestamp.now_utc_iso())`, then `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-start: blocked (auto: orchestrator review timeout) for <slug>" && git -C <worktree> push`, then halt. Do not retry. This halt message must read differently from `--auto`'s own "discussion review gaps unresolved after N rounds" halt, so an operator reading `status.md` later can tell which condition fired.

## Step 3 — Consume the file

Read `<worktree_root>/_mill/orch-review.md` in full as `raw_text`, then run it through the same backend `finalize()` call the normal Step 2 Agent-mode dispatch would otherwise reach — this reuses the blocking-class ceiling, verdict parsing, and canonical file-naming/writing `_review_discussion.finalize` already implements, so round 1's envelope shape needs no hand-derivation:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import dataclasses, json
import _config, _paths
from _review_discussion import finalize

git_root = _paths.resolve_git_root()
worktree_root = _paths.resolve_hub_path()
cfg = _config.load_config(worktree_root, git_root)
wiki_path = _paths.resolve_wiki_path(git_root)
reviews_dir = worktree_root / cfg['paths']['reviews_dir']
raw_text = open(worktree_root / '_mill/orch-review.md', encoding='utf-8').read()

result = finalize(
    cfg, '<slug>', raw_text,
    round_n=1, reviews_dir=reviews_dir,
    mill_dir=worktree_root, project_root=git_root, wiki_root=wiki_path,
    actual_model='orchestrator',
)
print(json.dumps(dataclasses.asdict(result)))
"
```

`finalize()` writes the canonical, timestamped review file under `_mill/reviews/` and returns the same `ReviewResult` shape Step 2 already knows how to consume — parse the printed JSON exactly as if it were round 1's own JSON envelope.

## Step 4 — Remove the trigger file

`<worktree_root>/_mill/orch-review.md` is ephemeral and never committed — delete it now that `finalize()` produced the canonical copy, so it can't be mistaken for a fresh one on a later task.

## Step 5 — Cost line

Print this round's line per `mill-go-base/SKILL.md`'s "## Review cost line" section with `reviewer_model = orchestrator` and no duration/tool-calls/cost figures (absent, same as any review file predating that metric).

## Step 6 — Hand back to mill-start

Return control to `mill-start`'s Phase: Discussion Review at step 3, passing the envelope from Step 3 above exactly as if it were round 1's own Step 2 output. `mill-start`'s `--auto` rules already govern everything from there (FIX-everything, no PUSH BACK, commit, push, loop or Handoff per the Convergence gate).

## Rules

- **One-shot, round 1 only.** This skill is never loaded for round 2+ — `mill-start` only loads it when `round_n == 1`. Round 2 (if the loop continues) uses the real configured automated reviewer, unmodified.
- **Never loaded outside `--orch`.** `--auto` alone always uses the real automated reviewer for every round; this skill exists only for the `--orch` flag's one substitution.
