MILL_REVIEW_BEGIN
# Review: mill-implementer: commit_sha transcription/truncation and final-status-line reliability

```yaml
duration_s: 216.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [NIT:consistency] Named "existing tests assert commit_sha" claim is false
**Demoted-from:** BLOCKING
**Section:** Decisions > rename-conflicts-finalize-field; Testing
**Issue:** Read in full, `test_15_stage_finalize_conflicts`, `test_19_finalize_conflicts_accepts_parity_flags`, and `test_2x_stage_finalize_conflicts_reaches_gate` in `test-millpy-merge-in-subagent.py` never assert the output JSON's `commit_sha` key (no `data["commit_sha"]`/`assertDictEqual` anywhere in the file) — `commit_15`/`test_19` only check `data["status"]`/mocked-call kwargs, and `test_2x_...reaches_gate` exercises the stuck/marker-gate path where `_forward_output`'s fallback SHA block is never reached at all. The `commit_sha` string in their fixture text is a *self-reported input* value `_forward_output` already discards, not something these tests check on output.
**Fix:** Re-verify which (if any) named tests actually need edits versus relying solely on the one new regression test already planned in Testing; correct the enumeration before plan writing so the plan doesn't budget work against a false premise.

### [NIT:scope] pre_merge_head doc-update target is unverified
**Section:** Technical context (mill-merge-in/SKILL.md bullet)
**Issue:** Grepped all of `plugins/mill/skills/` for `commit_sha`: no file documents consuming the conflicts-finalize envelope's SHA field by name (the `mill-merge-in/SKILL.md` `merge --continue` note at issue only discusses the `discarded` field). The "whichever file documents consuming the finalize envelope's SHA field" hedge may have no actual target.
**Fix:** State plainly during planning if no doc currently names the field, so the doc-update line item is dropped rather than searched for indefinitely.

### [NIT:consistency] #978 rationale claims an "instruction to restate" that doesn't exist
**Section:** Decisions > no-prose-commit-sha
**Issue:** `implementer-brief.md`'s `## Report` section (read in full) contains no existing instruction telling the implementer to restate `commit_sha` in prose — only a card-count self-check about honest completion counts. The rationale's "removing the instruction to restate it" implies deleting existing text; the actual change is adding a new prohibition.
**Fix:** Reword the rationale to "add a new prohibition" rather than "remove an instruction" so the plan writer doesn't search for text to delete that isn't there.

## Verdict

APPROVE
The affected-test enumeration for the #953 field rename is factually wrong per source and needs correction.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
