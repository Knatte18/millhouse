MILL_REVIEW_BEGIN
# Review: mill-go-base: remove subprocess/psmux dispatch branches

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [NIT:scope] "millpy-bg" preamble at SKILL.md 557-559 sits outside the twelve-branch table
**Demoted-from:** BLOCKING
**Section:** Technical context / twelve subprocess/psmux branches table.
**Issue:** `### 1. Implement`'s "Background via millpy-bg:" heading (line 557) and its "Before invoking millpy-bg" cwd warning (line 559) sit *above* the `If dispatch == agent` / `If dispatch == subprocess` split at line 574/582 — unlike every other occurrence of that same warning (738, 819, 939, 957, 975 etc.), which sits *inside* its `If dispatch == subprocess` branch and is deleted with it. The twelve-branch table and "Also removed" list don't name 557/559, so a plan writer following them leaves this residual "millpy-bg" text behind, which fails the discussion's own proposed regression-guard assertion ("the literal string `millpy-bg` does not appear").
**Fix:** Add lines 557-559 explicitly to "Also removed," or fold their content into the (surviving) Agent-mode branch prose.

### [NIT:decision] Holistic cleanup block's ~13 call sites have no stated disposition
**Demoted-from:** BLOCKING
**Section:** Decisions / `remove-psmux-cleanup-block`; Technical context "Also removed."
**Issue:** For per-batch cleanup, the decision explicitly deletes "all of its invocation points" (5 named triggers). For holistic, the parallel bullet says only "delete Lines 1004-1005's `_llm_claude.cleanup_session` call" — but "invoke the holistic cleanup block" appears ~13 times through the Holistic section (996, 1027, 1198, 1218, 1220, 1255, 1261, 1271, 1272, 1275, 1280, 1287), all moving into `holistic-review.md`. It's unstated whether those call sites are also stripped (matching the per-batch treatment) or left invoking a now-empty stub.
**Fix:** State explicitly whether the holistic cleanup block's invocation sites are removed like the per-batch ones, or intentionally left as no-op calls.

### [BLOCKING:design] Renumbering-impact check names only 3 of ~6 stale step-reference families
**Section:** Technical context, "Also removed" bullet on line 224-225 / dispatch-mode preamble.
**Issue:** The bullet says removing Step 1 turns the pattern into "two-step" and instructs checking for stale "step 3"/"step 6"/"step 6.5" references. Grep of SKILL.md shows step **2**, step **4** (incl. 4(a)/4(b)/4(c)), and step **5** are each cross-referenced many times too (e.g. lines 74, 245-266, 297-375, 523, 576, 633, 662, 676-687, 703, 835, 947, 965, 983, 1062-1075, 1159-1214, 1314-1330, 1438-1440), plus mill-go2/SKILL.md references "step 3," "step 4," "step 4(a)," and "step 6.5.1/6.5.2." Following the named 3-string check alone misses most of the actually-stale references after the shift-by-one renumber.
**Fix:** Broaden the check to every numbered step (2 through 7, including sub-labels) in SKILL.md and mill-go2/SKILL.md, not just the three named strings.

### [NIT:scope] Poll-loop-max-wait line range overstates the section by ~10 lines
**Section:** Decisions / `remove-subprocess-poll-loop-maxwait`; Technical context "Also removed."
**Issue:** Both cite lines 395-432 for the "Subprocess/psmux poll-loop max-wait" section, but the section (including the per-batch cleanup sub-block) actually ends at ~422, with "**Why not fork?**" starting at 423.
**Fix:** Minor — the file already tells implementers to anchor on literal text over line numbers, so low risk, but worth a quick re-measure.

## Verdict

REQUEST_CHANGES
Three BLOCKING gaps: an unenumerated dead-path leftover, an undecided holistic-cleanup disposition, and an undercounted renumbering-check scope.
MILL_REVIEW_END
