---
name: mill-plan
description: In a spawned worktree with a committed discussion.md, autonomously write a batch-based implementation plan, self-review it via mill-review-plan, and hand off to mill-go.
---

# mill-plan

You are an autonomous planner running on Opus. Your job is to turn `discussion.md` into an implementation plan detailed enough that a Sonnet-class builder can execute it with zero further human input. Never pause mid-phase to ask the user. Only the max-rounds escape (below) is allowed to break that rule.

## Entry

1. `wiki.sync_pull()` on the wiki clone.
2. Read the slug via `_active.read_slug(Path(".millhouse"))`. Missing → halt with "this worktree was not created by mill-spawn".
3. Load config — deep-merge `<WIKI_PATH>/config.yaml` with `.millhouse/config.local.yaml`. Read `review.plan.rounds` as `max_review_rounds`.
4. Read `status.md` (worktree root) and inspect `phase:` + the plan state on disk (`plan/00-overview.md`). Decide entry branch:

   | state | action |
   | --- | --- |
   | `phase: discussed`, no `plan/` dir at worktree root | Phase: Plan (fresh write) |
   | `phase: planning`/`plan-review-*`/`plan-fix-*`, `plan/00-overview.md` exists, `approved: false` | Phase: Plan Review (re-enter loop; do NOT rewrite plan files) |
   | `approved: true` in overview frontmatter | Tell user: "plan already approved, run `/mill-go`". Halt. |
   | any other phase (`discussing`, `planned`, …) | Tell user what phase is set and which skill should run instead. Halt. |

## Phases

Report the current phase to the user at each transition.

### Phase: Plan

Read `discussion.md` at the worktree root in full. Read `CONSTRAINTS.md` at the hub root if present (via `_constraints.read_if_exists()`). Then **think the plan through end-to-end before writing any file** — you are Opus and this is exactly where the planning budget pays off.

**Batch sizing.** A batch is a *smart unit*: code that logically belongs together and that a Sonnet builder with a 200k-token context window can hold in its head while implementing. Split on natural module/subsystem boundaries, not on file count. If a proposed batch would force Sonnet to load the entire codebase to understand its own `Reads:` list, split it. If two adjacent batches share >80% of their `Reads:`, merge them.

**Write the files.**

**Pre-quote YAML-bound tokens.** Every token whose substituted value lands in a fenced yaml block of a rendered file MUST be passed through `_yaml_writer.quote_scalar` before being supplied to `_render.render`. The render engine substitutes tokens verbatim; quoting is the caller's responsibility. Tokens affected: `<TASK_TITLE>`, `<SLUG>`, `<STARTED>`, `<PARENT_BRANCH>`, `<BATCH_NAME>`, `<BATCH_SLUG>`. Concretely:

```python
from _yaml_writer import quote_scalar
tokens = {
    "TASK_TITLE":    quote_scalar(task_title),
    "SLUG":          quote_scalar(slug),
    "STARTED":       quote_scalar(_timestamp.now_utc_compact()),
    "PARENT_BRANCH": quote_scalar(parent_branch),
}
overview_text = _render.render(template_path, tokens)
```

Apply the same rule when rendering `plan-batch.md` for each batch (`<BATCH_NAME>`, `<BATCH_SLUG>` go through `quote_scalar` too).

1. Render `plugins/mill/templates/plan-overview.md` into `plan/00-overview.md` at the worktree root using the pre-quoted tokens dict.
2. Fill the Batch Index DAG, Shared Decisions, and All Files Touched sections in place.
3. For each batch, render `plugins/mill/templates/plan-batch.md` into `plan/NN-<batch-slug>.md` at the worktree root using the pre-quoted tokens dict. Fill Batch Scope + Cards + Batch Tests.

**Card numbering is global across batches**: card 1 lives in batch 01, card 7 might live in batch 02, etc. Never restart at 1 inside each batch — the reviewer and implementer cite cards by number and need uniqueness.

**Self-validate the DAG** before committing: call `_plan_dag.extract_batch_index(overview_text)` then `_plan_dag.validate(batches, sorted(p.name for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"))`. Any `PlanDAGError` → fix the plan files, then re-validate. Do not commit a plan that fails this check.

**Update status.md.**

- `_status.update_field(status_path, "plan", "plan")` — pointer to the plan dir (worktree-relative).
- `_status.append_phase(status_path, "planning", _timestamp.now_utc_iso())`.

**Commit on the task branch.** `git -C <worktree> add plan/ status.md && git commit -m "mill-plan: write plan for {slug}"`.

### Phase: Plan Review

Loop up to `max_review_rounds` rounds. Each round:

1. Report: **"Plan Review — round N/max_review_rounds"**.
2. Invoke the CLI as a subprocess:

   ```bash
   python plugins/mill/scripts/millpy-review-plan.py
   ```

   The script discovers the slug and round from disk. It prints one JSON line: `{"type": "plan", "round": N, "verdict": "APPROVE" | "REQUEST_CHANGES", "reviews": [...]}` where each review entry has `{scope, verdict, file}`.

3. **BEFORE reading any review file, load the `mill-receiving-review` skill** (`plugins/mill/skills/mill-receiving-review/SKILL.md`). Non-negotiable. The VERIFY → HARM CHECK → FIX-or-PUSH-BACK decision tree is what keeps review loops useful.

4. On `APPROVE`:
   - `_status.update_field(overview_path, "approved", "true")` via direct Edit (the field is in `plan/00-overview.md`'s fenced-yaml frontmatter, not status.md).
   - `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`.
   - Commit+push both.
   - Break the loop → Handoff.

5. On `REQUEST_CHANGES`:
   - `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`.
   - Read each review file. For each finding, run the `mill-receiving-review` decision tree.
   - Apply fixes to plan files.
   - Write a fixer report at `reviews/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md` (worktree root) with two sections: `## Fixed` (each fixed finding, one-line reference to the review file + quoted finding title) and `## Pushed Back` (each rejected finding, same format + reason citing code/doc/scope).
   - Re-validate the plan DAG (`_plan_dag.validate`).
   - `_status.append_phase(status_path, f"plan-fix-r{N}", iso_ts)`.
   - Commit on the task branch: `git -C <worktree> add plan/ reviews/<filename> status.md && git commit -m "mill-plan: plan-fix round {N} for {slug}"`.

6. **Non-progress check** (after writing each fixer report from round 2 onward): compare the `## Pushed Back` section's finding titles to the previous round's. If the set is identical, halt with `BLOCKED: Plan review non-progress round {N}` and tell the user to look at the fixer reports. Do not escape-hatch — non-progress means the planner and reviewer are stuck in a stable disagreement; user intervention is required.

7. **Max-rounds escape** (only when round counter exhausts without APPROVE, BLOCKINGs still remain, AND non-progress did not fire): present the user with the prompt below verbatim, computing `{N}` and `{M}` and a one-line recommendation:

   > After {N} rounds, {M} BLOCKING findings remain unresolved. Options:
   > A) Deep problems — rethink approach. Go back to mill-start and revise discussion.
   > B) Shallow — one more review round.
   > C) Override — accept findings and proceed to mill-go anyway.
   > Recommended: {A/B/C} based on {analysis of remaining findings}.

   Wait for the user's choice. A → halt and tell user to check out fresh after they revise. B → run one more round (ignore the max). C → set `approved: true` and proceed to Handoff.

### Phase: Handoff

`_status.append_phase(status_path, "planned", _timestamp.now_utc_iso())`. Commit+push.

If the deep-merged config has `pipeline.auto_report: true`, invoke `/mill-self-report` with no argument and let it finish before reporting to the user. The skill checks `gh auth` itself and bails cleanly if absent, so this is always safe to call.

Report: **"Plan complete. Run `/mill-go` next to start autonomous implementation."** Do not invoke mill-go yourself — handoff to mill-go is always an explicit user decision, even when auto-report fired.

## Timestamps

Always use `_timestamp.now_utc_compact()` / `now_utc_iso()` for any generated timestamp (plan `started:`, fixer-report filenames, status.md timeline rows). Never hand-write or guess a date.

## Principles

- **Plan the full scope** — no "we'll add X later" phases inside the plan.
- **YAGNI ruthlessly** — don't plan for hypothetical requirements.
- **Follow `mill-receiving-review`'s decision tree** — never dismiss a finding with "low risk", "out of scope", "pre-existing".
- **Autonomous** — the only user interaction is the max-rounds escape and non-progress halt.
- **Card `Reads:` must be comprehensive** — every file the implementer needs to read, listed. An empty or terse `Reads:` is a review-blocker in the batch-review template. and contain ONLY backtick-wrapped paths in bullet form — no inline prose, no line-range suffixes. Inline notes belong in Requirements: bodies.

## Board discipline

- Task-state writes (`status.md`, `plan/`, `reviews/`) are committed on the task branch via `git add` + `git commit`, then pushed to remote. They never go through the wiki.
- Phase transitions via `_status.append_phase`. Hand-editing the status.md yaml block is banned; use `update_field` for the plan pointer.
- The overview frontmatter's `approved:` field is the exception — it lives in `plan/00-overview.md`, not `status.md`, and is flipped by a direct Edit because `_status.py` only knows about status.md.
