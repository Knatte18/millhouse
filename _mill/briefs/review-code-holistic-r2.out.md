MILL_REVIEW_BEGIN
# Review: mill-go's one-shot pre-batch-1 baseline can't cover a task's own later per-batch-baseline capability — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-05
```

## Findings

### [BLOCKING] Unauthorized "Trigger check" addition misattributes `_status` to conditions 2/4
**Location:** `plugins/mill/skills/mill-go/SKILL.md:428-434`
**Issue:** Card 3 (`_mill/plan/02-per-batch-baseline-recapture-hook.md:66`) requires the `### 0.6` block inserted "verbatim ... adjust only if repo prose style requires trivial wording smoothing." The implementer inserted a new paragraph before "Trigger check" stating conditions 2 and 4 import `_paths`, `_plan_dag`, and `_status` via worktree-form `PYTHONPATH`. This is not trivial wording — it's a substantive rule beyond the plan text and beyond the Shared Decision's stated scope ("cache-vs-worktree execution path for the retry", `00-overview.md:37-41`, explicitly scoped to "the recapture invocation" only). Worse, it is internally wrong: `_status.read_batches` is used by condition 3 (`SKILL.md:438-439`), not conditions 2 or 4 — condition 2 uses only `_paths`, condition 4 uses only `_plan_dag`. As written, condition 3's PYTHONPATH form (cache vs. worktree) is left unspecified, which undermines the exact self-hosting-staleness problem this task exists to fix (e.g. a future self-hosting task modifying `_status.py` itself).
**Fix:** Either drop the added paragraph and let Card 3's plan text stand verbatim (letting the existing project-wide cache-form convention apply, or explicitly scoping the exception via an updated Shared Decision), or fix the paragraph to correctly say "conditions 2, 3, and 4" and get that scope expansion recorded in `00-overview.md`'s Shared Decisions section rather than added ad hoc in the batch body.

## Verdict

REQUEST_CHANGES
Unauthorized non-verbatim addition to the 0.6 block misattributes `_status` usage and leaves condition 3's execution path unspecified.
MILL_REVIEW_END
