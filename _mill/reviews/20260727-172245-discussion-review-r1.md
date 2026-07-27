MILL_REVIEW_BEGIN
# Review: mill-go verify/cleanup gates misclassify build-tag deletions and round-suffixed phases

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewed_file: /home/knatte/Code/millhouse/wts/mill-go-verify-gate-misclassification/_mill/discussion.md
date: 2026-07-27
```

## Findings

### [GAP] added_dirs deletion test case is self-contradictory
**Section:** Testing -- Bug 1, second bullet
**Issue:** The suggested construction ("a two-file directory where one file gains a tag and the whole directory is deleted in the same batch") cannot occur: `git diff` shows a deleted file's original lines only as removals, never additions, so a file can register as an added-tag transition (added=1, removed=0) only if it still exists at HEAD -- which means its directory necessarily still exists on disk too. A directory that is truly gone can only ever surface via `removed_dirs`, never `added_dirs` (verified against `_go_build_tag_retiering_stuck` and `_parse_go_build_tag_diff` in `_implementer_common.py`).
**Fix:** Drop the "two-file directory ... deleted" construction; specify the fallback concretely: reuse case 66a's git setup (tag added, directory survives in git), then physically remove the directory from disk (e.g. `shutil.rmtree`) without committing, before calling `_go_build_tag_retiering_stuck` -- this exercises the isdir() check against the live filesystem exactly as the gate itself reads it.

### [NOTE] Bug 2 test citation overstates line-276 assertions
**Section:** Testing -- Bug 2, second bullet
**Issue:** The new integration test is said to mirror the existing "implementing" test at `test-cleanup.py` ~line 276, including a `plan.to_report == []` assertion, but that existing test (confirmed at lines 267-285) only asserts `to_remove_done`/`to_remove_abandoned`/`to_reset_home` are empty -- it never checks `to_report`.
**Fix:** Clarify that the `to_report == []` assertion is new, not literally mirrored from the cited test; harmless as written.

### [NOTE] Authoritative append_phase call-site list omits 2 files
**Section:** Technical context -- Bug 2 files
**Issue:** Technical Context names only `mill-plan`/`mill-go`/`mill-start` SKILL.md as "the authoritative list" of `append_phase` call sites, but `mill-finalize/SKILL.md` and `mill-merge/SKILL.md` also call it (for `pr-pending`). The enumerated regex/exact set in Decisions is still complete -- `pr-pending` is correctly excluded elsewhere -- so this doesn't affect correctness, only the citation's completeness.
**Fix:** Widen the sentence to `plugins/mill/skills/*/SKILL.md`, matching the broader (and accurate) scope the Decision's own rationale already uses.

## Verdict

GAPS_FOUND
One GAP: Bug 1's added_dirs deletion test scenario as described is unbuildable; two minor citation NOTEs.
MILL_REVIEW_END
