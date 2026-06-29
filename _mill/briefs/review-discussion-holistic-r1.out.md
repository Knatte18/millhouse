I have verified the discussion's key claims against the source files. The discussion is well-grounded and accurate on line numbers, regex structure, the `reads-not-backtick-path` interaction, and existing check names. I found one substantive gap and a few notes.

MILL_REVIEW_BEGIN
# Review: Add first-class Moves/Renames field to plan cards for rename-heavy batches

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-29
```

## Findings

### [GAP] git diff -M threshold false-BLOCKs the motivating workload
**Section:** Decisions > verification-scope (mechanical check) + Problem
**Issue:** The check emits deterministic BLOCKING when a planned Move lands as add+delete, relying on git's default `-M` (50%) similarity, but the stated motivating workload (line 14-15: "module renames + kernel extractions") and the allowed "seam splits" (line 138, 207) deliberately reduce the moved file's content below 50%, so a correctly-executed `git mv` + extraction would falsely report add+delete and BLOCK.
**Fix:** Decide and document the rename-detection threshold (e.g. `-M<n>%`/`--find-renames`) and an escape path for legitimate low-similarity renames (split-aware handling, or downgrade to NIT when similarity is borderline), since the pure-function tests and the git invocation both depend on this choice.

### [NOTE] Mechanical check contradicts _review_code.py invariant
**Section:** Technical context > mechanical-check-placement
**Issue:** `_review_code.py` opens with "v2 code review does NOT look at git diff... The reviewer never scrapes git for files"; the new git `--name-status -M` check (and the existing `bulk_files_with_diff` at line 944) contradict that stated invariant and will mislead future readers.
**Fix:** Have the plan update the module docstring to scope the "no git" rule to the LLM reviewer and document the backend's deterministic git usage.

### [NOTE] Holistic-scope behaviour of mechanical check unspecified
**Section:** Decisions > verification-scope
**Issue:** The check is described per-batch (`<batch-base>..HEAD`, start_sha read per-batch around line 240), but `scope="holistic"` code review has no per-batch start_sha and the discussion does not say whether/how the mechanical check runs there.
**Fix:** State that the mechanical check runs in per-batch review only (or define the base SHA for holistic).

### [NOTE] Card-field position of Moves left ambiguous
**Section:** Scope / Decisions > moves-required-field
**Issue:** "Required 7th field" does not say whether `Moves:` sits after `Deletes:` (semantic grouping with Creates/Deletes) or after `Commit:` in the template; planner output consistency depends on it.
**Fix:** Fix the template field order explicitly (recommend after Deletes).

## Verdict
GAPS_FOUND
Sound and well-grounded, but the -M threshold would false-BLOCK the very rename+extraction workload it targets.
MILL_REVIEW_END
