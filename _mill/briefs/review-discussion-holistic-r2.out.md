MILL_REVIEW_BEGIN
# Review: mill-merge / mill-merge-in: brief-staging path bug and easy-to-miss caching instruction

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (per system-provided model info)
reviewed_file: /home/knatte/Code/millhouse/wts/mill-merge-family-doc-gaps/_mill/discussion.md
date: 2026-09-19
```

## Findings

### [NIT:consistency] Decision wording vs Technical Context on insertion point
**Section:** Decisions/recovery-path-987 vs Technical context (last bullet) **Issue:** Decision says the note is placed "right before the `git -C <parent-path> commit -m "<cached_task>"` line" (a line mid-way inside the Step 5 bash fence), while Technical context says "immediately before that bash block" — a plan writer following the Decision text literally could try to insert prose inside the code fence, which is not possible. **Fix:** align the Decision wording to say "immediately before the Direct-squash bash block that contains the commit line," matching Technical context.

## Verdict

APPROVE
Claims verified against source (SKILL.md files, test-brief-commit.py, _plan_validate.py, _status.read_full); one non-blocking wording nit.
MILL_REVIEW_END
