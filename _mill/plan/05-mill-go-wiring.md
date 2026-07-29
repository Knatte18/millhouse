# Batch: mill-go-wiring

```yaml
task: "mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md"
batch: mill-go-wiring
number: 5
cards: 2
verify: null
depends-on: [1, 2]
```

## Batch Scope

Add the tree-guard safeguard (mill-go had none) to both of mill-go's review loops — the per-batch Code Review loop and the Holistic Review loop — plus the Agent-mode prepare/finalize bracketing at each loop's own dispatch call site. The per-batch loop additionally gets the commit-ordering fix named in `_mill/discussion.md`'s "Closing the same-file modify-then-delete window in mill-go's per-batch loop" Decision (mirroring the Holistic loop's own existing immediate-commit-after-`append_phase` pattern). Documentation-only batch; `verify: null`, justified in Batch Tests below.

## Cards

### Card 7: Tree-guard safeguard + commit-ordering fix in the per-batch Code Review loop (`### 3. Code Review loop`)

- **Context:**
  - `plugins/mill/scripts/_treeguard.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Locate the bullet `"- \`_status.append_phase(status_path, f"reviewing-{batch_name}-r{N}", _timestamp.now_utc_iso())\`."` (the line immediately after `"For each round \`N\` from 1 to \`roles.code-review.batch.rounds\`:"` and immediately before `"1. **Crash-recovery check.**"`). Replace this single bullet with two bullets:

    `- Tree-guard checkpoint: call \`_treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root)\` — on trigger, call \`_status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"])\`.`

    `- \`_status.append_phase(status_path, f"reviewing-{batch_name}-r{N}", _timestamp.now_utc_iso())\`. Commit immediately: \`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: reviewing batch {batch_name} round {N}"\` — mirrors the Holistic Review loop's own existing pattern at the same file (\`_status.append_phase(status_path, "holistic-reviewing", ...)\` immediately followed by an equivalent commit). This closes the window where an uncommitted phase-append could itself be the file a tree-guard restore later discards — see \`_mill/discussion.md\`'s "Closing the same-file modify-then-delete window in mill-go's per-batch loop" Decision.`

  - Locate step 2's opening sentence: `"2. If \`dispatch == agent\`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with \`<cli> = millpy-review-code.py\` and \`<args> = --batch <batch_name> [--extra-file <p> ...] [--prior-notes <digest-path>]\`."` Insert a new sentence immediately before it, still within numbered step 2:

    `Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before the Agent-mode dispatch below. This does not apply to the subprocess/psmux branch immediately following in this same step, which keeps its existing worktree_snapshot_guard coverage unchanged.`

  - Insert a second new sentence immediately after step 2's closing paragraph (the paragraph ending `"... The CLI prints one JSON line \`{"type":"code","round":N,"verdict":"...","reviews":[...]}\`."`) and before `"3. **Builder reads only the JSON envelope verdict, never the findings.**"`:

    `Tree-guard checkpoint (Agent-mode only, post-dispatch): when this round used the Agent-mode branch, call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) again immediately after the Agent-mode dispatch pattern above returns (prepare through finalize), and on trigger call _status.append_recovery_log the same way. This brackets the out-of-process reviewer-execution window that worktree_snapshot_guard cannot see under Agent-mode dispatch (see _mill/discussion.md's "Closing the Agent-mode bracketing gap" Decision). Do not add this checkpoint inside the shared "## Agent-mode dispatch" section itself — it belongs at this call site only, since that section also serves non-review Implement/Fix/merge-in dispatch, which is out of scope.`

  - Do not touch the subprocess/psmux `millpy-bg` invocation or polling logic in step 2 — its coverage (`worktree_snapshot_guard`) is explicitly unchanged (`_mill/discussion.md` Scope (Out)).
  - **Step 4.5 also needs bracketing.** Step 4.5 ("ERROR-only-aggregate retry") re-invokes `millpy-review-code.py` via a second, distinct Agent-mode dispatch of the same review CLI — the same out-of-process reviewer-execution window step 2's checkpoints exist to close, just reached via a different branch. Locate step 4.5's sentence `"If \`dispatch == agent\`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with \`<cli> = millpy-review-code.py\` and \`<args> = --batch <batch_name> [--extra-file <p> ...]\`."` Insert immediately before it:

    `Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before this retry's Agent-mode dispatch. Does not apply to the subprocess/psmux branch immediately below.`

    Insert immediately after that same sentence and before the `"If \`dispatch == subprocess\` or \`psmux\`:"` line that follows it:

    `Tree-guard checkpoint (Agent-mode only, post-dispatch): when this retry used the Agent-mode branch, call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) again immediately after it returns, and on trigger call _status.append_recovery_log the same way.`

  - **Fixer dispatch (step 4's NIT-fix pass, `<cli> = millpy-fix.py`) is out of scope — do not bracket it.** `millpy-fix.py` is not one of the three review CLIs (`millpy-review-discussion.py` / `millpy-review-plan.py` / `millpy-review-code.py`) this task's Scope (In) names; it dispatches a `mill:mill-implementer`-class subagent to a distinct role (fixing, not reviewing). `_mill/discussion.md`'s Scope (Out) explicitly limits this task to "the three review loops (discussion/plan/code+holistic)" and excludes "any... non-review-loop phase." Extending tree-guard bracketing to the fixer dispatch (and, by the same logic, to the Implement/merge-in dispatches sharing the same `## Agent-mode dispatch` section) would be a scope expansion beyond what `_mill/discussion.md` decided, conflicting with that already-approved scope boundary — leave it untouched.
  - Do not modify any other step in this section beyond the ones named above — this task's Scope (In) covers only the per-`append_phase` and per-review-dispatch checkpoints named above.
- **Commit:** `docs(mill): add tree-guard safeguard and commit-ordering fix to mill-go's per-batch Code Review loop`

### Card 8: Tree-guard safeguard in the Holistic Review loop

- **Context:**
  - `plugins/mill/scripts/_treeguard.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Locate step 2's sentence: `"2. **Skip this step when step 1 returned branch (a) or any sub-branch of (c).** \`_status.append_phase(status_path, "holistic-reviewing", _timestamp.now_utc_iso())\`. Commit: \`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: holistic reviewing round {H}"\`."` This loop already commits immediately after its `append_phase` call — no commit-ordering fix is needed here (only the per-batch loop in Card 7 had that gap). Insert a new sentence immediately before this step 2 sentence, still as its own bullet/line, applying only on the non-skipped execution path (i.e. it fires exactly when step 2's own `append_phase`+commit fires, and is likewise skipped when step 1 returned branch (a) or a sub-branch of (c)):

    `Tree-guard checkpoint: call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — on trigger, call _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — before the append_phase/commit below.`

  - Locate step 3's opening sentence: `"3. If \`dispatch == agent\`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with \`<cli> = millpy-review-code.py\` and \`<args> = [--extra-file <p> ...] [--prior-notes <digest-path>]\` (no \`--batch\` flag for holistic scope). Include any accumulated \`extra_files\` from prior \`NEED_CONTEXT\` rounds via \`--extra-file <p>\` (one flag per path)."` Insert a new sentence immediately before it, still within numbered step 3:

    `Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before the Agent-mode dispatch below. This does not apply to the subprocess/psmux branch immediately following in this same step, which keeps its existing worktree_snapshot_guard coverage unchanged.`

  - Insert a second new sentence immediately after step 3's full closing content (the venv-check bash block and any trailing prose that closes out the subprocess/psmux branch of this step) and before step 3.5 (`"3.5. **Step 3.5: ERROR-only-aggregate retry (no round consumed)**"`) — step 3.5 is the step that physically follows step 3's content, not step 4; do not skip past 3.5/3.6 to insert near step 4:

    `Tree-guard checkpoint (Agent-mode only, post-dispatch): when this round used the Agent-mode branch, call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) again immediately after the Agent-mode dispatch pattern above returns (prepare through finalize), and on trigger call _status.append_recovery_log the same way. This brackets the out-of-process reviewer-execution window that worktree_snapshot_guard cannot see under Agent-mode dispatch (see _mill/discussion.md's "Closing the Agent-mode bracketing gap" Decision). Do not add this checkpoint inside the shared "## Agent-mode dispatch" section itself — it belongs at this call site only, since that section also serves non-review Implement/Fix/merge-in dispatch, which is out of scope.`

  - Do not touch the subprocess/psmux `millpy-bg` invocation, the venv-check block, or the crash-recovery three-way branch in step 1 — none of these are in scope for this task.
  - **Step 3.5 also needs bracketing.** Step 3.5 ("ERROR-only-aggregate retry") re-invokes `millpy-review-code.py` via a second, distinct Agent-mode dispatch of the same review CLI — the same out-of-process reviewer-execution window step 3's checkpoints exist to close, just reached via a different branch. Locate step 3.5's sentence `"If \`dispatch == agent\`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with \`<cli> = millpy-review-code.py\` and \`<args> = [--extra-file <p> ...]\`."` Insert immediately before it:

    `Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before this retry's Agent-mode dispatch. Does not apply to the subprocess/psmux branch immediately below.`

    Insert immediately after that same sentence and before the `"If \`dispatch == subprocess\` or \`psmux\`:"` line that follows it:

    `Tree-guard checkpoint (Agent-mode only, post-dispatch): when this retry used the Agent-mode branch, call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) again immediately after it returns, and on trigger call _status.append_recovery_log the same way.`

  - **Step 3.6's redispatch also needs its own bracketing (round 2 plan-review GAP fix) — do not rely on step 3.5's checkpoints re-firing implicitly.** Step 3.6 ("Rate-limit fallback") reads: `"3. Re-run sub-step 3 (the holistic review CLI) with the swapped reviewer. The round counter \`H\` is **not** consumed."` — a third, distinct Agent-mode redispatch, textually referenced by pointing back at "sub-step 3" rather than repeating its dispatch text. Because this is a cross-reference, not a literal re-execution of step 3's own inserted checkpoint sentences, it needs its own explicit pair. Locate that numbered sub-item 3 inside step 3.6's "When sub-step 3.5's second pass returns..." block. Insert immediately before it:

    `Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before re-running sub-step 3 with the swapped reviewer below. Applies only when dispatch == agent; the subprocess/psmux path keeps its existing worktree_snapshot_guard coverage.`

    Insert immediately after that same numbered sub-item 3 and before sub-item 4 (`"4. If the fallback reviewer ALSO returns \`verdict: ERROR\`..."`):

    `Tree-guard checkpoint (Agent-mode only, post-dispatch): when the redispatch above used the Agent-mode branch, call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) again immediately after it returns, and on trigger call _status.append_recovery_log the same way.`

    Insert immediately after that same sentence and before the `"If \`dispatch == subprocess\` or \`psmux\`:"` line that follows it:

    `Tree-guard checkpoint (Agent-mode only, post-dispatch): when this retry used the Agent-mode branch, call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) again immediately after it returns, and on trigger call _status.append_recovery_log the same way.`
- **Commit:** `docs(mill): add tree-guard safeguard to mill-go's Holistic Review loop`

## Batch Tests

`verify: null` — this batch edits `mill-go/SKILL.md` prose and inline-snippet descriptions only; the underlying `_treeguard`/`_status` functions it calls are already covered by batches 1 and 2's unit tests. Per `_mill/discussion.md`'s Testing section, correctness of this wiring — including confirming the per-batch loop's new `"mill-go: reviewing batch {batch_name} round {N}"` commit actually lands before that round's review-CLI dispatch — is confirmed by a manual/integration mill-go dry run through at least one batch's Code Review round and one Holistic Review round, not a new automated test.
