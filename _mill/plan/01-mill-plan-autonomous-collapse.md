# Batch: mill-plan-autonomous-collapse

```yaml
task: 'Non-interactive pipeline: only mill-start''s interview may prompt the operator'
batch: mill-plan-autonomous-collapse
number: 1
cards: 2
verify: null
depends-on: []
```

## Batch Scope

`mill-plan/SKILL.md`'s Phase: Plan Review has two sites that today branch on `pipeline.autonomous_mode: true` to choose between an interactive numbered-options prompt and a clean `_status.set_blocked` halt: the Non-progress check (step 5) and the Max-rounds escape (step 6). This batch collapses both to always take the halt branch — mill-plan never waits for an operator reply again; it either resolves something itself (no site here needs new self-resolve logic — a stable reviewer/fixer disagreement and an exhausted round budget are both genuine "exhausted retries" signals per the task's own named exceptions) or halts cleanly. This batch also updates the stale "Autonomous" bullet in `## Principles` to match. No Python code is touched — this is a SKILL.md prose-only batch.

## Cards

### Card 1: Collapse mill-plan's Non-progress check to unconditional halt

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In `### Phase: Plan Review`, step `5. **Non-progress check**`, the paragraph currently reads exactly:

```
5. **Non-progress check** (after writing each fixer report from round 2 onward): **Skip this check when the latest round's `## Pushed Back` section is empty.** Empty Pushed Back means the planner addressed every finding cleanly — that is convergence, not non-progress. The check only fires when both rounds have a non-empty Pushed Back AND the title set is identical. If the deep-merged config has `pipeline.autonomous_mode: true`: skip the user prompt; `_status.set_blocked(status_path, f"non-progress round {N}", timestamp=ts)`; commit `git -C <worktree> add <status_path> <reviews_dir> && git -C <worktree> commit -m "mill-plan: blocked (autonomous-mode non-progress) for {slug}"` and push; halt with "Autonomous mode: plan blocked on non-progress at round {N}. Task left as [active] for manual review." If the set is identical, halt with `BLOCKED: Plan review non-progress round {N}` and tell the user to look at the fixer reports. Do not escape-hatch — non-progress means the planner and reviewer are stuck in a stable disagreement; user intervention is required.
```

  Replace the whole paragraph with:

```
5. **Non-progress check** (after writing each fixer report from round 2 onward): **Skip this check when the latest round's `## Pushed Back` section is empty.** Empty Pushed Back means the planner addressed every finding cleanly — that is convergence, not non-progress. The check only fires when both rounds have a non-empty Pushed Back AND the title set is identical. When it fires: `_status.set_blocked(status_path, f"non-progress round {N}", timestamp=ts)`; commit `git -C <worktree> add <status_path> <reviews_dir> && git -C <worktree> commit -m "mill-plan: blocked (non-progress) for {slug}"` and push; halt with "Plan blocked on non-progress at round {N}. Task left as [active] for manual review." Do not escape-hatch — non-progress means the planner and reviewer are stuck in a stable disagreement; user intervention is required.
```

  This removes the `pipeline.autonomous_mode: true` gate and the sibling interactive halt-message branch entirely, keeping only the (formerly autonomous-only) `_status.set_blocked` path as the unconditional behavior. Do not touch step 6 (Max-rounds escape) in this card — that is Card 2.
- **Commit:** `docs(mill-plan): collapse non-progress check to unconditional halt`

### Card 2: Collapse mill-plan's Max-rounds escape to unconditional halt

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In `### Phase: Plan Review`, step `6. **Max-rounds escape**` currently reads exactly (including the blockquote and the closing paragraph):

```
6. **Max-rounds escape** (only when round counter exhausts without APPROVE, BLOCKINGs still remain, AND non-progress did not fire): If the deep-merged config has `pipeline.autonomous_mode: true`: skip the user prompt; `_status.set_blocked(status_path, f"max-rounds exhausted after {N} rounds, {M} BLOCKINGs remain", timestamp=ts)`; commit and push; halt with "Autonomous mode: plan blocked after {N} rounds, {M} BLOCKINGs remain. Task left as [active]." present the user with the prompt below verbatim, computing `{N}` and `{M}` and a one-line recommendation. `{M}` is `result["blocking_count"]` from the most recent CLI invocation — do not re-count manually. If `blocking_count` was 0 in the latest round, this prompt should not have fired — verify step 4c logic before presenting.

   > After {N} rounds, {M} BLOCKING findings remain unresolved (blocking_count from latest round's review JSON). Present these three as a numbered list per `mill:conversation`'s convention: determine the recommended option from {analysis of remaining findings}, list it first as `1)` with `(Recommended)` appended to its label, then list the remaining two as `2)` and `3)` in their order below.
   > - Deep problems — rethink approach. Go back to mill-start and revise discussion.
   > - Shallow — one more review round. Invoke: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py" --max-rounds {N+1}` (the `--max-rounds` flag overrides the configured cap; without it the script re-reads config and exits at the same cap again).
   > - Override — accept findings and proceed to mill-go anyway.

   Wait for the user's choice. Deep problems → halt and tell user to check out fresh after they revise. Shallow → invoke `millpy-review-plan.py --max-rounds {N+1}` where `{N}` is the round count just reported (one extra round beyond the configured max). Override → set `approved: true` and proceed to Handoff.
```

  Replace the whole step (from `6. **Max-rounds escape**` through the paragraph ending "Override → set `approved: true` and proceed to Handoff.") with:

```
6. **Max-rounds escape** (only when round counter exhausts without APPROVE, BLOCKINGs still remain, AND non-progress did not fire): `_status.set_blocked(status_path, f"max-rounds exhausted after {N} rounds, {M} BLOCKINGs remain", timestamp=ts)`; commit and push; halt with "Plan blocked after {N} rounds, {M} BLOCKINGs remain. Task left as [active] for manual review." `{M}` is `result["blocking_count"]` from the most recent CLI invocation — do not re-count manually. If `blocking_count` was 0 in the latest round, this halt should not have fired — verify step 4c logic before proceeding.
```

  This deletes the entire numbered-options blockquote and the "Wait for the user's choice" paragraph — mill-plan never presents this prompt again; every max-rounds exhaustion is a clean halt.

  Separately, in `## Principles`, the bullet currently reads exactly:

```
- **Autonomous** — the only user interaction is the max-rounds escape and non-progress halt.
```

  Replace it with:

```
- **Autonomous** — mill-plan never waits for an operator reply. The max-rounds escape and non-progress check resolve by halting via `_status.set_blocked` instead of prompting.
```
- **Commit:** `docs(mill-plan): collapse max-rounds escape to unconditional halt`

## Batch Tests

`verify: null` — this batch edits only `plugins/mill/skills/mill-plan/SKILL.md`, a prose file interpreted by Claude Code at skill-invocation time, not executable Python. There is no runnable test surface. Correctness is verified by plan review (byte-exact old/new text matching against the actual worktree source, confirmed during Phase: Plan against the task-worktree copy of the file) and, downstream, by mill-go's code review reading the resulting diff.
