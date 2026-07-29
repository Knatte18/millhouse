MILL_REVIEW_BEGIN
# Review: mill-plan/SKILL.md doc gaps: missing mill:conversation load, Phase: Plan commit step omits push

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] `-C <worktree>` audit claim contradicted by line 126
**Section:** Scope > Out (and Decisions > push-wording-scope)
**Issue:** Scope > Out claims a "`-C <worktree>` cross-check on every commit-producing line" found "no further gaps" among 4a/4b/4c/Handoff/the line-126 skip branch. Verified against source: line 126's skip-branch commit — `git -C <worktree> add <plan_dir> && git commit -m "mill-plan: skip plan review..."` — has the identical `-C <worktree>` omission on `commit` (present only on `add`) that lines 116/242 are being fixed for. 4a (line 205), by contrast, genuinely has `-C <worktree>` on both verbs.
**Fix:** Either extend push-wording-scope's `-C` normalization to line 126, or amend the Scope > Out claim to acknowledge this remaining inconsistency and state an explicit reason for leaving it unfixed.

### [GAP] mill-go "Step 0.5" collides with an existing "0.5" heading
**Section:** Decisions > mill-conversation-load-placement
**Issue:** The decision places the new load at "Step 0.5" in mill-go's Entry, citing "mill-go's existing convention ... e.g. '0.55', '0.5', '4.5' elsewhere in the file" as precedent. Verified: `### 0.5. Baseline pre-flight` and `### 0.55. Done-gate baseline pre-flight` are H3 headings in the unrelated per-batch dispatch loop (a different section with its own independent numbering restarting at 0), not in Entry — only `4.5.` is a genuine Entry-section precedent. Adopting "Step 0.5" in Entry reuses a label already bound to a different step elsewhere in the same file.
**Fix:** Pick a non-colliding label for the new Entry step (e.g. a number not already used as a heading anywhere in the file), or explicitly state in the decision that Entry-step numbering and per-batch-loop numbering are treated as independent namespaces and the reuse is intentional.

### [GAP] holistic-rounds-exhausted prompt misdescribed as having "(Recommended)"
**Section:** Scope > Out
**Issue:** Scope > Out asserts three prompts (`infrastructure` line 490, `transient` commits_made>0 lines 494-496, holistic-rounds-exhausted lines 769-774) "already show literal numbered `1)/2)/3)` text with `(Recommended)` suffixed correctly." Verified: the holistic-rounds-exhausted prompt reads `1) Rethink... / 2) Skip holistic... / 3) Block...` with no `(Recommended)` suffix anywhere, unlike the other two cited prompts which do carry it.
**Fix:** Correct the claim — note this prompt has no recommended option at all (still conformant under `mill:conversation`'s "if any" clause), rather than stating it shows "(Recommended) suffixed correctly."

## Verdict

GAPS_FOUND
Three source-verification mismatches in Scope/Decisions claims that a plan writer would otherwise trust as fact.
MILL_REVIEW_END
