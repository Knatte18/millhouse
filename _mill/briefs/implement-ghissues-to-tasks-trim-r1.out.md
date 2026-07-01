No dirty tracked files. `verify: null` for this batch, so nothing to run.

{"status":"success","commit_sha":"993c3160","session_id":"46ad754c-04c9-4d66-b103-5b7d0b3f8340"}

Summary of work: Rewrote `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md` (in `C:\Code\millhouse\wts\mill-ghissues-source-adapter`) into a thin adapter wrapper per Card 6 of `_mill/plan/04-ghissues-to-tasks-trim.md`:

- Kept frontmatter, intro paragraphs, and Entry checks verbatim.
- Step 1 fetches issues via `_gh_issues.fetch()`, detects the repo via `_gh_issues.detect_repo()`, then builds the contract via `_gh_issues.to_contract()` and writes it to `.scratch/triage-contract.json`.
- Step 2 hands off to `mill-triage-to-tasks` via the Skill tool.
- Step 3 reads back `.scratch/triage-result.json` (if present), maps `route` → the exact close-comment strings, and calls `_gh_issues.close_with_comment()` per entry, tolerating individual failures.
- Step 4 reports only issues-closed/failed-to-close counts (grouping counts stay owned by `mill-triage-to-tasks`'s own report).
- `## Rules` trimmed to just this skill's own responsibilities (close-only-on-approval, exact close-comment strings).

Committed as `993c3160` via the `git-commit` skill and pushed to `hanf/mill-ghissues-source-adapter`. `verify: null` for this batch (pure skill/markdown edit), so no test run was required.

{"status":"success","commit_sha":"993c3160","session_id":"46ad754c-04c9-4d66-b103-5b7d0b3f8340"}