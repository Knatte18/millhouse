All source file references verified. Formulating the review.

# Review: (A) — Small infra fixes batch 7

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-12
```

## Findings

### [NOTE] points_to broken-junction edge case not specified
**Section:** D2 / Technical Context — `_junction.py`
**Issue:** The discussion states `points_to` compares `link_path.resolve()` with `target.resolve()`, and assumes "both must already exist for resolve() to canonicalise." On Windows, a stale junction (target directory was deleted after the junction was created) causes `Path.resolve()` to raise `OSError` rather than returning a path — so the "is a junction, but broken" case crashes instead of returning `False`.
**Fix:** Specify that `points_to` catches `OSError` from `resolve()` on either argument and returns `False`; a junction that can't be canonicalised does not resolve to the target.

### [NOTE] Technical Context snippet is incomplete re: lock release
**Section:** D1 / Technical Context — mill-go SKILL.md change
**Issue:** D1 requires the builder lock be released before the wiki-health-check halt, but the inline Python snippet shown in Technical Context only calls `health_check` — it contains no lock-release step. Taken with "No new shell-side error handling needed", a plan writer may omit the lock release from the SKILL.md diff.
**Fix:** Note that the SKILL.md sub-step follows the pattern of the existing "Blocked" section (lines 192–199): health check failure → `millpy-builder-lock.py release` → surface error + halt. The "no new shell-side handling" comment refers to Bash `|| { }` constructs, not the explicit orchestrator steps.

## Verdict

APPROVE  
All decisions are resolved with rationale and rejections; scope, testing, and constraints are fully specified.