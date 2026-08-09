MILL_REVIEW_BEGIN
# Review: mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; cannot independently confirm exact point version)
reviewed_file: _mill/discussion.md
date: 2026-08-09
```

## Findings

### [GAP] `--revise`'s "Phase 0" heading collides with mill-plan's own conventions
**Section:** Decision `mill-plan-revise-reentry` (#786) **Issue:** The decision names the new section "Phase 0 — Parse arguments," copying mill-setup's literal heading text verbatim, but `mill-plan/SKILL.md` has no "Phase N" numbering convention at all — its Entry section already uses a differently-named "Step 0" (load `mill:conversation`) plus numbered steps 1-4, and "Phase:" is separately reserved for the downstream named phases (`### Phase: Plan`, `### Phase: Plan Review`, etc. under `## Phases`). Verified: `mill-plan/SKILL.md` line 15 is literally "**Step 0: Load `mill:conversation`.**", and the phase-table lookup requiring interception by `--revise` (the `approved: true` → halt row) is Entry step 4 (line 46), which itself depends on `status_path`/`plan_dir` resolved in steps 1 and Path Setup. **Fix:** Specify the new section's actual heading (e.g. "Entry step 0.5" or fold into existing Step 0) and its exact position relative to existing Entry steps 0-4, rather than reusing mill-setup's "Phase 0" name unmodified.

### [NOTE] git-pr precedent overstated for the token-walk/halt convention
**Section:** Technical context, `--revise` precedent citation **Issue:** The claim that git-pr "uses a left-to-right token-walk with an explicit 'unknown token' halt" doesn't match what was read: git-pr only strips/ignores one specific flag (`--skip-task-branch-guard`) via a substring case-match and takes the first remaining token positionally — it has no unknown-token halt at all (verified `git-pr/SKILL.md` lines 38-48). mill-setup is the accurate precedent (confirmed: `### Phase 0 — Parse arguments`, token-walk, explicit halt on unknown token, lines 99-116). **Fix:** Drop git-pr as a precedent for the halt behavior, or narrow the citation to mill-setup only.

## Verdict

GAPS_FOUND
One GAP: `--revise`'s proposed "Phase 0" heading/placement conflicts with mill-plan's existing Step/Phase naming and ordering.
MILL_REVIEW_END
