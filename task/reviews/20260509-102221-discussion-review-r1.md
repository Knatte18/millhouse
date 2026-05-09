I have enough information to write the review. The facts I need:

- `resolve_active_worktree` at _paths.py:255 — confirmed, signature is `(container_path: Path, slug: str) -> Path`, hardcoded `wts/slug`.
- `_review_common.resolve_path` at line 182 — confirmed, currently calls the old helper.
- `millpy-abandon.py:53` — confirmed, reads `wiki_path / "active" / slug / "status.md"`.
- `millpy-cleanup.py:103-114` — confirmed, has the inline `hub_relative_path` duplication.
- `_inplace.is_inplace` — confirmed signature matches.
- `test-millpy-abandon.py` does NOT exist. The real file is `test-abandon.py`.

---

# Review: 35 (A) — Centralize path resolution across all three modes

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-09
```

## Findings

### [GAP] Wrong filename for existing abandon test

**Section:** `## Testing` — abandon test paragraph
**Issue:** The discussion says "check `plugins/mill/unit_tests/test-millpy-abandon.py` (likely exists)" — that file does not exist. The actual file is `test-abandon.py`.
**Fix:** Replace the filename reference with `test-abandon.py` and drop the "(likely exists)" hedge.

### [NOTE] `resolve_active_worktree` pseudocode leaves hub location implicit

**Section:** `### helper-bodies`
**Issue:** The pseudocode reads `_active.read_all(<hub-of-git_root>/.millhouse)` but does not state how `<hub-of-git_root>` is resolved when `hub_relative_path` is set (it requires `cfg["hub_relative_path"]`).
**Fix:** Replace the placeholder with `_active.read_all(resolve_hub_relative_path(git_root, cfg.get("hub_relative_path", ".")) / ".millhouse")` to make the dependency on `cfg` explicit.

## Verdict

GAPS_FOUND
One wrong filename would send the plan writer to a non-existent file; fix before planning.