Now I have everything I need to write the review.

# Review: 46 (A) — Home.md state machine + split mill-merge teardown into mill-cleanup

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-11
```

## Findings

### [GAP] Branch-protection fallback flip not addressed

**Section:** Technical context — `mill-merge` SKILL.md
**Issue:** The Technical Context pseudocode for the Home.md `[pr-pending]` flip covers only the explicit PR path (`git.require-pr-to-base: true`, SKILL.md line 98); the branch-protection fallback sub-path (lines 148–164) also appends `pr-pending` to status.md and halts at Step 11 with an explicit "Do not run Steps 6, 7 (Home.md flip)" directive. Both paths end in PR-pending state, so both should flip Home.md — but the discussion is silent on the fallback. A plan writer may implement the flip only in the primary path, leaving the fallback with the `[active]`-overloading problem the decision rationale explicitly calls out.
**Fix:** State explicitly that both PR-creation points in Step 5 (primary and branch-protection fallback) receive the Home.md `[pr-pending]` flip before halting.

### [NOTE] PR-path re-entry text stale after Steps 8–10 removal

**Section:** Technical context — `mill-merge` SKILL.md
**Issue:** The `## PR-path re-entry` section (current SKILL.md lines 261–270) says "The rest of the teardown (tag, Home.md flip, **worktree/branch/portal removal**, legacy wiki cleanup) runs as normal" for the MERGED case. After Steps 8–10 are removed, this prose still enumerates worktree/branch/portal removal as part of re-entry, which contradicts the teardown-split intent. The scope lists Step 12 as updated but does not mention the PR-path re-entry section.
**Fix:** Add `mill-merge` SKILL.md PR-path re-entry section to scope: remove "worktree/branch/portal removal" from the "runs as normal" list and add a note directing the operator to run mill-cleanup.

### [NOTE] `build_plan` note claims Home.md is the detection gate

**Section:** Technical context — `millpy-cleanup.py`
**Issue:** The parenthetical "note: these come from Home.md, not status.md phase" on the `elif phase == "pr-pending"` branch is the opposite of what the code does — `phase` is read from status.md (same as all other branches). The branch-protection fallback already writes `pr-pending` to status.md in the current SKILL.md (Step 5 line 151), so status.md detection is the actual gate. The note as written would lead a plan writer to look for a Home.md-based detection path that doesn't exist in the pseudocode.
**Fix:** Reword the note: "detected via status.md phase `pr-pending` (appended by mill-merge Step 5); Home.md `[pr-pending]` is the human-visible coordination signal."

## Verdict

GAPS_FOUND
Branch-protection fallback flip coverage is unspecified and would cause an incomplete implementation.