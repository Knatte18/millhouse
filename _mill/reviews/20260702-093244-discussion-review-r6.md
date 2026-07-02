Verified against source. The discussion is meticulous, but I found genuine internal inconsistencies and unaddressed failure modes. Two are blocking.

MILL_REVIEW_BEGIN
# Review: Fix agent-mode dispatch races and pipeline gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-02
```

## Findings

### [GAP] Baseline test cases contradict "gate reads only" decision
**Section:** Decisions › baseline-aware gate; Testing (a)/(b)/(e)
**Issue:** The Decision + Technical Context put computation in `--stage baseline` and make `_run_verify_gates` a read-only lookup that, on a `null` baseline, falls safe to "clean, run strict, do NOT cache" — yet Testing cases (a)/(b) say baseline `null` "on first call computes and persists," and (e) tests transient-worktree cleanup, all attributed to "`_run_verify_gates`'s new signature." A gate that only reads cannot compute/persist; the TDD target is mis-specified.
**Fix:** State that (a)/(b)/(e) exercise the `--stage baseline` computation function (not `_run_verify_gates`), and specify whether they run as real-git integration tests (per CLAUDE.md unit tests use no real git/worktrees) or via a mocked worktree/junction layer.

### [GAP] Transient-worktree path asymmetry can wrongly cache pre-existing-failures
**Section:** Decisions › baseline-aware gate (computation)
**Issue:** Baseline runs `module_wide_verify_cmd` in a transient worktree at a different filesystem path than the task worktree where the real per-batch gate runs. A deterministic path-sensitive verify failure in the transient path (e.g. mill's own `_paths`/cwd-resolving tests) fails both runs and caches `"pre-existing-failures"`, silently disabling #541's gate task-wide — exactly the "unsafe direction" the design prioritizes avoiding. The double-run retry only guards non-deterministic flakiness, not this deterministic environment mismatch.
**Fix:** Acknowledge the transient-vs-task path asymmetry and either run the baseline in an environment matching the task-worktree path, or narrow the fall-safe so environment/path-induced failures fall toward `"clean"`.

### [NOTE] `--stage baseline` must satisfy required `batch_name` positional
**Section:** Scope; Decisions › baseline-aware gate
**Issue:** `millpy-implement.py` requires a positional `batch_name` (`millpy-implement.py:81-84`), but the task-scoped `--stage baseline` runs pre-flight before any batch and at merge-in; the discussion never says what `batch_name` the pre-flight/merge-in calls pass or whether the arg becomes optional for this stage.
**Fix:** Specify that `batch_name` is made optional (or a placeholder) for `--stage baseline`.

### [NOTE] Transient worktree location unspecified
**Section:** Constraints (worktree cleanup)
**Issue:** The `git worktree add <tmp-path>` location is unspecified; CLAUDE.md mandates `.scratch/`, never system temp.
**Fix:** State the transient worktree is created under `.scratch/`.

## Verdict

GAPS_FOUND
Two internal inconsistencies (test target, baseline fall-safe) must resolve before planning.
MILL_REVIEW_END