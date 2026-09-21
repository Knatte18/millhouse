MILL_REVIEW_BEGIN
# Review: mill-go/mill-merge-in orchestration robustness gaps, round 2 — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-21
```

## Findings

### [BLOCKING:scope] Card 7 edits `mill-plan/SKILL.md` but never declares it
**Location:** Batch 3 / Card 7. **Issue:** Requirements instruct adding a `"verify-untested-tag-in-touched-package"` row to `mill-plan/SKILL.md`'s Step 1.5 fix table (confirmed present at `plugins/mill/skills/mill-plan/SKILL.md` line 362), but Card 7's `Edits:` lists only `_plan_validate.py`/`test-plan-validate.py`, and `mill-plan/SKILL.md` is absent from Batch 3 entirely and from the overview's `## All Files Touched`. **Fix:** Add `plugins/mill/skills/mill-plan/SKILL.md` to Card 7's `Edits:` and to the overview's `## All Files Touched`.

### [BLOCKING:scope] Card 3's completeness fallback misses the `--stage full` call site
**Location:** Batch 1 / Card 3. **Issue:** `millpy-implement.py`'s `main()` computes `card_ids`/`commit_none_card_ids` once (around the `_batch_text` read) and feeds them into two separate call sites — `finalize_from_output(...)` for `--stage finalize`, and a direct `_forward_output(...)` call for `--stage full` (verified at both call sites, both passing identical `card_ids=card_ids`). Card 3's Requirements say to thread `card_commit_messages` only into "the `finalize_from_output` call," leaving the `--stage full` call's demotions unfixed for the identical self-resolve-remint false-negative this card exists to close. **Fix:** Thread `card_commit_messages` into both call sites, or state explicitly why `--stage full` is out of scope.

### [NIT:design] Synthetic signature may not dedupe across baseline corroboration runs
**Location:** Batch 1 / Card 1, interaction with `_verify_baseline._signatures_for_pair`. **Issue:** `_signatures_for_pair` unions two runs' `_extract_failure_signatures` output via exact-string dedup (`seen` set). A synthesized `NONZERO_EXIT: exit {rc}: {first_line}` signature embeds the raw first output line, which can differ slightly between the two corroboration runs for the same non-test failure (timestamps, ordering), producing two distinct entries in the persisted baseline instead of one. **Fix:** Note this in Batch Tests or normalize the synthetic line before returning it.

### [NIT:consistency] Overview's test-convention Decision misdescribes `test-merge-in-subagent.py`
**Location:** `00-overview.md`, Decision "test convention." **Issue:** The Decision lists `test-merge-in-subagent.py` alongside the files batches actually "extend," but no card in Batch 4 edits it — Batch 4's own `## Batch Tests` correctly clarifies it is only run for regression safety (shared fixtures), never edited. **Fix:** Reword the Decision to separate "extended" files from "re-verified for regression safety."

## Verdict

REQUEST_CHANGES
Two scope gaps (undeclared `mill-plan/SKILL.md` edit; incomplete `--stage full` fix) must be resolved.
MILL_REVIEW_END
