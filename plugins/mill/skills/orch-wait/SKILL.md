---
name: orch-wait
description: Loaded by mill-start when invoked with --orch -- waits for an orchestrator-authored orch-review.md and substitutes it for discussion-review round 1's automated reviewer dispatch.
argument-hint: ""
---

# orch-wait

Loaded by `mill-start`'s `## Orch mode (--orch)` section, only for discussion-review round 1, in place of that phase's normal Step 2 dispatch. Companion skill: `orch-review`, loaded separately by the orchestrator (the session that dispatched this worker) to write the file this skill waits for.

This skill assumes `mill-start`'s Entry and Path Setup have already run — `slug`, `cfg`, `git_root`, `worktree_root`, `status_path`, `reviews_dir` are already bound. It performs one round's worth of work, then hands back to `mill-start`'s own Phase: Discussion Review at step 3.

## Step 1 — Announce the wait

Report to the log/status: `"Waiting for orchestrator review -- write _mill/orch-review.md next to discussion.md to resume."` No operator is present in this worker's own conversation to prompt.

## Step 2 — Blocking wait for the file

Same idiom as the entry-gate wait in `mill-go-base/SKILL.md` (`Monitor` tool, persistent bash poll, not a fixed `sleep`): poll every 30 seconds for `<worktree_root>/_mill/orch-review.md` to exist, giving up after the configured `pipeline.entry_wait_timeout_minutes` (read from config the same way `mill-go-base`'s entry-gate wait does, rather than hardcoding).

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
