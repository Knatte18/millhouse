All claims in the discussion verify against source. This is round 2; the three r1 review items are recorded as auto-resolved in the Q&A log, and I confirmed each resolution is now reflected in the discussion (unpiped `-clp:ErrorsOnly`, teardown left unchanged, `git_root`/`wiki_path` binding). Current-state claims all match source: `_marker.py:79` `cfg.get("spawn", {})`, `_verify_baseline.py:152-153` bare `worktree add`, mill-start/mill-plan Entry ordering (slug before config, inline path resolution), step 213 GAP-only enumeration, bare `dotnet build`/`dotnet test`, golang-build halt at 44-48, git-commit delegation silent on the halt, and `_worktree.py:237-261` `safe_rmtree` fallback.

MILL_REVIEW_BEGIN
# Review: Fix mill-start instruction gaps, baseline long-path on Windows, and language skill tooling reliability

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-09
```

## Findings

### [NOTE] Backstop file target left as "and/or"
**Section:** Scope (In) / Decision 622-fix
**Issue:** The ad-hoc dotnet backstop is scoped to "cli/SKILL.md and/or root CLAUDE.md", leaving the plan writer to guess one, the other, or both (both files exist).
**Fix:** Name the single canonical target (or explicitly say "both"), so batch C has an unambiguous edit set.

## Verdict

APPROVE
Thorough, source-grounded, and r1 gaps resolved; only a minor placement note remains.
MILL_REVIEW_END