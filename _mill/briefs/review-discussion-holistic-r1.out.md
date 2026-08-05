MILL_REVIEW_BEGIN
# Review: mill-go's one-shot pre-batch-1 baseline can't cover a task's own later per-batch-baseline capability

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-05
```

## Findings

### [GAP] subprocess/psmux has no distinct `--stage finalize` call point
**Section:** Decision: hook placement
**Issue:** Subprocess/psmux dispatch never invokes `--stage finalize` separately — it backgrounds a bare `millpy-implement.py <batch_name>` (defaulting to `--stage full`), whose handler runs dispatch and finalize (`_forward_output`, reading `batch_verify_baseline` at millpy-implement.py:1014) inside one process (millpy-implement.py:966-1036). The only literal `--stage finalize` invocation in mill-go/SKILL.md is inside the Agent-mode-only step 6 (SKILL.md:301).
**Fix:** Clarify the actual subprocess/psmux insertion point (e.g. before the `millpy-implement.py <batch_name>` background dispatch, or a code-level check inside the `--stage full` handler itself) — "immediately before `--stage finalize`, shared across both dispatch modes" is not literally true for subprocess/psmux.

### [GAP] trigger condition fires on batches that can never have a baseline
**Section:** Decision: retry trigger condition (no file-diff detection)
**Issue:** `_enumerate_batch_verify_triples` (millpy-implement.py:207-217) permanently skips any batch whose `verify:` frontmatter resolves to `None` (docs-only/no-verify batches), so such a batch's `verify_baseline_failures` stays unset forever, independent of any retry. Combined with "at most once per task run," a no-verify batch reaching finalize before a batch that genuinely needs recapture would consume the single retry attempt on a batch that structurally could never benefit.
**Fix:** Gate the "still unset" trigger on the batch also having a non-`None` resolved verify command, not just an unset `verify_baseline_failures` field.

### [NOTE] "once per task run" state-tracking mechanism unstated
**Section:** Decision: retry cadence — once per task run
**Issue:** No field is named for tracking "already attempted this run"; Technical Context's "no schema changes needed" rules out a persisted status.md field, implying an in-memory Builder variable (matching the existing `agent_id` precedent) — but this isn't stated, and such state resets on any mill-go session restart within the same task, so the actual bound achieved is "once per session," not "once per task lifetime."
**Fix:** State explicitly that the flag is a local Builder variable scoped to the current mill-go invocation, and note the cost-bounding rationale only holds within one session.

## Verdict

GAPS_FOUND
Hook-placement premise is false for subprocess/psmux, and the trigger condition can waste the single retry on a no-verify batch.
MILL_REVIEW_END
