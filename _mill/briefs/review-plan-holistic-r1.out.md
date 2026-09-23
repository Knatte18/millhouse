MILL_REVIEW_BEGIN
# Review: mill-plan/verify/implement pipeline: misc small bugs, round 3 — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
date: 2026-09-23
```

## Findings

### [NIT:consistency] Card 3's "no guard today" example list is mostly wrong
**Location:** batch 02-status-path-coercion / card 3 **Issue:** the Requirements' second bullet cites `append_inferred_success_log`, `append_fork_fallback_log`, `append_fixer_fork_fallback_log`, and `read_fixer_fork_fallback_log` as functions with "no guard today", but `plugins/mill/scripts/_status.py` shows each already calls `_require_path(status_path, "<fn>")` (lines 1393, 1506, 1565, 1626 respectively) — only `resume_batch` genuinely lacks a direct guard call. **Fix:** trim the example list to `resume_batch` (or state the rule generically: "every public function whose first parameter is `status_path`, guarded or not") since the four misnamed functions are already covered by bullet 1.

### [NIT:consistency] Card 4's inserted timeout note is self-contradictory on the numbers
**Location:** batch 03-verify-guidance-docs / card 4 **Issue:** the verbatim text block to insert says "a single run has taken about two minutes, over the default 2-minute Bash timeout" — "about two minutes" and "the default 2-minute timeout" are the same figure, so the sentence doesn't clearly establish that the run exceeds the limit (unlike `mill-go-base/SKILL.md`'s own parallel note, which cites a real timeout risk without conflating the two numbers). **Fix:** either give a more specific over-limit figure (e.g. "a little over two minutes") or drop the numeric comparison and just state it can exceed the default.

## Verdict

APPROVE
Mechanism claims verified against source; two cosmetic wording/example inaccuracies, no BLOCKING issues found.
MILL_REVIEW_END
