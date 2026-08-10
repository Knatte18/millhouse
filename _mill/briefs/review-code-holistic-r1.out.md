MILL_REVIEW_BEGIN
# Review: mill-go/mill-plan SKILL.md: undocumented mutation sequences, precondition bugs, and non-portable cross-references — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-10
```

## Findings

None.

Verified end-to-end against both batches:

- Card 1 (#810): the three new mutation-sequence clauses at `plugins/mill/skills/mill-go/SKILL.md:1129`, `:1149`, `:1151` match the plan's exact required text byte-for-byte, use the correct 3-space indent, and leave the pre-existing halt sentences unchanged. `_status.set_blocked(status_path, reason, timestamp=...)` matches the real keyword-only signature at `_status.py:241`, and `_notify.notify(event, detail, **context)` matches `_notify.py:102`. "holistic cleanup block" and the builder-lock-release invocation are pre-existing, consistently-used terms elsewhere in the file (e.g. lines 860, 979, 1338).
- Card 2 (#809): `SKILL.md:1203` now calls `_status.set_blocked(...)` in place of the buggy `update_field(status_path, "blocked_reason", ...)`; correctly stays minimal (no `_notify`/lock-release added), matching `_mill/discussion.md:163`'s explicit "minimal fix only" decision.
- Card 3 (#792): the new paragraph at `SKILL.md:485` matches the required text and sibling lead-sentence convention, correctly placed after the "Skip this step..." sentence and before "### 0.6.".
- Card 4 (#806): all 6 replacements in `mill-plan/SKILL.md` (lines 94, 118, 347, 366, 402, 432) verified present and correct; the 5 intentionally-untouched `plugins/mill/...` references (lines 166, 171, 195, 196, 317, 319) are still in repo-relative form as required.
- Both batch `verify:` greps re-run and pass: zero `update_field(status_path, "blocked_reason"` matches, exactly 4 `600000ms` matches in mill-go/SKILL.md; zero `plugins/mill/skills/mill-go|mill-receiving-review|plugins/mill/docs` matches in mill-plan/SKILL.md.
- Shared Decisions (doc-only scope, `PYTHONPATH=` prefix on every verify) applied consistently across both batches. No out-of-plan files touched; batches are independent with no cross-batch contract to check.

## Verdict

APPROVE
All four cards match plan text and cited source signatures exactly; both verify gates pass.
MILL_REVIEW_END
