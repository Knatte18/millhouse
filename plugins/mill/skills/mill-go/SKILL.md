---
name: mill-go
description: In a spawned worktree with an approved plan, sequentially execute every batch in the plan's DAG. Per batch spawn one implementer Sonnet, run code review, loop with receive-review on REQUEST_CHANGES, halt on stuck. Hand off to mill-merge.
---

# mill-go

You are the **Builder** — a lean orchestrator. You coordinate per-batch implementation but never read card bodies or diffs yourself. The **Implementer** (spawned per batch) reads its own batch file, implements cards, runs `verify:`, and fixes on receive-review. You read only `status.md`, the Batch Index DAG in `00-overview.md`, and the fenced yaml verdict block of each code review. Keeping your context lean is the whole point — Builder cost is a rounding error next to the Implementer and code-reviewer calls.

## Entry

1. `wiki.sync_pull()` on the wiki clone.
2. Read the slug via `_active.read_slug(Path(".millhouse"))`. Missing → halt with "this worktree was not created by mill-spawn".
3. Load config — deep-merge `<WIKI_PATH>/config.yaml` with `.millhouse/config.local.yaml`. Read these keys:
   - `pipeline.auto_merge` — whether to invoke mill-merge after success.
   - `pipeline.auto_report` — whether to auto-fire mill-self-report at end-of-work.
   - `review.code.rounds` — max review rounds per batch.
   - `review.code.self_fix_rounds` — passed to the implementer brief.
   - `review.code.holistic` — if true, run one holistic code review after all batches approve.
4. Acquire the builder lock: `_builder_lock.acquire(mill_dir, slug)`. On `LockBusy`: surface the message and halt — a second mill-go will corrupt state.
5. **Entry phase gate.** Read `<WIKI_PATH>/active/<slug>/status.md` phase:

   | phase | action |
   | --- | --- |
   | `planned` | fresh run — continue to Prepare |
   | `implementing` / `reviewing` / `fixing` | resume (see *Resume*) |
   | `blocked` | surface `blocked_reason` from status.md and halt |
   | `discussed` / `discussing` / `planning` | tell user to finish mill-plan and halt |
   | `done` | tell user the task is complete; suggest `/mill-merge` if auto-merge was off |
   | any other | surface + halt |

6. Read the plan overview: `<WIKI_PATH>/active/<slug>/plan/00-overview.md`. Confirm `approved: true` in the frontmatter. Extract the Batch Index via `_plan_dag.extract_batch_index(overview_text)`, validate via `_plan_dag.validate(batches, sorted(p.name for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"))`, then compute `order = _plan_dag.topo_order(batches)`.

## Prepare

On a fresh run only (no `## Batches` section in status.md):

- `_status.init_batches(status_path, order)` — seeds every batch at `state: pending`.
- `_status.append_phase(status_path, "implementing", _timestamp.now_utc_iso())`.
- Commit+push via `_wiki.write_commit_push(...)`.

## Execute — sequential loop

For each batch in `order`:

### 1. Implement

- Resolve the batch's file path via the Batch Index entry's `file:`.
- Build implementer prompt: render `plugins/mill/templates/implementer-brief.md`. Tokens:

   | Token | Value |
   | --- | --- |
   | `<TASK_TITLE>` | from `status.md` yaml block |
   | `<SLUG>` | the slug |
   | `<BATCH_NAME>` | batch name from Batch Index |
   | `<BATCH_FILE>` | abs path to `NN-<slug>.md` |
   | `<OVERVIEW_FILE>` | abs path to `00-overview.md` |
   | `<PROJECT_ROOT>` | worktree cwd (abs) |
   | `<WIKI_PATH>` | wiki path (abs) |
   | `<SELF_FIX_ROUNDS>` | `review.code.self_fix_rounds` |
   | `<ROUND>` | `1` on first implementation |

- Record `start_sha = git rev-parse HEAD` (reserved for future per-batch diff scoping — not used by the refactored code reviewer but kept for traceability).
- Set batch state → `running`, `start_sha: <sha>`. Generate a new `implementer_session = uuid4()` and record it.
- Commit+push status.md.
- Spawn implementer: `_implementer_sonnet.run(prompt_text, session_id=session_id, resume=False, cwd=project_root)`. Returns `(output, session_id)`.

### 2. Parse implementer report

The implementer's last output line must be JSON:

```json
{"status":"success|stuck","commit_sha":"...","session_id":"...", ...}
```

- `status: success` → continue to Code Review.
- `status: stuck, stuck_type: transient` → auto-retry ONCE with a fresh session (new UUID, `resume=False`). Record `review_round: 0`, do not change batch state. If second attempt is also stuck → escalate per *Stuck escalation* below.
- `status: stuck, stuck_type: verify | logic` → **ask user** per *Stuck escalation*.
- Malformed / missing JSON line → treat as `stuck_type: logic` reason "no structured report".

Record `commit_sha` from a successful report on the batch entry.

### 3. Code Review loop

- Set batch state → `reviewing`, `review_round: 1`.
- `_status.append_phase(status_path, f"reviewing-{batch_name}-r1", iso_ts)`.
- `extra_files = []`.

For each round `N` from 1 to `review.code.rounds`:

1. **Crash-recovery check.** Before firing the CLI, scan `<WIKI_PATH>/active/<slug>/reviews/` for a file matching `*-code-review-{batch_name}-r{N}.md`. If found, treat it as this round's review file — parse its verdict from the fenced yaml block (via `_review_common.parse_verdict` on the file content) and skip to step 4 below. This covers the case where mill-go crashed after writing the review but before committing state.

2. Invoke:

   ```bash
   python plugins/mill/scripts/millpy-review-code.py --batch <batch_name> \
       [--extra-file <p> ...]
   ```

   The CLI prints one JSON line `{"type":"code","round":N,"verdict":"...","reviews":[...]}`.

3. **Before reading any review file, load the `mill-receiving-review` skill.** Non-negotiable.

4. Branch on verdict:
   - `APPROVE` — batch state → `approved`, `review_file: <path>`. `_status.append_phase(..., f"approved-{batch_name}")`. Commit+push. Break out of the loop → next batch.
   - `NEED_CONTEXT` — read the `## Missing context` bullets from the review file. For each listed path, if it exists under the worktree, append to `extra_files` for the NEXT round. `_notify.notify("mill-go.review-need-context", f"batch {batch_name} round {N}", slug=slug, files=len(missing))`. Record this gap for mill-self-report (see Handoff). Increment round and continue the loop. If ALL the missing files are paths already in `extra_files` from a prior round (no new info), treat as a stuck-logic failure and break.
   - `REQUEST_CHANGES` — set batch state → `fixing`. `_status.append_phase(..., f"fixing-{batch_name}-r{N}")`. Commit+push. **Resume the implementer session** with a new user message:

     > Load the `mill-receiving-review` skill. Read `<review-file-abs-path>`. Apply VERIFY / HARM CHECK / FIX or PUSH BACK per finding. Re-run `verify:` from the batch frontmatter. Report the same JSON shape as before, reflecting the post-fix state.

     Spawn via `_implementer_sonnet.run(fix_prompt, session_id=session_id, resume=True, cwd=project_root)`. Parse the JSON report the same way as step 2. On success → increment round, continue loop (next round's review). On stuck → escalate.

5. **Max-rounds exhaustion.** After `review.code.rounds` rounds without APPROVE: `_notify.notify("mill-go.review-exhausted", f"batch {batch_name}", slug=slug, rounds=N)`, set batch state → `blocked`, `blocked_reason: "review rounds exhausted"`, `_status.append_phase(..., "blocked")`, commit+push. Go to *Blocked* below.

### Stuck escalation

- `transient` (already retried once) → surface to user with three options: retry fresh, edit plan and retry, block. User picks.
- `verify` / `logic` → surface to user with three options: edit plan to clarify then retry fresh, skip this batch (block the task), block the task. User picks.
- On user-chosen block: set batch state → `blocked`, `blocked_reason: <reason>`, `_status.append_phase(..., "blocked")`, commit+push. Go to *Blocked*.

### Blocked

- `_notify.notify("mill-go.blocked", f"batch {batch_name}: {blocked_reason}", slug=slug, batch=batch_name)`.
- Release the builder lock: `_builder_lock.release(mill_dir)`.
- Tell the user: "Batch X blocked with reason Y. Inspect reviews/ and status.md. Re-run `/mill-go` after resolving, or `/mill-abandon` to wind down." Do not proceed to Handoff.

## Holistic code review

After every batch in `order` has state `approved`, and only if `review.code.holistic: true`:

- Invoke `python plugins/mill/scripts/millpy-review-code.py` (no `--batch`).
- Same review-loop mechanics as per-batch, except there is no implementer resume — on `REQUEST_CHANGES` the orchestrator is the one that must dispatch fixes to the most relevant batch's implementer session. **Simplification for v2.0:** on holistic `REQUEST_CHANGES`, do not auto-dispatch — surface the findings to the user with a two-option prompt: (A) manually fix + re-run holistic, (B) treat as approved and self-report the gap. Record the decision in status.md.
- On `NEED_CONTEXT` apply the same extra-files / notify path as per-batch.

## Handoff

- `_status.append_phase(status_path, "done", _timestamp.now_utc_iso())`.
- Flip Home.md's task line to `[done]` via `_tasks_md.set_phase(home_path, slug, "done")` — acquire the wiki shared lock first (`_wiki.acquire_lock` … `_wiki.release_lock`) since Home.md is shared across tasks.
- Commit+push the wiki change.
- `_notify.notify("mill-go.done", f"task {slug} complete", slug=slug)`.
- If `pipeline.auto_report: true` → invoke `/mill-self-report` directly with no argument. The skill checks `gh auth` itself and bails cleanly if absent. Wait for it to finish before continuing.
- If `pipeline.auto_merge: true` → invoke `/mill-merge`. Otherwise tell the user: "Task complete. Run `/mill-merge` to merge the task branch back to parent."
- Release the builder lock.

## Principles

- **Lean Builder.** You never read card bodies, diffs, or source files unless responding to a stuck-logic event on a specific batch. Your context stays small by design — this is what lets Opus be a legitimate Builder choice.
- **Implementer owns receive-review.** On `REQUEST_CHANGES` the implementer (not Builder) loads `mill-receiving-review` and applies findings. Builder passes a pointer to the review file; the implementer's warm session already knows the code.
- **Commits go through `git-commit`.** `implementer-brief.md` already instructs this, but enforce it if the implementer asks for confirmation: every per-card commit invokes the `git-commit` skill so lint + `codeguide-update` run per-commit. Batch N+1's implementer then reads a codeguide that already reflects batch N's additions.
- **One task per worktree.** The builder lock enforces this at runtime. Do not attempt to relax it.
- **Never guess when stuck.** Surface to the user with concrete options; don't invent a recovery.
- **Review files are the ground truth.** Verdict parsing reads only the fenced yaml block; the `## Findings` body is the implementer's job to read, not yours.

## Board discipline

- Home.md writes (`[done]` flip at handoff) go through `_wiki.write_commit_push` WITH the shared lock held.
- Per-task writes (`active/<slug>/status.md`, `active/<slug>/reviews/*`) go through `_wiki.write_commit_push` without the shared lock.
- Phase transitions via `_status.append_phase`; batch-state mutations via `_status.set_batch_field`. Hand-editing either block is banned.
