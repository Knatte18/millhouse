MILL_REVIEW_BEGIN
# Review: mill-go: concurrency, silently-ignored fields, and bookkeeping bugs in execution/handoff — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (Sonnet 5, per Anthropic's current naming)
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:design] Card 10 (#973) never updates `All Files Touched` after descoping a batch
**Location:** Batch 3, Card 10 (`millpy-descope-batch.py`, step 7-11). **Issue:** The CLI's own behavior spec ("edit two files, move one, commit" per the Batch Scope prose, and the numbered steps 1-13) edits `00-overview.md`'s Batch Index and `status.md` but never prunes `## All Files Touched` — if the descoped batch owned a file no surviving batch edits, that section now overclaims, and mill-go never re-runs `_plan_validate.run()` at execution time (confirmed: no `_plan_validate`/`plan_validate` reference anywhere in `mill-go-base/SKILL.md`) to ever catch or self-correct the drift. **Fix:** Add a step computing the surviving union of `Edits:`/`Creates:`/Move-target paths across remaining batches and rewriting `## All Files Touched` accordingly, or explicitly document this as an accepted, deliberate limitation in the Batch Scope prose.

### [NIT:consistency] Card 7's insertion anchor is only spelled out for SKILL.md, not holistic-review.md
**Location:** Batch 2, Card 7. **Issue:** The per-batch insertion point is given as an exact sentence pair ("between the existing 'Regardless of whether a plan edit was made...' sentence and the existing 'Before re-firing, record the self-resolve...' sentence") — verified accurate against `SKILL.md` lines 854-855 — but the "parallel change" to `holistic-review.md`'s equivalent bullet only names the bullet, not its analogous anchor sentence (which reads "Before re-invoking, record the self-resolve..." at line 187, not "re-firing"). **Fix:** Add the equivalent anchor-sentence pair for `holistic-review.md` explicitly, mirroring the SKILL.md phrasing.

## Verdict

REQUEST_CHANGES
Card 10 leaves `## All Files Touched` unmaintained after a descope; one NIT on Card 7's holistic-review.md anchor text.
MILL_REVIEW_END
