# Batch: plan-start-quick-wiring

```yaml
task: Ask the parent session when stuck (parent_thread)
batch: plan-start-quick-wiring
number: 5
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-brief-commit.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-variants.py
depends-on: [3]
```

## Batch Scope

Wires the three remaining converted sites to the `ask-parent` skill: `plan-cap` (mill-plan step 6 max-rounds escape), `start-cap` (mill-start `--auto`/`--orch` non-progress cap branch with `auto_approve_on_cap: false`) and `quick-gate` (mill-quick done-gate failure).
Each card edits one SKILL.md and reuses that skill's existing override/terminal procedures for `approve` and `retry`, so no new mechanism is introduced per site.
Every other halt in these skills stays user-only, including mill-plan's step 5 non-progress halt and every ERROR-only/usage-error/validator halt.

## Cards

### Card 12: `plan-cap` — mill-plan step 6 asks the parent before halting

- **Context:**
  - `plugins/mill/skills/ask-parent/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Phase: Plan Review, "**Path Setup (Plan Review).**" paragraph: add one sentence binding `parent_escalated_plan_cap = False` (session-local; step 6 asks the parent at most once per review loop).
  - Step 6 "**Max-rounds escape**": insert, before the _status.set_blocked call, a parent-escalation sub-step: when `parent_escalated_plan_cap` is false, set it true and load the `ask-parent` skill with site `plan-cap`, reason `f"max-rounds exhausted after {N} rounds, {M} BLOCKINGs remain"`, actions `approve,retry,halt`.
    On `approve`: run the "Live operator waiver of step 6" implicit-approve-at-cap terminal actions (direct-`Edit` `approved: true` in the plan overview, commit, push, Handoff) with commit message `mill-plan: approve plan for {slug} (parent waived remaining BLOCKINGs at round cap)`.
    State that this does not go through Entry step 4's `--approve` pre-check, whose `phase == "blocked"` / `"max-rounds exhausted"` conditions do not hold because the block is not recorded yet.
    On `retry`: apply the guidance to files under `<plan_dir>` only (the Plan Review guardrail still holds), run the same DAG re-validation and full-validate gate step 4d runs after its fixes, commit `git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: parent-guided retry for {slug}"` and push, with no `_status.append_phase` call;
    then bind `operator_max_review_rounds = <current effective cap> + 1` exactly as "Live operator-raised round-cap override" describes (its precedence over `max_review_rounds` / `local_max_review_rounds` and its `--max-rounds <operator_max_review_rounds>` threading through every prepare/finalize and Step 3.5 retry dispatch apply unchanged) and continue the loop at round N+1.
    If that extra round again ends at step 6, the escalation is spent and the halt proceeds.
    On `halt`: the existing halt, with `halt_suffix` appended to the set_blocked reason (the reason still starts with `"max-rounds exhausted"`, so the Entry `blocked` re-entry row and `--approve` keep working) and to the operator-facing halt text.
  - "**Live operator-raised round-cap override.**" paragraph: add one sentence that a parent-guided `retry` at step 6 binds this override the same way a live operator instruction does.
  - Step 2's "**Waiting is never a decision point.**" paragraph and the `## Principles` "**Autonomous**" bullet: add that step 6 may first ask the parent session via the `ask-parent` skill — a wait bounded by `pipeline.parent_escalation_timeout_minutes`, not a prompt — and still halts via _status.set_blocked when the parent does not unblock it.
  - Step 5's "Non-progress check" stays user-only: add one sentence there saying it never asks the parent (resolving a stable planner/reviewer disagreement means overruling one side, which stays the operator's call).
- **Commit:** `feat(mill-plan): ask the parent session before the max-rounds halt`

### Card 13: `start-cap` — mill-start `--auto` non-progress cap asks the parent

- **Context:**
  - `plugins/mill/skills/ask-parent/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - `## Auto mode`, "Phase: Discussion Review — `--auto` changes" list: extend the "Before the loop, initialise" bullet with `parent_escalated_start_cap: bool = False` and `parent_retry_round: int | None = None`.
  - In the same list's non-progress bullet, "**Otherwise** (`auto_approve_on_cap` is `False`, today's behavior)" branch: before the _status.set_blocked call, when `parent_escalated_start_cap` is false, set it true and load the `ask-parent` skill with site `start-cap`, reason `f"auto: discussion review gaps unresolved after {N} rounds"`, actions `approve,retry,halt`.
    On `approve`: run the same terminal actions as the `auto_approve_on_cap` `True` branch just above, with commit message `"mill-start: discussion-fix round {N} for {slug} (approved by parent)"`.
    On `retry`: apply the guidance to `<discussion_path>`, commit and push (`git -C <worktree> add <discussion_path> && git -C <worktree> commit -m "mill-start: parent-guided retry for <slug>" && git -C <worktree> push`) with no `_status.append_phase` call, set `parent_retry_round = N + 1`, run step (3) (update `prev_blocking_titles`) and continue the loop (`round += 1`).
    If a later round reaches this branch again, the escalation is spent and the halt proceeds.
    On `halt`: the existing set_blocked / commit / push / halt, with `halt_suffix` appended to the set_blocked reason.
    Interactive mode never reaches this branch; say so in one clause.
  - In the bullet about the extension round's `--max-rounds <max_review_rounds + 1>`, add: when `parent_retry_round` is set and the round being dispatched is `>= parent_retry_round`, pass `--max-rounds <round>` (the round being dispatched) instead — the extension round may already be spent, so the cap is computed from the current round.
  - Repeat that rule inline at each of the four dispatch sites in Phase: Discussion Review that currently carry the extension-round `--max-rounds <max_review_rounds + 1>` rule: step 2's Agent-mode `<args>` sentence, step 2's subprocess/psmux `>` reminder, step 3.5's Agent-mode `<args>` sentence, and step 3.5's subprocess/psmux `>` reminder.
    At each site, `--max-rounds <round>` supersedes `<max_review_rounds + 1>` when both would apply.
- **Commit:** `feat(mill-start): ask the parent session before the --auto round-cap halt`

### Card 14: `quick-gate` — mill-quick done-gate failure asks the parent

- **Context:**
  - `plugins/mill/skills/ask-parent/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-quick/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - `## Verify & Complete` step 4 "**Failure path:**": add a first bullet, before _status.set_blocked: when `parent_escalated_quick_gate` is not yet set (session-local, initially false; state this in the bullet), set it and load the `ask-parent` skill with site `quick-gate`, reason `f"done gate failed: {result['reason']}"`, actions `retry,halt`.
    On `retry`: apply the guidance as a fix (same rules as `## Fix`: this session edits, then commits via the `git-commit` skill), then re-run step 1 (the done gate) once and branch per step 2; a second failure takes this failure path again, where the spent escalation means the halt proceeds.
    On `halt`: continue with the existing bullets, with `halt_suffix` appended to the set_blocked reason and to the `BLOCKED:` message.
  - The builder lock stays held during the wait; the existing release bullet runs only when the halt proceeds.
- **Commit:** `feat(mill-quick): ask the parent session before the done-gate halt`

## Batch Tests

Pure skill text, so `verify:` runs the existing lint tests that scan these files, as chained direct invocations (see the overview's `skill-text-verify-uses-direct-invocations` Decision):
`test-skill-helper-drift.py` (every `_<module>.<fn>(` reference in these SKILL.md files resolves to a shipped function),
`test-brief-commit.py` (mill-start commit steps keep staging `_mill/briefs/`),
`test-mill-go-variants.py` (the shared "Why not fork?" paragraph that mill-start and mill-plan cite).
