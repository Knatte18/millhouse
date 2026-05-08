# Review: 32 (A) — Bug-fix batch 2

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-08
```

## Findings

### [GAP] Missed `task/plan/` prefix at holistic line 103
**Section:** `## Decisions / holistic-implement-paths` and `## Technical context #200`
**Issue:** `millpy-implement-holistic.py:103` builds `batch_files_text` as `str(project_root / "plan" / b["file"])` — the same class of missing `task/` prefix bug. The discussion lists fixes for lines 77, 91, and 123 only. After those three edits the `BATCH_FILES` token passed to the LLM prompt template will still resolve to non-existent paths, leaving the script partially broken post-fix.
**Fix:** Add `millpy-implement-holistic.py:103` to the fix list: `project_root / "plan" / b["file"]` → `project_root / "task" / "plan" / b["file"]`.

### [NOTE] Third `detect_repo()` call site not addressed in mill-ghissues-to-tasks
**Section:** `## Scope (In)` — `mill-ghissues-to-tasks/SKILL.md`
**Issue:** `mill-ghissues-to-tasks/SKILL.md:32` calls `_gh_issues.detect_repo()` (no `git_root=`) with the instruction "Record the repo name for the close step." The Decision's MUST requirement covers all in-tree call sites; the discussion only names lines 27 and 127. Post-fix this call remains cwd-sensitive and its stored result is unused (line 127 doesn't accept a `repo=` arg under the new scheme), leaving misleading dead code.
**Fix:** Note that line 32 should be removed or updated alongside the fetch/close updates.

## Verdict

GAPS_FOUND
Line 103 of millpy-implement-holistic.py is an unaddressed `task/` path bug that would survive the planned fix.