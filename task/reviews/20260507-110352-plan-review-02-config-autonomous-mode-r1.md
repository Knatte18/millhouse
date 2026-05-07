# Review: 16 (A) — Autonomous bug-fix pipeline (mill-autofix) — 02-config-autonomous-mode

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-config-autonomous-mode
date: 2026-05-07
```

## Findings

### [BLOCKING] Card 7 Location 1 insertion point contradicts its own guard scope
**Step:** Card 7, Location 1 (Stuck escalation)
**Issue:** The card says insert "at the very top of the `### Stuck escalation` section (before the `transient` bullet)" yet the guard's text qualifies the transient case as "(already-retried)". The stuck escalation section's first bullet (`**CLI emits \`stuck_type: transient\`**`) implements a first-pass one-retry policy that the guard must not short-circuit — but inserting at the very top of the section fires the guard before that retry has been attempted, blocking on the first transient failure instead of the second.
**Fix:** Change the insertion location to between the first and second bullets of the stuck escalation section — i.e., after the "CLI emits / apply one-retry" bullet and before the "`transient` (already retried once)" bullet — so the guard fires only when user interaction would occur under normal (non-autonomous) mode.

### [NIT] `ts` unresolved in Card 6 guard text
**Step:** Card 6, Locations 1 and 2
**Issue:** Both insertions use `_status.append_phase(status_path, "blocked", ts)` but `ts` is not defined in the surrounding step-5/step-6 scope (the skill uses `iso_ts = _timestamp.now_utc_iso()` in step 4a; there is no `ts` binding at steps 5 and 6).
**Fix:** Replace `ts` with `_timestamp.now_utc_iso()` inline in both insertions, matching the existing pattern.

## Verdict

REQUEST_CHANGES — one BLOCKING on the mill-go stuck-escalation insertion location.