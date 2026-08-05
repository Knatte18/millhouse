MILL_REVIEW_BEGIN
# Review: mill-go's one-shot pre-batch-1 baseline can't cover a task's own later per-batch-baseline capability

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4-5 (self-assessed; task frontmatter says sonnethigh)
reviewed_file: _mill/discussion.md
date: 2026-08-05
```

## Findings

### [GAP] subprocess/psmux hook placement can't see the current batch's own commits
**Section:** Decision: hook placement (+ Scope: In, bullet 1)
**Issue:** Verified against `millpy-implement.py`: Agent-mode's hook (before step 6 `--stage finalize`, SKILL.md ~line 301) runs *after* the Agent tool call has already committed that batch's own cards, so the retry sees the batch's own fix to baseline machinery. subprocess/psmux's hook (before the `millpy-bg`-backgrounded dispatch, SKILL.md ~line 434) necessarily runs *before* that batch's implementer has committed anything (`--stage full`'s implement-then-finalize happens inside one synchronous process with no external call boundary to hook into, per the Decision's own rationale) — so for subprocess/psmux the retry can only ever see prior batches' commits, never the current batch's own in-flight fix. The two placements are therefore not functionally equivalent, only "the same underlying check... wired at different points" as claimed — a plan writer would reasonably assume symmetry. The original motivating incident (`mill-validate-verify-diagnostics-gaps` batch 6) happened to be rescued by *earlier* batches' commits, masking this asymmetry; a batch that itself introduces/fixes baseline machinery and also needs its own baseline recaptured would silently fail to benefit under subprocess/psmux dispatch, consuming the single once-per-run retry attempt on a checkout that structurally cannot contain the fix.
**Fix:** Either state this as an explicit, accepted limitation of subprocess/psmux mode (mirroring how the "once per session" cadence limitation is called out), or note that a plan writer should decide whether the once-per-run budget should skip/defer when the eligible batch is itself mid-dispatch under subprocess/psmux (i.e., the check can't yet know if the current batch will touch baseline code).

## Verdict

GAPS_FOUND
Hook-placement asymmetry between dispatch modes affects retry efficacy but is unacknowledged.
MILL_REVIEW_END
