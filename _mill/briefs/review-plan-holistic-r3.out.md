MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: Phase Plan Review gate, convergence, and DAG-validation correctness bugs — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: plan/
date: 2026-08-21
```

## Findings

### [BLOCKING:consistency] Card 1 leaves "Step 4.5" label after renumbering marker to 3.5
**Location:** Batch 1, Card 1. **Issue:** Card 1 renumbers only the literal `4.5.` marker token to `3.5.` and explicitly forbids altering any other text in the moved block, including the very next line `**Step 4.5: ERROR-only-aggregate retry (no round consumed)**` — the shipped section will read "3.5." followed by "Step 4.5: ...", self-contradicting, unlike the matching `1.5.`/`**Step 1.5: ...**` pattern elsewhere in the file. **Fix:** Also rename the bold sub-heading text from "Step 4.5" to "Step 3.5" as part of the same requirement.

### [BLOCKING:consistency] Batch 1 Scope asserts a false Batch-2 dependency/overlap
**Location:** Batch 1 (`01-review-loop-gate-doc-fixes.md`), `## Batch Scope`. **Issue:** The scope text states "Batch 2 depends on it, since both batches touch `mill-plan/SKILL.md` and must not run in parallel" — but the overview's Batch Index has Batch 2 `depends-on: []` (root batch), and Batch 2's own file edits only `_plan_validate.py`/`test-plan-validate.py`, never `mill-plan/SKILL.md` (deliberately excluded, per Batch 2's own Scope text). This dependency/overlap actually describes Batch 3, not Batch 2. **Fix:** Correct Batch 1's Scope prose to state it is a root batch with no forward dependency on Batch 2 (Batch 3 is the one depending on both).

### [BLOCKING:consistency] Overview Shared Decision mis-cites Card 6 for the #861 fix
**Location:** `00-overview.md`, `### Decision: pipeline.done_gate stays null`. **Issue:** The decision cites "per this plan's own #861 fix (Card 6, Batch 1 — the new 'verify it passes clean first' precondition on the Done-gate reminder)" — but #861 is implemented by Card 7 (Batch 1), not Card 6 (Card 6 is #901, out-of-worktree-target). **Fix:** Change "Card 6" to "Card 7" in this Decision.

### [NIT:consistency] "batch-verify scope is narrow" Decision omits Batch 3 from Applies-to
**Location:** `00-overview.md`, `### Decision: batch-verify scope is narrow`. **Issue:** The decision's body explicitly discusses Batch 3 ("Batches 1 and 3 are pure `mill-plan/SKILL.md` ... prose ... `verify:` is `null`") but the trailing "**Applies to:** Batch 1, Batch 2" line omits Batch 3. **Fix:** Add Batch 3 to the Applies-to list, or scope the body text to only Batches 1/2.

### [NIT:consistency] Tree-guard citation still lists step 4a as an append_phase site after Card 1 removes it
**Location:** Batch 1, Card 1 (Tree-guard safeguard paragraph edit). **Issue:** Card 1 deletes 4a's only `_status.append_phase` call (moving that write into the new step-3.5 unconditional append), but the same card's updated citation still reads "...the unconditional round-recorded append at step 3.5, and steps 4a/4b/4c/4d below" — 4a no longer makes any append_phase call, so listing it here is now a stale/inaccurate claim (harmless in practice since it's over-inclusive, but a leftover inconsistency). **Fix:** Drop "4a" from the citation's step list, leaving "steps 4b/4c/4d below".

## Verdict

REQUEST_CHANGES
Three BLOCKING consistency defects (stale step-4.5 label, false Batch-2 dependency claim, wrong card citation) need fixing before approval.
MILL_REVIEW_END
