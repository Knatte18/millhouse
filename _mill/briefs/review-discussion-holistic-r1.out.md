MILL_REVIEW_BEGIN
# Review: mill-go-base: orchestration robustness gaps

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-18
```

## Findings

### [BLOCKING:design] 1031's speculative baseline launch races a restarted entry-gate wait
**Section:** `### 1031-parallel-entry-baseline`
**Issue:** The early `--stage baseline` launch is recorded only in a session-local Builder variable, but `millpy-bg.py` dispatches via `popen_detached` (SKILL.md/millpy-bg.py) — a genuinely detached OS process outside the builder lock's lifecycle. The entry-gate wait's own documented interruption path (SKILL.md ~line 196-197: "if the wait itself is stopped/interrupted... re-running `/mill-go` will re-evaluate the phase... or re-arming the wait") is a first-class, expected recovery flow, not a rare edge case. On that restart the Builder-variable memory of the earlier launch is gone, so either a second early launch or step 0.5's own fallback launch fires a *second* `--stage baseline` process while the orphaned first one may still be running concurrently. Both write `_status.set_module_verify_baseline(status_path, result)` to the same `status.md` with no locking shown in `_status.py`. The decision's idempotency argument (cache-check-then-noop) only protects a re-invocation that sees an already-cached result — it does not prevent two concurrent computations from racing a read-modify-write on the same file.
**Fix:** Decision must specify how a restarted entry-gate wait detects or reconciles an orphaned earlier launch (e.g. persist the log-path on disk/in status.md rather than only in a Builder variable, or explicitly accept and justify the race) before this is closed.

### [BLOCKING:consistency] 995 rationale's "four TaskOutput call sites" contradicts its own action list and the source
**Section:** `### 995-taskoutput-write-only-warning`
**Issue:** The Decision names exactly three call sites (line 303, 325, 393). The Rationale says "confirmed via `grep` that none of the four `TaskOutput` call sites in `SKILL.md` currently carries any such warning." A `grep` of `TaskOutput(` across `SKILL.md` (and the rest of `mill-go-base/`) finds only three occurrences (303, 325, 393) — the same three the Decision already names. "Four" is factually wrong and internally inconsistent with the Decision's own list.
**Fix:** Correct "four" to "three" in the Rationale, or if a fourth site is genuinely intended, name it explicitly in the Decision's action list.

## Verdict

REQUEST_CHANGES
Two BLOCKING issues: an unaddressed concurrency race in #1031 and a self-contradictory site count in #995.
MILL_REVIEW_END
