MILL_REVIEW_BEGIN
# Review: millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] CREATE_BREAKAWAY_FROM_JOB misattributed to worker's child command
**Section:** Scope (bullet 3) + Technical Context (`_subprocess_util.py`) **Issue:** Both sections claim the worker's inner `subprocess.run(cmd, ...)` child (the actual `millpy-implement.py` etc.) is "further isolated by `CREATE_BREAKAWAY_FROM_JOB`" — but reading `_subprocess_util.popen_detached` and `millpy-bg.py`'s `_worker_main` shows that flag is only set on the launcher→worker `Popen` call (via `popen_detached`); the worker's own child is spawned with plain `subprocess.run(cmd, stdout=log_f, stderr=STDOUT, creationflags=CREATE_NO_WINDOW)` — no breakaway flag at all. **Fix:** Correct the mechanism explanation — the child surviving `TerminateProcess` on the worker is ordinary Windows parent/child independence (no Job Object groups them), not a second application of `CREATE_BREAKAWAY_FROM_JOB`; the fix itself (ctypes probe) is unaffected, but the rationale text is wrong and should not carry into the plan.

### [BLOCKING:consistency] "stdlib-only" premise for rejecting psutil contradicts pyproject.toml
**Section:** Decisions → `bg-liveness-probe-fix` (Rejected) **Issue:** Rejects `psutil` because "the mill script family is deliberately stdlib-only — see `millpy-bg.py`'s worker fast-path docstring," but `plugins/mill/pyproject.toml` already lists `pyyaml`, `pygit2`, and `tinydb` as dependencies, and the cited docstring's stdlib-only scope is explicitly the worker fast-path's startup-perf hot path (`if "--_worker" in sys.argv:`), not a project-wide convention — no other file states a general stdlib-only rule. **Fix:** Restate the rejection on its actual merits (e.g. avoid a new runtime dependency for a narrow win32-only branch, keep parity with the untouched POSIX path) rather than a nonexistent global stdlib-only policy.

### [NIT:design] Sweep-vs-in-flight-retry race not addressed
**Section:** Decisions → `teardown-safety-net` (Verification note) **Issue:** The note establishes `git worktree remove --force` deregisters from `git worktree list` before the in-process rmtree retry loop even starts; a concurrently-running mill-cleanup sweep could therefore race the original process's own retries against the same directory during that window (worst case ~2s). **Fix:** Note this as an accepted, benign race (double-rmtree is idempotent-ish, not data-loss) or have the plan add a lock/skip-if-recently-touched guard.

## Verdict

REQUEST_CHANGES
Two sourced technical misattributions in the bg-liveness rationale need correcting before plan writing.
MILL_REVIEW_END
