MILL_REVIEW_BEGIN
# Review: mill-go: done-gate halt path and cleanliness-gate recovery are under-documented

```yaml
duration_s: 277.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [NIT:consistency] New `run_gate` snippet breaks Handoff's own halt-parsing prose
**Demoted-from:** BLOCKING
**Section:** Decision `done-gate-classifier-safe-invocation`, and `handoff.md` "0. Pre-done gate" (verified: lines 103-130).
**Issue:** The decision's rewritten snippet is `result = _done_gate.run_gate(gate_cmd, git_root); print(json.dumps(result))` with no `sys.exit(1)` on failure, and `run_gate`'s documented return shape uses key `"result"` (matching `run_preflight`). But the immediately-following, unedited Handoff prose (lines 127-130) still says "If the exit code is non-zero and the JSON line has `status: blocked`, halt" — the bash process will now always exit 0, and the field is `result` not `status`, so the halt condition as written can never fire and the gate silently stops blocking anything.
**Fix:** Either have `run_gate`'s caller `sys.exit(1)` on `result["result"] == "blocked"` (Handoff would still need this decided) or rewrite the classification prose to branch on `result["result"] == "blocked"` directly instead of exit code + `status` key; the discussion never states which, and never flags that this downstream text needs a corresponding edit.

### [NIT:scope] Builder-lock-release decision doesn't say whether `_notify.notify` is also added
**Section:** Decision `builder-lock-release-all-handoff-halts`.
**Issue:** The decision cites the canonical `### Blocked` shape (`_notify.notify(...)`, then lock release, then halt) as the pattern to mirror, but handoff.md's four halt paths currently call none of `_notify.notify` — the "In:" scope bullet only asks for lock release, leaving it ambiguous whether notify-parity is also wanted.
**Fix:** State explicitly whether `_notify.notify` calls are in scope for these four halts or deliberately out of scope.

## Verdict

APPROVE
One BLOCKING: the new run_gate snippet silently defeats Handoff's own done-gate halt check.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
