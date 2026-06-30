I have everything I need. Let me verify the one factual claim about another `gh pr list` argv in the mill-merge SKILL.md.

The branch-protection fallback at line 138 of mill-merge/SKILL.md constructs `gh pr list --head "$CHILD_BRANCH" --state open --json number,url --jq '.[0]'`, and card 3 explicitly forbids touching it. This bears on the single-source Decision. My review follows.

MILL_REVIEW_BEGIN
# Review: Handle pre-closed and pre-merged PRs gracefully in mill-merge — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-30
```

## Findings

### [NIT] single-pr-query-source Decision overstates uniqueness
**Location:** overview Shared Decisions / Card 3
**Issue:** The Decision asserts "No other code constructs a `gh pr list` argv," but mill-merge/SKILL.md L138's branch-protection fallback keeps its own `gh pr list --head ... --state open --json number,url --jq '.[0]'`, and Card 3 deliberately forbids modifying it (Scope/Out).
**Fix:** Scope the Decision wording to "the PR-state resolution query," acknowledging the fallback's distinct existence-check query is intentionally left in place.

### [NIT] Card 3 Context omits wiki `_client` for get_task
**Location:** 03-mill-merge-skill.md / Card 3
**Issue:** Requirements reference `_client.get_task(wiki_path, slug)` and `task["title"]`, but the wiki `_client` module is not in `Context:` (only `_pr_state.py`, `_paths.py`, mill-finalize/SKILL.md).
**Fix:** Add the wiki `_client` module to `Context:`. Mitigated since the exact call already appears at L48 of the edited mill-merge/SKILL.md, so no true cold-start.

### [NIT] merged route skips Step 5.5 preflight before Step 6
**Location:** 03-mill-merge-skill.md / Card 3 (merged route)
**Issue:** The `merged` route runs Step 4 then jumps to Step 6 (archive-tag, which imports `_archive_tag`), skipping the Step 5.5 cache-preflight; a stale cache crashes with `ModuleNotFoundError` — the exact case 5.5 guards.
**Fix:** Have the `merged` route run Step 5.5 before Step 6 (the old `## PR-path re-entry` also skipped it, so this is a pre-existing gap, not a regression).

## Verdict

APPROVE
Plan is aligned, complete, decisions faithfully implemented, DAG sound; only minor clarifications.
MILL_REVIEW_END