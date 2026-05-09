I have enough information. Let me write the review.

# Review: 38 (A) — Drop active.slug.md marker

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-09
```

## Findings

### [GAP] `ActiveWorktreeSlugMismatch` fate unspecified
**Section:** Scope / Technical Context (`_paths.py:295,307`)
**Issue:** The exception is exported in `_paths.__all__`, documented in `_review_common.py`'s raises clause (line 172), and explicitly tested in `test-paths.py` (lines 429, 516) and `test-review-common.py` (lines 292–294). The module map replaces line 307 (`_active.read_slug(worktree/.millhouse)`) with `_marker.slug_from_branch(...)`, but nowhere states whether `ActiveWorktreeSlugMismatch` is retained (wrapping a slug-comparison failure), dropped, or superseded by `MarkerError` propagation.
**Fix:** Add a decision: state explicitly whether `ActiveWorktreeSlugMismatch` survives the rewrite (recommend retaining it — wrap the slug-mismatch branch in `resolve_active_worktree` so callers catching it continue to work unchanged) and whether the existing slug-mismatch test cases in `test-paths.py` are updated or dropped.

### [NOTE] `discover_active_worktrees` Home.md access path is implicit
**Section:** Technical Context (`_spawn_core.py:152-202`)
**Issue:** The module map says callers `millpy-vscode.py` and `millpy-terminal.py` have "unchanged signature; just the rewritten body," which constrains `discover_active_worktrees` to keep `(worktrees_dir: Path)` as its public signature. But the new body needs `Home.md` for the branch→slug lookup. How the function derives `wiki_path` internally from `worktrees_dir` (e.g., `worktrees_dir.parent / "wiki"` vs. git-root resolution from a found entry vs. sibling discovery) is not stated. The "inject parsed tasks into the helper" phrase reads as internal loop structure, not as a new parameter.
**Fix:** Add one sentence clarifying the Home.md access path inside `discover_active_worktrees` — e.g., resolve wiki via `_sibling.resolve_path` from the container (`worktrees_dir.parent`), or enumerate an arbitrary worktree to get a git root and call `resolve_wiki_path`. The strategy matters when the worktrees dir is empty or when `wiki_path` config is non-default.

## Verdict

GAPS_FOUND
One exported exception's fate is unspecified; one implementation path is ambiguous.