MILL_REVIEW_BEGIN
# Review: mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [BLOCKING] check_and_restore trusts an unchecked git-checkout restore
**Location:** Batch 1 (treeguard-helper), Card 1, step 6
**Issue:** `_subprocess_util.run(["git","checkout","HEAD","--",*deleted_paths], cwd=worktree)` is explicitly required to NOT branch on `returncode`, and step 7 unconditionally returns `triggered: True, restored_paths: sorted(deleted_paths)` even if the checkout failed. Callers (batches 3-5) log this to `status.md` via `append_recovery_log` as a factual audit trail — a failed restore would be recorded as a successful one, silently defeating the exact data-loss the task exists to fix.
**Fix:** Check `result.returncode`; only report a path as restored (and only set `triggered`) for paths git actually restored, and surface/log the failure case. Add a test scenario for a failed/partial restore.

### [BLOCKING] mill-start's ERROR-only retry dispatch (step 3.5) is not tree-guard-bracketed
**Location:** Batch 3 (mill-start-wiring), Card 5
**Issue:** `mill-start/SKILL.md`'s Phase: Discussion Review has a second Agent-mode dispatch site at step 3.5 (ERROR-only-aggregate retry, re-invoking `millpy-review-discussion.py` via the Agent-mode pattern) that is a distinct out-of-process reviewer-execution window — the same risk class step 2's pre/post checkpoints were added to close. Card 5 only wires bracketing around step 2's dispatch; step 3.5 is never mentioned.
**Fix:** Add the same pre/post tree-guard checkpoint sentences around step 3.5's Agent-mode re-dispatch.

### [BLOCKING] mill-plan's ERROR-only retry dispatch (step 4.5) is not tree-guard-bracketed
**Location:** Batch 4 (mill-plan-wiring), Card 6
**Issue:** Same gap as above: `mill-plan/SKILL.md`'s Phase: Plan Review step 4.5 (ERROR-only-aggregate retry) re-invokes `millpy-review-plan.py` via Agent-mode dispatch, but Card 6 only brackets step 2's dispatch, leaving step 4.5's out-of-process window unprotected.
**Fix:** Add pre/post tree-guard checkpoints around step 4.5's Agent-mode re-dispatch.

### [BLOCKING] mill-go's ERROR-retry and fixer Agent-mode dispatches left explicitly unbracketed
**Location:** Batch 5 (mill-go-wiring), Cards 7 and 8
**Issue:** Both the per-batch loop (step 4.5) and the Holistic loop (step 3.5) have their own ERROR-only-aggregate retry re-dispatch of `millpy-review-code.py` via Agent-mode — an out-of-process reviewer-execution window identical in kind to the ones the cards do bracket. Card 7 additionally states "Do not modify... any other step in this section," explicitly excluding step 4.5 (and the step-4 NIT-fix/REQUEST_CHANGES fixer dispatches) from bracketing even though these are also Agent-mode out-of-process dispatches.
**Fix:** Extend the pre/post tree-guard checkpoints to the ERROR-retry re-dispatch in both loops (step 4.5 and step 3.5); reconsider whether fixer dispatches need the same treatment or document why they're categorically safe.

### [NIT] Contradictory ordering guidance in check_and_restore
**Location:** Batch 1, Card 1, steps 4 and 7
**Issue:** Step 4 says to collect `deleted_paths` "preserving the git status order; do not re-sort," but step 7 immediately returns `sorted(deleted_paths)` — and `status_porcelain`'s output is already alphabetically sorted, so the "preserve order" instruction is moot and reads as contradictory.
**Fix:** Drop the "do not re-sort" wording from step 4, or clarify it only applies to the argv order passed to `git checkout`.

### [NIT] Vacuous "record-shape" test assertion
**Location:** Batch 1, Card 2, requirement bullet (scenario 2/3 record-shape assertion)
**Issue:** The described proof ("the function signature takes no status_path/cfg argument... already enforced by the call sites in this test file itself") verifies nothing beyond what the test file's own code already guarantees syntactically — it's not a runtime check of `_treeguard`'s behavior.
**Fix:** Either drop this bullet or replace it with a concrete assertion (e.g., diffing `status.md`'s mtime/content before and after `check_and_restore` runs in a scenario where `status.md` isn't the deleted file).

### [NIT] No test for `_find_recovery_log_block`'s malformed-section ValueError path
**Location:** Batch 2 (status-recovery-log), Card 4
**Issue:** Card 3 requires `_find_recovery_log_block` to raise `ValueError` when the heading is present but the fence is missing/unterminated (mirroring `_find_batches_block`), but Card 4's test list never exercises this path.
**Fix:** Add a 5th test case seeding a `## Tracked-file recovery log` heading with no/unterminated fence and asserting `ValueError`.

## Verdict

REQUEST_CHANGES
Silent restore-failure risk plus a systemic gap: ERROR-retry Agent-mode re-dispatches across all three skills aren't tree-guard-bracketed.
MILL_REVIEW_END
