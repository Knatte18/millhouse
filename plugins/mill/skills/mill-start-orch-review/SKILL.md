---
name: mill-start-orch-review
description: Variant entry for an agent dispatched to run mill-start --auto -- pauses before discussion-review round 1's automated reviewer dispatch and instead waits for an orchestrator-authored orch-review.md, then resumes full auto mode for the rest of mill-start unchanged.
argument-hint: ""
---

# mill-start-orch-review

Loaded by a **dispatched worker agent** (via the `Agent` tool, into a task worktree) whose brief is: run `/mill-start --auto` end-to-end, except that discussion-review round 1 is supplied by the orchestrator (the driving session that dispatched this worker) instead of the configured automated reviewer. Companion skill: `mill:mill-orch-review`, which the orchestrator loads separately to write the file this skill waits for.

This is a **thin override**, not a reimplementation. Follow `mill:mill-start`'s `--auto` mode verbatim — Entry, Phase: Color through Phase: Discussion File unchanged — and Phase: Discussion Review unchanged **except** for its Step 2 dispatch on round 1 only, which this skill replaces with the wait-and-substitute procedure below. Every round after round 1 (if the loop continues) reverts to mill-start's normal Step 2 automated-reviewer dispatch — this skill's substitution is one-shot.

## When the override applies

At the top of Phase: Discussion Review's loop, after computing `round_n` (mirror `_review_discussion.prepare`'s own round discovery so both agree — call `_review_common.discover_round(reviews_dir, "discussion", "holistic")` directly rather than duplicating its logic):

- `round_n == 1`: apply the override below in place of the normal Step 2 dispatch.
- `round_n > 1`: this skill does nothing further — follow `mill-start`'s Step 2 exactly as written (real automated reviewer, real `prepare`/dispatch/`finalize` cycle) for this and every later round.

## Round-1 override

1. **Announce the wait.** Report to the log/status: `"Waiting for orchestrator review -- write _mill/orch-review.md next to discussion.md to resume."` This worker has no operator in its own conversation to prompt; the wait is the only signal.

2. **Blocking wait for the file**, same idiom as the entry-gate wait in `mill-go-base/SKILL.md` (`Monitor` tool, persistent bash poll, not a fixed `sleep`): poll every 30 seconds for `<worktree_root>/_mill/orch-review.md` to exist, giving up after 4 hours (matching `pipeline.entry_wait_timeout_minutes`'s default — read it from config the same way mill-start's Entry does, rather than hardcoding, so a hub-wide override applies here too).

   On timeout: call `_status.set_blocked(status_path, "auto: awaiting orchestrator review (orch-review.md) timed out after <N>h", timestamp=_timestamp.now_utc_iso())`, then `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-start: blocked (auto: orchestrator review timeout) for <slug>" && git -C <worktree> push`, then halt. Do not retry.

3. **Consume the file.** Once present, read `<worktree_root>/_mill/orch-review.md` in full as `raw_text`, then run it through the exact same backend `finalize()` call mill-start's own Agent-mode dispatch would otherwise reach — this reuses the blocking-class ceiling, verdict parsing, and canonical file-naming/writing that `_review_discussion.finalize` already implements, so nothing about round 2+'s envelope shape needs to be re-derived by hand:

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

   `finalize()` writes the canonical, timestamped review file under `_mill/reviews/` (via `write_review_file`) and returns the same `ReviewResult` shape mill-start's Agent-mode dispatch already knows how to consume — parse the printed JSON exactly as if it were that round's JSON envelope.

4. **Remove the trigger file.** `<worktree_root>/_mill/orch-review.md` is ephemeral and never committed — delete it now that `finalize()` has produced the canonical copy, so a stale file cannot be mistaken for a fresh one on a future task.

5. **Resume mill-start's own logic unchanged from Step 3 onward** (`## Phase: Discussion Review`, steps 3, 3.5, Convergence gate, 4a/4b/5): treat the envelope from step 3 above exactly as if it were the output of mill-start's own Step 2 dispatch. Because this worker is running under `--auto` with no operator present, the `--auto`-mode rules already documented in `mill-start/SKILL.md`'s "Auto mode" subsection govern: every BLOCKING and every NIT is FIX (no PUSH BACK available), auto-resolve into `discussion_path`, commit, push, loop or proceed to Handoff per the Convergence gate.

6. **Cost line.** Print this round's line per `mill-go-base/SKILL.md`'s "## Review cost line" section with `reviewer_model = orchestrator` and no duration/tool-calls/cost figures (absent, per `review-output.schema.md`'s note that fields predating a metric are simply missing).

## After round 1

If the loop continues into round 2 (not converged and rounds remain), this skill has nothing further to add — the round-2 iteration's Step 2 dispatch is `mill-start`'s own real automated reviewer, unmodified. Everything from Phase: Discussion Review onward for that round, and every phase after the loop (Handoff), is plain `mill-start --auto` with no involvement from this skill.

## Rules

- **One-shot substitution.** Only discussion-review round 1 is ever supplied by the orchestrator. This skill has no mechanism for, and must never be asked to, substitute a later round.
- **Never used outside `--auto`.** Interactive `mill-start` already has an operator in its own conversation to review directly; this skill exists only so a dispatched worker with no operator in its context can receive one human-authored review. Do not load this skill for an interactive (non-`--auto`) run.
- **The wait is a real blocking wait**, not a fixed delay — same `Monitor`-tool bash-poll idiom as `mill-go-base/SKILL.md`'s entry-gate wait, including a giveup timeout and a `blocked`-status halt on giveup.
- **This worker's `--auto` blocked-halt vs. a review-timeout halt are distinct failure modes** — both use `_status.set_blocked`, but the message text must say which condition fired (compare the existing "discussion review gaps unresolved after N rounds" message in `mill-start/SKILL.md`'s Auto-mode subsection to this skill's own "awaiting orchestrator review... timed out" message) so an operator reading `status.md` later can tell them apart.
