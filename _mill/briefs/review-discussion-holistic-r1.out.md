MILL_REVIEW_BEGIN
# Review: Blocking phase-wait gate for mill-plan/mill-go chaining

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5
reviewed_file: _mill/discussion.md
date: 2026-07-30
```

## Findings

### [GAP] Wait phase-set omits upstream's own mid-loop resume phases
**Section:** Decisions > "Exact phase-table edit sites"; "Scope > In"
**Issue:** mill-plan writes `plan-review-r{N}`/`plan-fix-r{N}` during its review loop (mill-plan/SKILL.md:239,244) and mill-go's new wait branch only triggers on `discussed`/`discussing`/`planning` (unchanged trigger set, per the Decision's own text) — so mill-go started while mill-plan is mid-review-loop still falls into the unchanged "any other -> halt" row (mill-go/SKILL.md:83). Same shape on the other side: mill-start writes `discussion-fix-r{N}` mid-loop (mill-start/SKILL.md:228) but mill-plan's carve-out only covers `phase: discussing`, so that intermediate phase still lands in mill-plan's catch-all halt (mill-plan/SKILL.md:39). Review/fix loops are often the bulk of upstream wall-clock time, so this reintroduces babysitting for a common, not edge, case — the exact problem this task exists to remove.
**Fix:** Either extend both wait-trigger phase sets to include the respective mid-loop phases (`plan-review-r*`/`plan-fix-r*` for mill-go; `discussion-fix-r*` for mill-plan), or explicitly decide-and-document that mid-loop phases are deliberately out of scope with a stated reason.

### [GAP] `TaskStop`-on-Monitor interrupt handling is unverified against any source
**Section:** Decisions > "Operator interrupts the wait (`TaskStop` / harness-level stop)"
**Issue:** `TaskStop` appears nowhere else in this repo, and `Monitor` appears only once (cli/SKILL.md:32, a syntax note) with no documented stop/interrupt notification shape. The Decision analogizes to the Agent-mode dispatch stopped/interrupted precedent (which is specific to Agent-tool `agentId` + `<task-notification>`, mill-go/SKILL.md:125-151) without establishing that a `persistent: true` Monitor task exposes an equivalent interrupt signal, or what handle (task_id?) the orchestrator would retain to detect it — Agent-mode dispatch explicitly documents "record the agentId"; this Decision documents no analogous capture step for the Monitor call.
**Fix:** Confirm (or explicitly assume-and-flag) that Monitor delivers a distinguishable stopped/interrupted notification under `persistent: true`, and name what identifier the orchestrator retains to recognize it.

### [NOTE] Unit mismatch between config key and helper signature undocumented
**Section:** Decisions > "Poll interval and give-up timeout values"; "Poll script contract"
**Issue:** `pipeline.entry_wait_timeout_minutes` is in minutes but `build_wait_command(..., giveup_s, ...)` takes seconds — the discussion never states which SKILL.md call site performs the ×60 conversion.
**Fix:** Note in Technical Context (or a Decision) that the SKILL.md call site multiplies the config minutes value by 60 before calling `build_wait_command`.

## Verdict

GAPS_FOUND
Wait-phase coverage misses upstream mid-loop resume phases, defeating the task's own stated goal.
MILL_REVIEW_END
