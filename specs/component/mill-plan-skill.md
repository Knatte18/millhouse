# mill-plan (skill)

```yaml
type: skill
layer: 03
v1_ref: plugins/mill/skills/mill-plan/ + doc/prompts/plan-review.md + doc/formats/plan.md
status: partially discussed — key decisions captured, not ready for full-write
note: "Autonomous planner. Runs on Opus in a task-worktree after mill-start. Writes batch-based plan files, self-reviews via mill-review-plan, self-corrects via mill-receiving-review. Hands off to mill-go."
```

**For the thread that will do the full-write:** these notes are *starting points*, not a finished spec. Grill Henrik further on edge cases before writing. v1's mill-plan is the strongest reference and most phases transfer. Known underspecified areas are listed in *Open design points*.

## Purpose

Read `discussion.md` and write a batch-based implementation plan detailed enough that a Sonnet-class builder can execute it autonomously. Review the plan, self-correct on `REQUEST_CHANGES`, and hand off to mill-go once approved.

## Decisions

- **Model**: Opus (massive planning context; detail quality is the whole value prop).
- **Autonomous**: Never pauses mid-phase to ask the user. Same discipline as v1.
- **Plan is batch-based**, not card-based:
  - A **batch** = a coherent chunk sized for Sonnet (~200k context window) to implement in one go.
  - **Cards are logical sub-sections inside a batch file** — `### Card N`, each with `Reads:/Modifies:/Creates:/Requirements:/Commit:` fields — but they are NOT separate files, and NOT the unit of implementation. This avoids the v1 tangle where cards across files had cross-dependencies that forced implementers to re-batch anyway.
  - One verify command per batch (runs after all cards in the batch are implemented). Sonnet is expected to self-fix on verify failure.
- **Plan files layout** at `<WIKI_PATH>/active/<slug>/plan/`:
  - `00-overview.md` — frontmatter + **Batch Index DAG** (each batch with `depends-on:` + `verify:`) + shared decisions + total file-touch list.
  - `NN-<batch-slug>.md` for each batch (numbered `01-`, `02-`, ...). Contains batch scope + cards within + batch tests.
- **Batch-level DAG for parallelism**: the Batch Index in `00-overview.md` is a fenced yaml block listing every batch with `depends-on:` (list of batch names). Batches with no unresolved dependencies can be implemented in parallel by mill-go. This is coarser than v1's per-card DAG — a proven size that does NOT tangle.
- **Batch tests**: every batch SHOULD carry a `verify:` command exercising the batch's surface (where repo type supports it — some repos may have no meaningful batch test and fall back to the overview's repo-wide `verify:`). Sonnet runs `verify:` after implementing all cards in the batch; failure → Sonnet self-fixes in the same session.
- **Slug lookup**: same rule as mill-start — read `.millhouse/active.slug.md`. Never touch `.active/` or the wiki junction as path.
- **Entry phase check**: read `<WIKI_PATH>/active/<slug>/status.md`. Expected `phase: discussed`. Fallbacks per v1 (already-planned → tell user to run mill-go; not-discussed → tell user to run mill-start).
- **Review integration**: Invoke `mill-review-plan.py` CLI as subprocess (same pattern as mill-start/discussion). Parse verdict via `_review_common.parse_verdict`. Load `mill-receiving-review` skill before reading any review output.
- **Review loop**:
  - On `APPROVE` — set `approved: true` in `00-overview.md` frontmatter, commit+push, proceed to Handoff.
  - On `REQUEST_CHANGES` — invoke `mill-receiving-review`, apply VERIFY/HARM CHECK/FIX-or-PUSH-BACK per finding, write fixer report, re-invoke reviewer with updated plan only.
  - **No `-pr N` flag** — use `review.plan.rounds` from config (default 3).
  - **Max-rounds escape (v2 change vs v1)**: when max rounds exhausted with BLOCKINGs remaining, **stop and ask the user** with concrete suggestions:
    > "After {N} rounds, {M} BLOCKING findings remain unresolved. Options:
    > A) Deep problems — rethink approach. Go back to mill-start and revise discussion.
    > B) Shallow — one more review round.
    > C) Override — accept findings and proceed to mill-go anyway.
    > Recommended: {A/B/C} based on {analysis of remaining findings}."
    
    Replaces v1's hard block. (Non-progress detection still causes hard block.)
- **Non-progress detection**: carry over from v1 — if pushed-back findings in the current fixer report are identical to the previous round's pushed-back findings, halt with `BLOCKED: Plan review non-progress` and notify.
- **Fixer report format**: keep v1 verbatim — `<ts>-plan-fix-r<N>.md` with `## Fixed` and `## Pushed Back` sections.
- **Status transitions via `_status.py`**:
  - After writing plan: add `plan: active/<slug>/plan` field to status.md (not a phase change, use Edit).
  - After each review round: `append_phase("plan-review-r<N>")` or `append_phase("plan-fix-r<N>")`.
  - After approval: `append_phase("planned")`.
- **mill-receiving-review skill load**: mandatory before reading any review output (same discipline as mill-start).

## Flow

1. `wiki.sync_pull(cfg)`.
2. Read slug from `.millhouse/active.slug.md`.
3. Entry check — status.md phase. Handle re-entry (partially-written plan) via overview frontmatter `approved:` field.
4. Read discussion.md.
5. Phase: Plan — write `00-overview.md` + `NN-<batch>.md` files. Add `plan:` pointer to status.md. Commit+push.
6. Phase: Plan Review loop (up to `review.plan.rounds`):
   a. Invoke `mill-review-plan.py`.
   b. Load `mill-receiving-review` skill.
   c. Read review output.
   d. If APPROVE → set `approved: true`, break loop.
   e. If REQUEST_CHANGES → apply VERIFY/HARM CHECK/FIX, write fixer report, re-loop.
   f. Non-progress check between rounds.
   g. On max-rounds exhaustion → ask user with suggestions (see Decisions).
7. Phase: Handoff — `append_phase("planned")`. Tell user to run mill-go.

## Backend

**New / to add:**
- `_status.py` — already planned for mill-spawn/mill-start. Needed here for `append_phase` + `update_field` (plan pointer, approved flag).

**Reused / already exists:**
- `mill-review-plan.py` — invoked as subprocess.
- `_review_common.parse_verdict` — verdict parsing.
- `_constraints.read_if_exists` — already planned for mill-start.
- `_wiki.py` — sync_pull, write_commit_push.
- `_active.py` (planned with mill-start) — slug lookup.

## Templates

- **No new templates from mill-plan itself**. Plan-writing is interactive Claude reasoning, not template rendering. However, consider:
  - `templates/plan-overview.md` — skeleton for `00-overview.md` with fenced yaml frontmatter (`task:`, `slug:`, `approved: false`, `started: <timestamp>`, `root: <prefix>`, `verify: <cmd>`) + empty `## Batch Index`, `## Shared Decisions`, `## All Files Touched` sections.
  - `templates/plan-batch.md` — skeleton for `NN-<batch>.md` with frontmatter (`batch: <name>`, `cards: <count>`, `verify: <cmd>`) + empty `## Batch Scope`, `## Cards` sections.
  - Both are optional conveniences — the skill may write from scratch if preferred.

## Plan frontmatter (minimum)

`00-overview.md` frontmatter:
```yaml
task: <task-title>
slug: <slug>
approved: false        # flipped to true on APPROVE verdict
started: <UTC YYYYMMDD-HHMMSS>    # from shell `date -u` — never guess
root: <prefix>         # repo branch prefix, e.g. "hanf" or empty
verify: <repo-wide verify cmd>    # optional; per-batch verify is primary
```

`00-overview.md` also contains a **Batch Index DAG** (fenced yaml block, separate from frontmatter):
```yaml
batches:
  - name: foundation
    file: 01-foundation.md
    depends-on: []
    verify: pytest tests/foundation/ -q
  - name: reviewers
    file: 02-reviewers.md
    depends-on: [foundation]
    verify: pytest tests/reviewers/ -q
  - name: templates
    file: 03-templates.md
    depends-on: [foundation]
    verify: null             # no meaningful batch test
  - name: integration
    file: 04-integration.md
    depends-on: [reviewers, templates]
    verify: pytest tests/integration/ -q
```

Two batches with the same unresolved dependencies are parallelizable. mill-go reads this block to build its execution schedule.

`NN-<batch>.md` frontmatter:
```yaml
batch: <batch-name>
cards: <count>
verify: <batch-specific verify cmd | null>   # same command repeated from overview
depends-on: [<other-batch-names>]            # mirrors overview; authoritative here
```

## Card fields (inside batch files, per `### Card N` subsection)

- `Reads:` — files the implementer reads (non-empty, comprehensive).
- `Modifies:` / `Creates:` — files touched.
- `Requirements:` — what the card must achieve (prose).
- `Commit:` — suggested commit message.

## Out of scope vs v1

- No per-card files (`card-NN-*.md`). Cards are sections inside batch files.
- No per-card DAG. Batch-level DAG only — coarser and stable.
- No `-pr N` flag.
- No hard-block on max-rounds-exhaustion — user gets an escape hatch.
- No `spawn_reviewer` / `millpy.entrypoints.*` — CLI-direct.
- No `mill-self-report` auto-fire (not in scope for v2 baseline).

## Open design points

- **Timestamp safety**: Claude Code often guesses timestamps. Skill MUST use shell `date -u +%Y%m%d-%H%M%S` via Bash for `started:` and fixer-report filenames. Consider a `_timestamp.py` helper or explicit instruction in SKILL.md.
- **Batch sizing heuristic**: how does the planner decide what goes into one batch? Token-count rule (~X tokens of implementer context)? Number of files? Logical cohesion? Needs guidance in the SKILL.md to produce consistent plans.
- **Verify per batch**: command form + failure handling. Is there a standard `verify:` shape (pytest -k batch, make test-batch, custom)? When no meaningful batch test exists (e.g. pure docs batch), `verify: null` — no hard block from missing verify.
- **Batch DAG cycles**: plan-review MUST reject any plan whose Batch Index contains a cycle. Ensure the plan-review template or a pre-handoff validator catches this.
- **Re-entry correctness**: when mill-plan re-enters after a partial write, exactly what state triggers what action. v1 had `approved: false` → re-enter Plan Review. Confirm this state machine.
- **User-prompt UX at max-rounds**: exact wording of the escape-hatch prompt, how suggestions are formed from remaining findings.
- **Fixer-report commit granularity**: one commit per round or one after all rounds?
- **Opus-as-planner cost/latency budget**: is there a hard cap on plan-writing time? v1 had none.
