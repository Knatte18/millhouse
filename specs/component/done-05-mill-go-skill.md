# mill-go (skill)

```yaml
type: skill
layer: 03
v1_ref: plugins/mill/skills/mill-go/
status: done — merged to main 2026-04-22 (branch impl/05-mill-go)
note: "Lean Builder/orchestrator. Runs on Sonnet. Reads the batch DAG from 00-overview.md; never reads batch files or cards. Spawns one implementer Sonnet per batch, reuses its session across code-review → fix cycles, merges when the last batch approves."
```

## Implementation notes

Shipped as `plugins/mill/skills/mill-go/SKILL.md` + `templates/implementer-brief.md`. Also delivered a substantial Layer-02 re-work and infrastructure pieces that mill-go needs.

**Major design changes vs. spec:**
- **Code-review no longer diffs git.** Per user directive during discussion: `_review_code.py` now reads the plan's overview + the named batch file + every source file listed under that batch's `Reads:`/`Modifies:`/`Creates:`. No `git diff`. No per-batch `start_sha..HEAD` logic — plan content is the ground truth. `mill-review-code.py` gained `--batch <name>` + `--extra-file <path>` (repeatable).
- **NEED_CONTEXT verdict added.** Reviewers are forbidden from guessing file contents; if they need a file not in the bulk, they emit `verdict: NEED_CONTEXT` with a `## Missing context` list. Orchestrator re-fires with `--extra-file` for each listed path, and records the gap for self-report. Added to every review template + `_review_common.parse_verdict` + `aggregate_verdict` (propagates up) + `review-output.schema.md`.
- **Old review-code templates dropped.** `review-code-single.md` + `review-code-multi.md` deleted; replaced with `review-code-batch.md` (per-batch) + `review-code-holistic.md` (end-of-task). `review.code.style` config key dropped.
- **"batches:" section lives in its own fenced-yaml block** under `## Batches` in status.md, not inside the top yaml block — the top block holds `task_description: |` block scalars and round-tripping through `yaml.safe_dump` would collapse them. Spec's schema showed `batches:` in the top block; the user-visible shape is the same list of entries, just under a dedicated heading.
- **Stuck taxonomy simplified to two paths** (option B from discussion): `transient` → one silent auto-retry, then ask user. Anything else (`verify`/`logic`/malformed JSON) → ask user immediately with three options.
- **Parallelism postponed.** v2.0 is strictly sequential; parallelism is a future additive backlog item per discussion.

**New helpers in plugins/mill/scripts/:**
- `_builder_lock.py` — per-worktree mutex (5-min stale window, no PID).
- `_notify.py` + `_notify_stdout.py` — pluggable notification API; stdout backend ships as default; future backends drop-in via `notify.backend:` config.
- `_plan_dag.topo_order()` added alongside the existing `validate()`.
- `_status.py` gained `init_batches`, `set_batch_field`, `read_batches`.
- `_review_common.parse_batch_refs` + `resolve_ref_paths` promoted from `_review_plan` internals to shared helpers.

**Config additions (wiki/config.yaml):**
- `pipeline.builder`, `pipeline.implementer`, `pipeline.auto_merge`, `pipeline.auto_report`.
- `review.code.holistic: true` (default on, user-confirmed).
- `review.code.self_fix_rounds: 2`.
- `notify.backend: stdout`.
- `llm.implementer_timeout` bumped from 1800 → 3600s per user.

**Tests:** `integration_tests/test-go-assets.py` covers the refactored `_review_code.run` end-to-end against a stub reviewer (no real LLM call), plus `implementer-brief.md` rendering, `_notify` dispatch, `_builder_lock` conflict detection, and `_status` batches round-trip. Existing `test-plan-assets.py` and `test-spawn.py` still pass after the shared-helper move.

**Deliberately not shipped in 05:**
- No full mill-go → real implementer → real reviewer E2E test (would burn real tokens). The skill itself will be exercised the first time a real task runs through mill-go.
- `--extra-file` not added to `mill-review-plan.py`. Mill-plan is interactive — when plan-review returns NEED_CONTEXT, the user fixes the batch's `Reads:` list and re-runs; no CLI-level extra-file needed.
- No `mill-receiving-review` auto-dispatch on holistic `REQUEST_CHANGES`. Surfaces to user with two options instead (A: manual fix + re-run, B: treat as approved + self-report). Simpler for v2.0.

**Also updated:**
- `plugins/mill/skills/mill-self-report/SKILL.md` — config key renamed from `notifications.auto-report.enabled` → `pipeline.auto_report`.
- `plugins/mill/skills/mill-plan/SKILL.md` — handoff now auto-fires `/mill-self-report` when `pipeline.auto_report` is true.

## Purpose

Execute an approved plan. Schedule batches per the DAG in `00-overview.md`, spawn one implementer per batch, run code review after each batch, let the same implementer session receive-review and fix on `REQUEST_CHANGES`. Mark the task `[done]` on success; block with notification on failure.

## Role split (vs. v1)

- **Builder (this skill)** — coordination + state only. Reads `status.md` and `00-overview.md`'s Batch Index DAG. Never reads batch files, card bodies, or the diff. Small context, cheap to run.
- **Implementer (spawned per batch)** — reads its own batch file + `00-overview.md` shared decisions + `Reads:` source files. Implements cards sequentially inside the batch, runs `verify:`, self-fixes verify failures.
- **Escalation only** — Builder reads plan content *only* when an implementer reports "stuck" and the orchestrator must decide: retry, ask user, or block.

## Decisions

- **Builder model**: Sonnet (default). Config override: `pipeline.builder: sonnet | sonnet-fast | opus`. Opus is a legitimate choice for Builder *because* Builder's context stays lean — it normally holds only `status.md` + the Batch Index DAG + orchestration metadata, never plan content. Opus-as-Builder is cheap in practice (few tokens per orchestration call) and pays off the one time it matters: resolving an implementer-stuck event with maximum decision quality. Sonnet is the default because pure scheduling rarely needs Opus-level thinking.
- **Implementer model**: Sonnet (default). Config override: `pipeline.implementer: sonnet | sonnet-fast | opus`. A batch can pin its own implementer via frontmatter `implementer:` (overrides config).
- **Entry phase gate**: `status.md phase:` must be `planned` (plan approved). Fallbacks:
  - `implementing`/`reviewing`/`fixing` → resume (see *Resume semantics*).
  - `blocked` → surface `blocked_reason:` and stop.
  - `discussed`/`discussing`/`planning` → tell user to finish `mill-plan`.
  - `done` → tell user the task is complete.
- **Slug lookup**: `.millhouse/active.slug.md` (same rule as mill-start/mill-plan). Never touch `.active/` or the wiki junction as path — resolve via `<WIKI_PATH>`.
- **Sequential batch execution in v2.0**: the DAG's `depends-on:` is respected for ordering but batches run one at a time. Parallel execution is a future extension — purely additive. See *Out of scope*.
- **Builder lock**: `.millhouse/builder.lock` (same mechanism as v1). Prevents double-spawn when the user restarts mill-go mid-run. Stale lock (older than 5 min) is overwritten.
- **Who reads what (lean-Builder invariant)**:
  - **Builder reads**: `status.md`, `00-overview.md`'s Batch Index DAG, and — from each code-review file — **only the fenced ```yaml verdict block**. The `## Findings` section is never read by Builder.
  - **Implementer reads**: its own batch file, `00-overview.md`'s Shared Decisions section, and source files listed under `Reads:` / `Modifies:` / `Creates:`. On `REQUEST_CHANGES`, the implementer is the one that loads the `mill-receiving-review` skill, reads the review file (findings included), applies VERIFY / HARM CHECK / FIX-or-PUSH-BACK, and fixes.
  - **Builder reads plan content** only on an implementer-stuck event, and only the relevant slice: the stuck batch's `NN-<batch>.md` file + `00-overview.md`'s Shared Decisions section. Never other batches, never other cards.
- **Session reuse per batch (see `01-llm-session-id`)**:
  1. Implementer spawned with a caller-generated session id (UUID). Implements cards + runs `verify:`. Reports `{success | stuck, commit_sha, session_id}`.
  2. Builder kicks off `mill-review-code.py` (separate thread, bulk reviewer). Parses verdict from the review file's fenced yaml block.
  3. If `APPROVE`: session closed, move on.
  4. If `REQUEST_CHANGES`: Builder **resumes** the implementer session with `"Load mill-receiving-review. Read <review-file>. Apply VERIFY / HARM CHECK / FIX-or-PUSH-BACK per finding. Re-run verify. Report {success | stuck}."`. Implementer's context still has the code it just wrote; no plan re-read.
  5. Loop until APPROVE or `review.code.rounds` exhausted.
- **Batch state persistence**: `status.md` YAML block carries a `batches:` list. Per batch: `name`, `state` (pending/running/reviewing/approved/blocked), `implementer_session`, `commit_sha`, `review_round`. Builder restart reads this to resume cleanly.
- **Stuck handling**:
  1. Implementer reports `stuck` with a short reason.
  2. Builder reads the stuck batch's file + `00-overview.md`'s Shared Decisions for the first time.
  3. Builder decides per policy:
     - Obvious retry (e.g. transient tool failure): new implementer session, fresh prompt.
     - Ambiguous: ask user with 2-3 options (retry, modify plan, skip batch, block).
     - Hard failure (verify still fails after N rounds): notify + block.
- **Verify handling per batch**: Implementer runs `verify:` once all cards in the batch are done. If it fails, implementer tries to self-fix in the same session. If it still fails after `verify.max-self-fix-rounds` (default 2), implementer reports `stuck`.
- **On last-batch APPROVE**: Builder writes `[done]` in Home.md (one commit via `_wiki.write_commit_push`), sets `status.md phase: done`, releases the builder lock, tells user to run `mill-merge` (next skill).
- **mill-go does NOT invoke mill-merge**: handoff is explicit. Matches v1.

## Flow

1. `wiki.sync_pull(cfg)` + entry phase gate.
2. Acquire builder lock.
3. Read `00-overview.md`'s Batch Index DAG. Compute topological order of batches.
4. Initialise `status.md batches:` list (first run) or read existing (resume).
5. For each batch in topological order:
   a. Build implementer prompt (pointer to batch file + overview, not inlined content). Generate session UUID.
   b. Spawn implementer (new session). Monitor until it reports success or stuck.
   c. On stuck → escalation policy (see Decisions — Builder now reads the stuck batch's plan file for the first time).
   d. Run `mill-review-code.py` against the batch's commit range.
   e. Read **only the fenced yaml verdict block** from the review file.
   f. If APPROVE → update batch state `approved`, move on.
   g. If REQUEST_CHANGES → resume implementer session with a review-file pointer and the receiving-review instruction (the implementer loads the skill and reads the findings, not Builder). Loop up to `review.code.rounds`. On exhaustion → notify + block.
6. After all batches approved: `phase: done`, Home.md `[done]`, release lock, tell user to run `mill-merge`.

## Backend

**New / to add:**
- `_llm_claude.run_implementer(...)` — from `01-llm-session-id` spec. Grants Read/Edit/Write/Bash/Grep/Glob tools. Returns `(output, session_id)`.
- `_builder_lock.py` — tiny wrapper around `.millhouse/builder.lock` (atomic create/check/release with stale timeout). Could also live in `_wiki.py` if we don't want a new file.
- `_status.py` — already planned (mill-spawn/mill-start/mill-plan). Gains `update_batch_state(...)` for the `batches:` list.
- `_dag.py` — topological sort of the Batch Index. Tiny (~40 LOC) — accept a dict of `name → depends-on`, detect cycles, return a flat execution order. Cycle detection also useful for plan-review.

**Reused / already exists:**
- `mill-review-code.py` — invoked as subprocess.
- `_review_common.parse_verdict` — verdict parsing.
- `_wiki.py` — sync_pull, lock, write_commit_push.
- `_active.py` (planned) — slug lookup.
- `_tasks_md.py` (planned) — Home.md `[active]` → `[done]` write.
- `mill-receiving-review` skill (already present).

## Status.md shape (extended)

```yaml
task: <task-title>
slug: <slug>
phase: planned | implementing | reviewing | fixing | done | blocked
started: <UTC YYYYMMDD-HHMMSS>
blocked_reason: <string, only when phase: blocked>

plan_start_hash: <sha>      # set by mill-go at entry; stale-plan detection

batches:
  - name: foundation
    state: approved          # pending | running | reviewing | fixing | approved | blocked
    implementer_session: <uuid>
    commit_sha: <sha>
    review_round: 1
  - name: reviewers
    state: running
    implementer_session: <uuid>
```

## Resume semantics

- `phase: implementing` + `batches[i].state: running` → skip to batch i, resume its implementer session if it exists, else respawn.
- `phase: reviewing` + `batches[i].state: reviewing` → re-run review for batch i (idempotent since review files are round-numbered).
- `phase: fixing` + `batches[i].state: fixing` → resume session, continue the fix loop from the next round.
- `phase: blocked` → always stop; user must inspect `blocked_reason` and decide.

## Out of scope vs v1

- No DAG/card-level implementer scheduling. Batch-level only.
- No per-card implementer spawn (token sloss); one implementer per batch, many cards per session.
- No parallel batch execution in v2.0. Sequential respecting `depends-on:`. Future: additive scheduler that spawns N independent batches at once when their deps are satisfied.
- No `mill-self-report` auto-fire (can be invoked manually).
- No pre-arm wait phase — mill-plan is synchronous, mill-go never runs concurrently with a planner.

## Open design points

- **Session resume is a hard prerequisite**: the entire mill-go flow depends on `claude -p --resume <id>` actually carrying context across turns for the implementer session. Verify this end-to-end in the `01-llm-session-id` work BEFORE mill-go implementation begins; if resume silently drops context or expires too fast, the receiving-review delegation falls apart and the Builder/implementer split must be rethought. No amount of spec clarity compensates for a broken resume.
- **Builder lock shape**: reuse v1's plain lockfile (PID + timestamp) or integrate with `_wiki.py`'s lock? PID check on Windows is fiddly.
- **Stuck escalation policy taxonomy**: what exactly constitutes "obvious retry" vs "ask user" vs "block"? Needs a finite rule list, not a vibe.
- **Code-review scope per batch**: does `mill-review-code.py` diff from merge-base-main or from the batch's start commit? For per-batch review we want only the batch's changes — needs a new flag (`--since <sha>`) or the backend must be taught about `batches[].start_sha`.
- **Final holistic code review**: v1 ran a final holistic review after all cards. Skip in v2? Keep as opt-in via config (`review.code.holistic: true`)?
- **Implementer tool budget**: exact allowedTools list. Write + Edit + Bash + Read/Grep/Glob for sure; TodoWrite maybe; WebFetch/WebSearch never.
- **Self-fix round cap**: default 2 makes sense; config override via `review.code.self-fix-rounds`? Or hardcode?
- **Timeouts**: per-implementer max wall-time? v1 had 14400s pre-arm timeout but no implementer timeout. Needs a sane default (e.g. 60 min per batch) with config override.
- **Notifications**: whether to re-introduce v1's `notify` entrypoint or leave blocked-state reporting as stdout-only.
- **Home.md `[done]` vs `[completed]`**: v1 used both markers inconsistently. v2 should pick one — I suggest `[done]`. Confirm.
- **Crash during review round**: if mill-go dies after code-review fires but before verdict is parsed, resume must find the just-written review file and use it rather than firing a new review. Needs a round-aware recovery test.
