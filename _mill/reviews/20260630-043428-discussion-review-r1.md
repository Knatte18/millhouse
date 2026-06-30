MILL_REVIEW_BEGIN
# Review: Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-30
```

## Findings

### [GAP] Warm-resume SendMessage mechanism unverified
**Section:** Decisions / warm-session-resume-recovery; Scope (mill-go SKILL routing)
**Issue:** The primary recovery hinges on `SendMessage(<retained agent_id>, ...)` to a warm background agent, but no such capability exists anywhere in the codebase (the only `SendMessage` is an unrelated Win32 call in `_winenv.py`), and `SKILL.md` step 3 (line 121-123) describes Agent dispatch as fire-and-forget with no documented runtime-ID handle. The design rests solely on a one-off human improvisation as proof it works.
**Fix:** Confirm and cite the Agent-tool API that returns/retains a reusable runtime ID and supports re-messaging a background agent; if absent, the design collapses to the explicitly-rejected fresh-redispatch fallback and must be re-scoped.

### [GAP] Additive constraint contradicts transient->incomplete reclassification
**Section:** Constraints (line 98) vs Scope (line 25) / Testing (line 109)
**Issue:** Constraints state "every existing routing (transient/...) keeps current behavior. No existing test for those types may change verdict," yet Scope changes `_batch_completeness_stuck` and `_reclassify_verify_failure` from `transient` to `incomplete`. Existing tests assert the old verdict (e.g. test-implementer-common.py case 27a, line 1257, "fewer commits than cards -> stuck/transient") and WILL change. A plan writer cannot satisfy both as written.
**Fix:** Reword the additive constraint to carve out the two intentionally-reclassified detections (their tests MUST update to `incomplete`); only the other `transient` emitters (API-error markers, network) stay unchanged.

### [GAP] Subprocess `incomplete` routing auto-accepts partial batch
**Section:** Scope (line 28) / Q&A (subprocess routing); Gotchas (line 94)
**Issue:** `incomplete` in subprocess/psmux routes to "the existing `commits_made > 0` handling," whose autonomous-mode auto-pick is option 1 "skip to cleanliness gate ... as if the implementer had reported success" (SKILL.md line 411-412). For a provably-partial batch this ships unfinished work -- the exact #574 false-success that `incomplete` was introduced to prevent.
**Fix:** Specify that `incomplete` in autonomous subprocess/psmux mode must auto-`--resume` once (never skip-to-cleanliness), reconciling with the existing `commits_made>0` auto-pick.

### [NOTE] Shared `_reclassify_verify_failure` touches the explicit-success path
**Section:** Constraints (line 99 "explicit-success path byte-for-byte unchanged")
**Issue:** `_reclassify_verify_failure` is invoked on the `status=="success"` path (_implementer_common.py line 883), so changing its `0<content<card_count` branch to `incomplete` alters the explicit-success path's verify-failure routing -- tensioning the byte-for-byte-unchanged constraint that Scope says only inference paths gain stricter checks.
**Fix:** State whether the explicit-success verify-failure reclassification should also become `incomplete`, or gate the rename to inference-path callers only.

### [NOTE] Normalized `status: incomplete` envelope lacks `commits_made`
**Section:** Scope (line 27) / Q&A (implementer partial-progress JSON)
**Issue:** The implementer emits `{"status":"incomplete","cards_done":N,"cards_remaining":M,"session_id":...}` with no `commits_made`, but subprocess routing keys on `commits_made`. When `_forward_output` normalizes this parse, the field would be missing.
**Fix:** Require the normalization to compute and attach `commits_made` via `_content_commit_count` so subprocess routing parity holds.

## Verdict

GAPS_FOUND
Recovery mechanism feasibility and two constraint contradictions must be resolved before planning.
MILL_REVIEW_END
