MILL_REVIEW_BEGIN
# Review: Instrument and bound the verify runner

```yaml
duration_s: 105.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: C:\Code\millhouse\wts\verify-runner-instrumentation\_mill\discussion.md
date: 2026-10-14
```

## Findings

### [BLOCKING:design] Merge-in rollback discards the Verify log rows
**Section:** Decisions, "Durable record" (commit coverage, merge-in bullet) **Issue:** `mill-merge-in` step 4 rolls back with `git reset --hard "$CHK"` on a stuck verify, and step 5 (the only commit that would stage `status_path`) runs on the success path only, so rows written by failed or timed-out merge-in replays (the rows the task most wants) are reverted along with earlier uncommitted rows. **Fix:** State the disposition for merge-in failure paths (commit `status_path` before rollback, or explicitly accept that failed merge-in rows are not durable) and reconcile with "every command that times out produces a `## Verify log` row".

### [BLOCKING:design] Timed-out merge-in verify has no defined handling before the fixer dispatch
**Section:** Decisions, "Timeout" (merge-in bullet) and "Merge-in SKILL replay goes through a CLI" **Issue:** Only the post-fix re-verify is said to use the stuck shape; the initial verify in `_run_verify_fix` (prepare and full stages) and the new CLI replay both lead to a fixer-LLM dispatch on failure, and that dispatch re-runs the same hung command, so one hang can cost several full timeout budgets and hand the LLM a "timeout" as if it were a test failure. **Fix:** Decide whether a `timed_out` result skips the fixer and goes straight to stuck/escalation at the initial-verify and CLI-replay sites, and state the resulting envelope.

### [NIT:design] Config and status_path reach `_done_gate` by an unstated route
**Section:** Decisions, "Timeout" / "Durable record" **Issue:** `run_gate` / `run_preflight` take only `(gate_cmd, git_root)` and the SKILL snippets resolve neither a timeout nor `status_path`; the `timeout_seconds(cfg)` `ValueError` would also fall outside the never-raise contract if resolved in the snippet rather than inside the function's try. **Fix:** Name where the done-gate resolves timeout and `status_path`, and that an invalid value is returned as `blocked` rather than raised.

### [NIT:ambiguity] Output decoding for the `.out` file is unspecified
**Section:** Decisions, "Shared runner module" **Issue:** `output` is "read from the output file" with no encoding or error policy, while the never-raise contract and the existing `text=True` behaviour both depend on it. **Fix:** State the encoding and `errors=` mode used when reading the file.

## Verdict

REQUEST_CHANGES
Two merge-in failure-path behaviours (row durability, timeout-to-fixer routing) are undecided and affect the plan.
MILL_REVIEW_END
