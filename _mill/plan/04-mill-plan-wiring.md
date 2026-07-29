# Batch: mill-plan-wiring

```yaml
task: "mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md"
batch: mill-plan-wiring
number: 4
cards: 1
verify: null
depends-on: [1, 2]
```

## Batch Scope

Add a brand-new tree-guard safeguard to mill-plan's Phase: Plan Review (mill-plan has no equivalent safeguard today — confirmed by `_mill/discussion.md`'s Technical context grep of "Status safeguard": no hits), applied before every `_status.append_phase` call in the phase (steps 4a/4b/4c/4d), plus the Agent-mode prepare/finalize bracketing around step 2's dispatch. Documentation-only batch; `verify: null`, justified in Batch Tests below.

## Cards

### Card 6: Add the tree-guard safeguard and Agent-mode bracketing to `mill-plan/SKILL.md`'s Phase: Plan Review

- **Context:**
  - `plugins/mill/scripts/_treeguard.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Locate the paragraph `"**Path Setup (Plan Review).** Derive: \`reviews_dir = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])\`. Use this variable for all review file path references in this phase."` (immediately under the `### Phase: Plan Review` heading). Insert a new paragraph immediately after it, and before the `"Load the \`mill-receiving-review\` skill now, unconditionally, ..."` paragraph:

    `**Tree-guard safeguard (applies to all \`_status.append_phase\` calls in this phase):** Before any \`_status.append_phase\` call in this phase (steps 4a/4b/4c/4d below), call \`_treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root)\`. If the returned dict's \`"triggered"\` field is \`True\`, call \`_status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"])\` immediately after — this records the detection non-blockingly; it never halts the phase. mill-plan runs a structurally identical review-loop architecture to mill-start and mill-go and had no equivalent safeguard before this task (see \`_mill/discussion.md\`'s "Wiring point: all three review loops, not just mill-start" Decision).`

  - Locate step 2's opening sentence: `"2. **Dispatch mode:** Resolve dispatch mode via \`_agent_dispatch.resolve_dispatch_mode(cfg)\`. If \`agent\` (Claude provider only): follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in \`plugins/mill/skills/mill-go/SKILL.md\`) with \`<cli> = millpy-review-plan.py\` and \`<args> = --holistic-only\`. ..."` Insert a new sentence immediately before the `"If \`agent\`"` clause, within the same numbered item:

    `Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before the Agent-mode dispatch below. This does not apply to the subprocess/psmux branch, which keeps its existing worktree_snapshot_guard coverage unchanged.`

  - Insert a second new sentence immediately after step 2's closing paragraph (`"**Pre-review validator gate:** ... The claim at line 104 ... is now accurate in agent mode because the prepare stage runs the validator before returning a brief to the Agent."`) and before the `"**Subprocess/psmux branch — Invoke the CLI as a subprocess:**"` heading:

    `Tree-guard checkpoint (Agent-mode only, post-dispatch): when this round used the Agent-mode branch, call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) again immediately after the Agent-mode dispatch pattern above returns (prepare through finalize, including any validator-fix re-invocation cycle), and on trigger call _status.append_recovery_log the same way. This brackets the whole out-of-process reviewer-execution window that worktree_snapshot_guard cannot see under Agent-mode dispatch (see _mill/discussion.md's "Closing the Agent-mode bracketing gap" Decision). Do not add this checkpoint inside the shared "## Agent-mode dispatch" section itself in mill-go/SKILL.md — it belongs at this call site only, since that shared section also serves non-review Implement/Fix/merge-in dispatch, which is out of scope.`

  - Do not touch the `**Subprocess/psmux branch — Invoke the CLI as a subprocess:**` prose or its `millpy-bg` invocation — the subprocess/psmux path's coverage (`worktree_snapshot_guard`) is explicitly unchanged (`_mill/discussion.md` Scope (Out)).
  - **Step 4.5 also needs bracketing.** Step 4.5 ("ERROR-only-aggregate retry") re-invokes `millpy-review-plan.py` via a second, distinct Agent-mode dispatch — the same out-of-process reviewer-execution window step 2's checkpoints exist to close, just reached via a different branch. Locate step 4.5's sentence `"**Agent-mode:** follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in \`plugins/mill/skills/mill-go/SKILL.md\`) with \`<cli> = millpy-review-plan.py\` and \`<args> = --holistic-only\`."` Insert immediately before it:

    `Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before this retry's Agent-mode dispatch. Does not apply to the Subprocess/psmux branch immediately below.`

    Insert immediately after that same sentence and before the `"**Subprocess/psmux branch:**"` heading that follows it:

    `Tree-guard checkpoint (Agent-mode only, post-dispatch): when this retry used the Agent-mode branch, call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) again immediately after it returns, and on trigger call _status.append_recovery_log the same way.`

  - Do not modify steps 4a/4b/4c/4d/5/6's own logic — the new safeguard paragraph above already covers every `_status.append_phase` call site in this phase without needing a per-step edit, mirroring how mill-start's single phase-level paragraph covers its own multiple `append_phase` call sites.
  - Do not add anything to `### Phase: Handoff` — its `_status.append_phase(status_path, "planned", ...)` call is a separate phase, not covered by the "applies to all `_status.append_phase` calls in this phase" wording.
- **Commit:** `docs(mill): add tree-guard safeguard to mill-plan's Plan Review loop`

## Batch Tests

`verify: null` — this batch edits `mill-plan/SKILL.md` prose and inline-snippet descriptions only; the underlying `_treeguard`/`_status` functions it calls are already covered by batches 1 and 2's unit tests. Per `_mill/discussion.md`'s Testing section, correctness of this wiring is confirmed by a manual/integration mill-plan dry run through at least one Plan Review round, not a new automated test.
