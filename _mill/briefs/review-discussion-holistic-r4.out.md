MILL_REVIEW_BEGIN
# Review: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-06
```

## Findings

### [GAP] mill-merge-in verify replay is an unaddressed #604 site
**Section:** Scope (In) / Decision "Verify-cwd explicit field (#604)"
**Issue:** `mill-merge-in/SKILL.md:77-84` (step 4 Verify) also consumes `iter_batch_verifies` — it unpacks `(name, cmd)` 2-tuples and runs each "from the worktree root", so (a) the planned 3-tuple `(name, command, cwd)` shape breaks its unpacking, and (b) it ignores `cwd: hub`, re-running nested-layout hub-relative commands at git-root and reproducing #604 in the merge replay path — the exact bug class this task fixes. It is absent from both the Scope "In" list and the #604 read-site enumeration (which names only implement/fix/baseline).
**Fix:** Add `mill-merge-in/SKILL.md` step 4 to scope: switch to the 3-tuple, resolve each batch's `cwd` (via `parse_verify_field`), and run each verify at the resolved cwd; note the `${PLUGIN_ROOT}`/allowlist loop already there.

### [NOTE] iter_batch_verifies tuple-shape change ripples to test consumers
**Section:** Testing
**Issue:** Changing `iter_batch_verifies` to 3-tuples breaks existing consumers not listed for update: `test-plan-dag.py:174` asserts exact 2-tuples and `test-merge.py:431` unpacks the return.
**Fix:** Add these two tests to the Testing section's update list alongside the fixer/validate cases.

### [NOTE] Second worktree-param callsite in clean_ephemeral not enumerated
**Section:** Decision "compute_scope_violations caller signature"
**Issue:** The rename of `clean_ephemeral_scope_violations`'s `worktree` param to `hub_root` names only the line-268 join and the compute call; it omits `_is_go_main_artifact(worktree, violation)` at `_cleanliness.py:256`, another reference to the renamed param.
**Fix:** Note that all `worktree` references in the function (including line 256) rename to `hub_root`; behavior is unchanged since `_is_go_main_artifact` matches on basename.

## Verdict

GAPS_FOUND
mill-merge-in's verify replay is an unaddressed #604 execution site and breaks on the new tuple shape.
MILL_REVIEW_END