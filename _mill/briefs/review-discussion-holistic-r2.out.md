MILL_REVIEW_BEGIN
# Review: mill-go: quality-gate coverage gaps (NIT-fix regressions, missing lint gate)

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:design] Incident root cause misdiagnosed — per-commit lint already exists and is broken for Go
**Section:** Problem (#800) / Technical context / Scope "Out". **Issue:** `git-commit/SKILL.md` step 1 already runs "language-appropriate lint on staged files" per commit (also invoked by `implementer-brief.md:73-75` and both fixer briefs) — this should have caught the incident's ineffassign finding in a newly-created Go file. But `workflow/SKILL.md`'s Language Detection table (lines 67-77) only lists Python (`pyproject.toml`/etc.) and C# (`.csproj`/`.sln`) marker rows — **no Go/`go.mod` row exists** — so git-commit's "skip if no language detected" branch silently no-ops lint on every Go commit. This is the likely actual root cause, and the discussion's Scope never mentions or decides to fix it; `done_gate`-only closes the symptom (PR-time) but leaves per-commit lint permanently dark for Go. **Fix:** Either add fixing the Language Detection table (add a Go row) to Scope with its own Decision/rationale, or explicitly state in Technical context why the existing per-commit lint gate is intentionally left broken and `done_gate` alone is deemed sufficient.

### [BLOCKING:design] Cross-batch digest scan not justified by the stated rationale
**Section:** Decision `prior-blocking-digest-is-cumulative-and-cross-scope` / Technical context. **Issue:** The spec globs `*-code-review-{batch_name}-r{N}.md` for "any batch name" / "per batch name in this task's plan" — i.e. batch B's fixer digest includes batch A's BLOCKING history too, not just batch-vs-holistic. The Rationale only argues for crossing the batch/holistic *scope* boundary ("batch digest sees only batch history, holistic digest sees only holistic history") and never justifies pulling in *other batches'* findings. Testing's fixture list also only covers "cross-scope aggregation," not cross-batch. **Fix:** Either add an explicit rationale for cross-batch inclusion (and a corresponding test fixture), or narrow the glob to the current batch's own files + all holistic files, matching what the rationale actually supports.

## Verdict

REQUEST_CHANGES
Two design gaps: unaddressed per-commit-lint root cause for Go, and unjustified cross-batch digest scope.
MILL_REVIEW_END
