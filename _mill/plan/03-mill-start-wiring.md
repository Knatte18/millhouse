# Batch: mill-start-wiring

```yaml
task: "mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md"
batch: mill-start-wiring
number: 3
cards: 1
verify: null
depends-on: [1, 2]
```

## Batch Scope

Widen mill-start's existing status.md-only "Status safeguard" (Phase: Discussion Review) to cover the whole `_mill/` tree via `_treeguard.check_and_restore` + `_status.append_recovery_log`, and add the new Agent-mode prepare/finalize bracketing checkpoint around the phase's Agent-mode dispatch. This is a documentation-only batch (a `SKILL.md` prose/inline-snippet edit) with no automated test surface of its own — `verify: null`, justified in Batch Tests below.

## Cards

### Card 5: Widen the Status safeguard and add Agent-mode bracketing in `mill-start/SKILL.md`'s Phase: Discussion Review

- **Context:**
  - `plugins/mill/scripts/_treeguard.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Locate the existing paragraph beginning `"**Status safeguard (applies to all \`_status.append_phase\` calls in this phase):** Before any \`_status.append_phase\` call, run \`git -C <worktree> status --short -- _mill/status.md\`. If the output contains \`D\` ... Blank output means the file is present and unchanged — blank is NOT the deletion signal."` (the paragraph immediately after the `### Phase: Discussion Review` heading). Replace it in place with:

    `**Tree-guard safeguard (applies to all \`_status.append_phase\` calls in this phase):** Before any \`_status.append_phase\` call in this phase, call \`_treeguard.check_and_restore(worktree_root, "_mill")\`. If the returned dict's \`"triggered"\` field is \`True\`, call \`_status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"])\` immediately after — this records the detection non-blockingly; it never halts the phase. This widens the prior status.md-only safeguard to the whole \`_mill/\` tree (\`discussion.md\`, \`status.md\`, \`briefs/\`, \`reviews/\`) and restores only the exact paths git reports as deleted, never a blanket subtree checkout — see \`_mill/discussion.md\`'s "Detection query and restore granularity" Decision for why a legitimate uncommitted modification elsewhere in \`_mill/\` (e.g. a just-appended, not-yet-committed \`status.md\` phase row) is never swept into the restore.`

    Replace this paragraph's whole content — do not leave the old `git status --short -- _mill/status.md` wording alongside the new text.
  - Locate step 2's sentence: `"2. **Dispatch mode:** Resolve dispatch mode via \`_agent_dispatch.resolve_dispatch_mode(cfg)\`. If \`agent\` (Claude provider only): follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in \`plugins/mill/skills/mill-go/SKILL.md\`) with \`<cli> = millpy-review-discussion.py\` with \`<args> = --max-rounds <max_review_rounds + 1>\` ONLY when this round is the Auto mode non-progress-extension round ...; omit \`<args>\` ... on every other round. Thread \`--round <round>\` ... If \`subprocess\` or \`psmux\`: use the subprocess branch below."` Insert a new sentence immediately before the `"If \`agent\`"` clause (still within step 2, same numbered item, not a new numbered step):

    `Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill") — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before the Agent-mode dispatch below. This does not apply to the subprocess/psmux branch, which keeps its existing worktree_snapshot_guard coverage unchanged.`

  - Insert a second new sentence immediately after step 2's final sentence and before step 3 (`"3. **Confirm \`mill-receiving-review\` is loaded ..."`), i.e. after the "**Agent-mode properties:**" paragraph that closes out step 2:

    `Tree-guard checkpoint (Agent-mode only, post-dispatch): when this round used the Agent-mode branch, call _treeguard.check_and_restore(worktree_root, "_mill") again immediately after the Agent-mode dispatch pattern above returns (prepare through finalize), and on trigger call _status.append_recovery_log the same way. This brackets the whole out-of-process reviewer-execution window that worktree_snapshot_guard cannot see under Agent-mode dispatch (see _mill/discussion.md's "Closing the Agent-mode bracketing gap" Decision). Do not add this checkpoint inside the shared "## Agent-mode dispatch" section itself in mill-go/SKILL.md — it belongs at this call site only, since that shared section also serves non-review Implement/Fix/merge-in dispatch, which is out of scope.`

  - Do not touch the `**Subprocess/psmux branch**` prose or its `millpy-bg` invocation in this phase — the subprocess/psmux path's coverage (`worktree_snapshot_guard`) is explicitly unchanged (`_mill/discussion.md` Scope (Out)).
  - Do not add or modify anything in `### Phase: Handoff` — its own `_status.append_phase(status_path, "discussed", timestamp)` call is a separate phase, not covered by the "applies to all `_status.append_phase` calls in this phase" wording (which is phase-scoped to Discussion Review, both before and after this edit).
- **Commit:** `docs(mill): widen mill-start's tracked-file safeguard to the whole _mill/ tree`

## Batch Tests

`verify: null` — this batch edits `mill-start/SKILL.md` prose and inline-snippet descriptions only; there is no runnable surface to assert against directly (the underlying `_treeguard`/`_status` functions this batch calls are already covered by batches 1 and 2's unit tests). Per `_mill/discussion.md`'s Testing section, correctness of this wiring is confirmed by a manual/integration mill-start dry run through at least one Discussion Review round, not a new automated test.
