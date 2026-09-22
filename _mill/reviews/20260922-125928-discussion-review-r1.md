# Review: compute_baseline: use the task worktree's own pre-edit state, not a parent-branch checkout

```yaml
verdict: APPROVE
reviewer_model: orchestrator
reviewed_file: _mill/discussion.md
date: 2026-09-22
```

## Findings

### [NIT:consistency] Gotchas section misquotes mill-go-base/SKILL.md
**Demoted-from:** BLOCKING
**Section:** Technical context / Gotchas found during exploration, third bullet
**Issue:** Claims "§0.5's current instruction is `grep '^{' <log-path>` while §0.5's speculative branch says `tail -1`; reconcile both". Both the speculative branch (line 583) and the main §0.5 flow (line 605) actually use `grep '^{' <log-path>` — `tail -1` does not appear anywhere in `mill-go-base/SKILL.md`. There is no current discrepancy to reconcile.
**Suggested fix:** Drop the false "tail -1" claim. The underlying point (parse by `substage` key, not positionally, once a second JSON line is added) is still valid and can stand on its own without the fabricated inconsistency.

## Verdict

APPROVE
One source-grounding error in an otherwise thoroughly-verified technical-context section — everything else checked (line anchors, function signatures, `_checkout_parent_branch`'s tip-not-merge-base behavior, `iter_batch_verifies`, `_status.py`/`millpy-cleanup.py`/`millpy-merge-in-subagent.py` call sites) matched the actual source exactly.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
