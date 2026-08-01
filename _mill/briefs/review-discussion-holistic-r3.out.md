MILL_REVIEW_BEGIN
# Review: Add mill-quick: skip-review pipeline for simple tasks

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; brief pins me as sonnethigh)
reviewed_file: _mill/discussion.md
date: 2026-08-01
```

## Findings

### [GAP] No wiki `ready-to-merge` phase flip on done-gate success
**Section:** Scope (In) / Decisions — none currently cover this; Technical Context's mill-merge/mill-finalize bullet only checks `phase: done`
**Issue:** On verify success, mill-quick calls only `_status.append_phase(status_path, "done", ts)`, explicitly said to "mirror mill-go's Handoff Step 1 exactly" — but mill-go's Handoff Step 2 (`_client.set_phase(wiki_path, slug, "ready-to-merge")`) is a separate step the discussion never mentions or decides to skip. Verified: `mill-go/SKILL.md` Handoff step 2 flips Home.md via `set_phase`; `mill-status/SKILL.md`'s phase-reference table maps `[ready-to-merge]`+`done` to "written by mill-go Handoff step 2, next action: run /mill-merge"; `mill-cleanup/SKILL.md`'s states-handled table has no row for `[active]`+`done` (mill-quick's produced state) — only `[ready-to-merge]`+`done` ("Skip — waiting on mill-merge"). Without the flip, a mill-quick-completed task shows Home.md `[active]` with status.md `phase: done`, an undocumented combination neither mill-status nor mill-cleanup's tables recognize, and mill-status won't surface the "run /mill-merge" prompt the way it does for the full pipeline.
**Fix:** Decide explicitly whether mill-quick's done-path also calls `_client.set_phase(wiki_path, slug, "ready-to-merge")` (mirroring mill-go Handoff Step 2, not just Step 1) or is an accepted, stated limitation that mill-status/mill-cleanup won't correctly reflect a mill-quick-completed-but-not-yet-merged task.

## Verdict

GAPS_FOUND
Missing wiki ready-to-merge phase flip on mill-quick's done path breaks board-visibility invariants mill-status/mill-cleanup rely on.
MILL_REVIEW_END
