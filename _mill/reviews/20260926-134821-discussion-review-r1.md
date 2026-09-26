# Review: mill-merge: run the deterministic path as one script

```yaml
verdict: REQUEST_CHANGES
reviewer_model: orchestrator
reviewed_file: _mill/discussion.md
date: 2026-09-26
```

## Findings

### [BLOCKING:design] "Squash landed?" is a heuristic that skips a needed push
**Section:** Decision `re-entry-idempotency` ("Squash: `Already up to date` or `nothing to commit` skips push"), Decision `step5-in-script`.
**Issue:** If a run dies after `commit` but before `push` (kill, timeout, crash), the parent is clean and ahead of `origin/<parent>`. The re-run's ff-only is a no-op, `merge --squash` finds nothing to add, "nothing to commit" skips the push, and the script proceeds to archive tag and `[done]` with the squash never on origin. The reverse also fails: once the parent has advanced after a landed squash, a re-run re-squashes and conflicts instead of reporting "nothing to commit".
**Suggested fix:** Derive "landed" from state, not command output. After the ff-only, if `git -C <parent-path> rev-list origin/<parent>..<parent>` is non-empty, push those commits (no new squash). Treat the squash as already landed only when that is empty and the child's cleanup-tip content is already in `origin/<parent>`. Add unit tests for "local squash commit unpushed" and "parent advanced after landing".

### [BLOCKING:design] The in-script lock wait and crash paths are not survivable
**Section:** Decision `lock-timing` (poll every 10 s up to 5 min), Decision `script-shape` (crash = traceback, no JSON), Testing (lock released "on exception").
**Issue:** One script call can now block up to 5 min on the lock and then run fetch, squash, push and rebase-retry, but `mill-merge/SKILL.md` gives no invocation timeout and the Bash tool defaults to 2 min (max 10). A timeout kill skips `finally`: the lock stays (stale for 5 min) and the parent may be left mid-squash with no rollback, which the next run reports only as the dirty-parent halt. The tests cover lock release on exception but not rollback on exception between `merge --squash` and a successful push.
**Suggested fix:** State the timeout the skill must pass (at least 600000 ms) or shorten the wait so the whole run fits, and return a `halt` "lock busy" with `resume: []` rather than blocking. Require the runner's `finally` to roll back (`reset --hard origin/<parent_branch>`) on any exception before the squash is pushed, plus a SIGTERM handler that does the same. Document that a hard kill leaves a stale lock (5-min rule) and a dirty parent (existing dirty-parent halt text).

### [NIT:decision] `--parent <new>` semantics are undefined
**Section:** Decision `stops-that-remain-with-the-model` (merge-in callback), Decision `json-result-contract` (`resume`).
**Issue:** `mill-merge-in` already rebinds `status.md` on a dead-parent substitution, but only when `status.md` exists; on re-entry it is "not persisted". The discussion does not say whether `--parent` skips the script's own liveness check, requires a second confirm, or is persisted anywhere. Without the flag, a re-run re-resolves the old dead parent and returns another `confirm-parent` callback.
**Suggested fix:** Say that `--parent` overrides the resolved parent for this run and skips the liveness callback, and that the skill must pass it on every re-run after a substitution.

### [NIT:scope] Cross-reference list may be incomplete
**Section:** Technical context, "Cross-references to update".
**Issue:** A grep in the worktree also finds `plugins/mill/integration_tests/test-merge.py` comments naming "mill-merge Step 4/5" (lines 405, 589, 1338), which the list omits; they are comments only, but they go stale with the rewrite.
**Suggested fix:** Add them to the list or state that stale step-number comments in that file are left alone.

## Verdict

REQUEST_CHANGES
Resumption after a killed run and the in-script lock wait need explicit designs; lock-across-callback and rollback-at-stop are otherwise covered.
