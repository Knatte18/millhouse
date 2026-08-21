MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: Phase Plan Review gate, convergence, and DAG-validation correctness bugs

```yaml
duration_s: 334.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version unconfirmed)
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Findings

### [BLOCKING:design] #896 misdescribes step 4.5's current document position
**Section:** Decisions / #896. **Issue:** The decision claims "Step 4.5 ... sits between step 2 and 4a-4d," but in the current `mill-plan/SKILL.md` (verified by reading), step 4.5's heading is at line 488 — textually *between* 4b (line 475) and 4c (line 527), i.e. AFTER 4a and 4b, not before them. **Fix:** Correct the premise and specify whether step 4.5 itself must be relocated (moved before 4a) in the same batch, or add explicit placement instructions for the new unconditional append that actually precede 4a/4b in the document — as written, "insert immediately after step 4.5" would land the new call after 4a/4b's text, contradicting the stated goal of running it "BEFORE branching into 4a/4b/4c/4d."

### [NIT:consistency] #887's "batch" field rationale overstates convention uniformity
**Section:** Decisions / #887. **Issue:** The decision resolves the new check's error-dict `batch` field via `batch_name_to_path[B].stem` "to match every other check's error-dict convention," but `_check_parallel_modifies_overlap` (the check being reused/mirrored) and `_check_depends_on_batch_mismatch` both use `entry["name"]`, not the stem, in their own `batch` fields — verified in `_plan_validate.py` lines 1055 and 1141. **Fix:** Soften the rationale to "most other checks" or name the two exceptions; the chosen stem-based behavior itself is fine and need not change.

## Verdict

REQUEST_CHANGES
One BLOCKING: #896's placement instruction rests on an incorrect claim about step 4.5's current document position.
MILL_REVIEW_END
