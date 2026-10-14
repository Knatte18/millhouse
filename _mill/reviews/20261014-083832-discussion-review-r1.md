# Review: Drop the eager verify-baseline pre-flight

```yaml
verdict: APPROVE
reviewer_model: orchestrator
reviewed_file: _mill/discussion.md
date: 2026-10-14
```

## Findings

### [NIT:consistency] One rephrase prescribed for four unrelated comments
**Demoted-from:** BLOCKING
**Section:** Scope/In, final bullet.
**Issue:** The bullet groups four citations under one replacement — "the still-real failure mode (a lingering dotnet testhost/MSBuild handle after a verify run)" — but they have three different subjects.
`_worktree.py:272` is the WinError 32 testhost handle and fits.
`_long_path.py:7` is WinError 145 on recursive delete and junction removal.
`test-worktree.py:547` is pruning a stale nested-worktree registration; `:597` is `core.longpaths` placement in the remove/prune argv.
Followed literally, three of the four get a comment that misdescribes what they cover.
Compounding it: 547 and 597 both name "`_verify_baseline.py`'s transient nested worktree", which #1130/#1181 already removed — the module docstring now reads "never a checkout, never a transient worktree under `.scratch/`" — so those two are stale before this task touches them.
**Fix:** Give each of the four its own replacement subject, and state that 547/597 only need `_verify_baseline.py` dropped as the attribution, since `remove_safe`'s pruning and longpaths behaviour are what those tests actually exercise.

### [NIT:decision] No verify named for the batch editing `_long_path.py`
**Demoted-from:** BLOCKING
**Section:** Constraints, second bullet, against Scope/In's final bullet.
**Issue:** Scope/In requires editing `plugins/mill/scripts/_long_path.py`, and Constraints rules `test-long-path.py` out of any batch verify because it is one of `main`'s nine red tests.
That is the natural verify for that file, and no alternative is chosen.
`_plan_validate.py` does permit a batch with no `verify:` (`_check_verify_full_suite`'s batch handling treats absent `verify:` as `cwd=None`, and the overview-level non-null requirement is separate), so both options are open — the discussion picks neither.
**Fix:** Decide it here: either give that batch `verify:` omitted on the grounds that it is a comment-only edit, or fold the comment rephrasings into a batch whose verify covers a different, green test file.

### [NIT:consistency] Testing's enumerated ranges miss two breakage sites
**Section:** Testing.
**Issue:** Two sites that the removals break fall outside what Testing names.
`test-implementer-common.py` imports `_normalize_failure_signature` at line 35 and exercises it directly in case 71b (~4918); that is neither a waiver nor a pre-existing-failures case, so "remove waiver/pre-existing-failures cases" does not reach it, and the import breaks at collection.
`test-millpy-merge-in-subagent.py:451-461` asserts the literal string `--mode is required unless --recompute-baseline is set`, outside the 1130–1290 range Testing gives.
Decision `signatures-field`'s re-grep instruction catches the first only.
**Fix:** Name both in Testing.

## Verdict

APPROVE

The scope list is accurate and complete — a full sweep for `_verify_baseline`, `verify_baseline_failures`, `module_verify_baseline`, `baseline_verify_timeout_minutes`, `--stage baseline`, `recompute-baseline` and `baseline-preflight-log` across `plugins/`, `mill-config.yaml` and `doc/` returns nothing the discussion has not already classified, every helper slated for deletion is confirmed to have no caller outside the baseline stage, and the `no-status-migration` decision's load-bearing claims hold (`set_batch_field`/`set_batch_fields` validate only the key being written, and `_render_batches`' fixed `order` list drops anything absent from it).
_Note: 2 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
The 0.55 boundary is drawn explicitly and correctly, including that 0.55 precedes 0.5 in the file.
What needs settling is the comment-rephrasing instruction and the verify command for the batch that carries it.
