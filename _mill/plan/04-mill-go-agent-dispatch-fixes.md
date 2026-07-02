# Batch: mill-go-agent-dispatch-fixes

```yaml
task: "Fix agent-mode dispatch races and pipeline gaps"
batch: mill-go-agent-dispatch-fixes
number: 4
cards: 3
verify: null
depends-on: [3]
```

## Batch Scope

Two independent `#587`/`#590` fixes land in the same file (`mill-go/SKILL.md`) and are therefore grouped into one batch to avoid a `parallel-modifies-overlap` conflict with any other batch touching this file: (1) `#587`/`#595` — add a one-shot `TaskOutput` liveness probe to `## Agent-mode dispatch` step 4 before treating a stopped/interrupted reviewer or fixer notification as terminal-transient, and reword the three other places the file currently asserts stopped/interrupted is unconditionally terminal so nothing contradicts step 4's new behavior; (2) `#590` — add a new pre-flight step that invokes `millpy-implement.py --stage baseline` once before the task's first batch implementer is ever dispatched. Depends on batch 3 (`--stage baseline` must exist for the new pre-flight step to invoke a real CLI). `verify: null` — this batch is a pure `SKILL.md` prose change with no runnable surface; see Batch Tests.

## Cards

### Card 8: reword the three stale "stopped/interrupted is unconditionally terminal" statements

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Reword three sentences so none of them assert stopped/interrupted is unconditionally terminal-transient once Card 9 adds the probe-first branch to step 4:
  - `mill-go/SKILL.md:125` currently reads: "A background agent is a **detached worker** that can be stopped or interrupted independently of the orchestrator. If the `<task-notification>` indicates the subagent was stopped or interrupted (rather than completing normally), treat it the same as a raw API error and apply the one-retry transient path in step 4." Reword the second sentence to something like: "If the `<task-notification>` indicates the subagent was stopped or interrupted (rather than completing normally), route it through step 4's recovery paths below — implementer notifications go through the existing clean-mid-work-stop / `incomplete` routing; reviewer and fixer notifications are checked with a one-shot liveness probe before being treated as terminal."
  - `mill-go/SKILL.md:156` (an "Agent-mode properties" bullet) currently reads: "A background agent IS a detached worker and CAN be stopped or interrupted. A stopped/interrupted agent produces a notification indicating it did not complete normally — handle that the same as a raw API error via the one-retry transient path in step 4." Reword the second sentence to: "handle that per step 4's recovery paths below (implementer: existing clean-mid-work-stop / `incomplete` routing; reviewer/fixer: liveness-probe-then-one-retry-transient path)."
  - `mill-go/SKILL.md:158` currently reads: "The one-retry transient policy applies to both raw API errors and stopped/interrupted agents (see step 4)." Reword to: "The one-retry transient policy applies to raw API errors immediately, and to stopped/interrupted reviewer/fixer agents once step 4's liveness probe confirms the agent is no longer running (see step 4). Stopped/interrupted implementer agents are routed to the existing clean-mid-work-stop / `incomplete` recovery instead (see step 4)."

  Use the exact rationale and phrasing basis in `_mill/discussion.md`'s `stopped/interrupted-notification liveness probe (#587, #595)` Decision subsection — it already works out this exact rewording intent ("...treat that as a candidate for the one-retry transient path in step 4, after step 4's liveness probe confirms the agent is no longer running"). Do not touch any other line in this pass; Card 9 makes the actual step 4 logic change.
- **Commit:** `docs(mill-go): reword stopped/interrupted framing at steps 3 and Agent-mode properties for #587/#595`

### Card 9: step 4 liveness probe before terminal-transient classification

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `## Agent-mode dispatch` step 4 (`mill-go/SKILL.md:127-134`), split the existing single "treat stopped/interrupted the same as a raw API error" clause into two explicit sub-paths:
  1. **Raw API/infrastructure errors** (text like `API Error` / `Internal server error`, roughly 0 tokens, no `MILL_REVIEW` block and no `status` JSON): unchanged — classify as `stuck_type: transient` and re-dispatch once immediately, exactly as today.
  2. **Stopped/interrupted notification for an implementer dispatch:** unchanged — routes through the existing "Clean mid-work stop (implementer only)" path (`:129-134`) into `--stage finalize` / the `incomplete` recovery machinery (step 6.5), never through this new liveness probe. State explicitly that this carve-out exists because `finalize`'s own completeness recount already disambiguates partial-vs-dead for the implementer, making a probe redundant there.
  3. **Stopped/interrupted notification for a reviewer or fixer dispatch:** NEW — before classifying as `stuck_type: transient`, call `TaskOutput(task_id: <agentId>, block: false)` using the `agentId` retained per step 3 ("Record the `agentId` the Agent tool returns in that launch message and retain it for the duration of this batch"). Branch on the result:
     - If it reports the agent is still running: take no dispatch action this turn. Do not re-dispatch, do not classify as `stuck_type: transient`. The harness will deliver the agent's own next `<task-notification>` for the same `agentId` when it actually finishes (matches the observed `#595` behavior — the "killed" agent later delivered a real `completed` notification unprompted). Explicitly note this wait is unbounded by design, matching every other Agent-mode dispatch's existing "no log-polling or liveness check required" contract — no bounded re-check loop is added for this probe.
     - If it reports the agent is no longer running, or the probe call itself errors (the task_id is already gone): proceed to the existing one-retry transient classification and re-dispatch exactly as today.

  Write this using `_mill/discussion.md`'s `stopped/interrupted-notification liveness probe (#587, #595)` Decision and its `Bounded wait after a "running" probe` paragraph as the source of truth for exact behavior and rationale — both incidents (`#587`, `#595`) are summarized there and are useful to cite inline as the reason this probe exists (a real-world "killed"/"stopped by user" notification was stale for an agent that kept running to completion).
- **Commit:** `feat(mill-go): add TaskOutput liveness probe before reviewer/fixer transient re-dispatch (#587, #595)`

### Card 10: pre-flight baseline computation before batch 1

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new pre-flight step, run once, immediately before "### 1. Implement" (`mill-go/SKILL.md:200-219`) fires for the task's FIRST batch only (not on every batch — only once per task run). Insert it as a new numbered step before "### 1. Implement", or as a new subsection at the start of "### 1. Implement" gated on "this is the first batch of the task" (match the existing style of step "### 0. Wiki health-check" at `mill-go/SKILL.md:180-198`, which already runs once before any batch work). The step invokes:
  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" --stage baseline
  ```
  (no `batch_name` positional argument — `--stage baseline` is task-scoped, not batch-scoped, per Card 6 of batch `implement-baseline-stage`). State explicitly that this call is idempotent and safe to invoke unconditionally even on a resumed/restarted mill-go run: the `--stage baseline` handler itself checks whether `module_verify_baseline` is already cached and no-ops if so (Card 6's Requirements). Parse the JSON line the CLI prints; on `{"result": "error", ...}` or `{"result": "skipped", ...}`, log the reason and continue to batch 1 anyway (this pre-flight step never blocks the task — its only job is to populate the cache before batch 1's implementer can touch dependency manifests; a failed/skipped computation just means the per-batch module-wide gate falls back to strict behavior, which is safe).

  Cite `_mill/discussion.md`'s `baseline-aware module-wide verify gate (#590)` Decision paragraph beginning "Compute it **eagerly, once, before the task's first batch implementer is ever dispatched**" as the authoritative rationale for why this must run before batch 1 specifically (guarantees no implementer session has touched dependency manifests yet, so the transient worktree's reused dependency state is still guaranteed to match the parent branch tip).
- **Commit:** `feat(mill-go): add pre-flight module-wide verify baseline computation before batch 1 (#590)`

## Batch Tests

`verify: null` — this batch is a pure `mill-go/SKILL.md` prose change (orchestration instructions the Builder session follows, not a Python function). Per `_mill/discussion.md`'s Testing section, the liveness-probe change (Cards 8-9) has no automated test surface at all: step 4's classification lives entirely in SKILL.md prose with no Python function to stub, and `test-agent-mode-dispatch.py` only covers the prepare/finalize CLI JSON round-trip, never the harness's `<task-notification>`/`TaskOutput` layer. Validation is manual-reasoning-only: re-read the four edited sections (`:125`, `:127-134`, `:156`, `:158`, plus the new pre-flight step) end-to-end for internal consistency (no leftover "unconditionally terminal" phrasing) before committing this batch. Card 10's pre-flight step is exercised operationally the next time `mill-go` runs under Agent-mode dispatch on a task with a non-null `verify:` in its plan overview frontmatter — this task's own `mill-go` run (after this plan is approved) is that first real exercise.
