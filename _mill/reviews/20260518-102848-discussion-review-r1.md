Now I have enough information to write the review.

# Review: 58 (D) — Activate psmux-based claude subprocess routing

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-18
```

## Findings

### [GAP] Config load chain uses wrong first argument
**Section:** `### config-loading-in-invoke`
**Issue:** The decision describes `_config.load_config(wiki_path, worktree_root)` after calling `_paths.resolve_wiki_path(...)`, but `_config.load_config`'s actual first argument is `repo_root` (verified: `_config.py:148`). Every production caller passes `git_root` / `hub_dir` — never a wiki path (`_review_common.py:304`, `millpy-bg.py:142`, `millpy-inspect.py:47`). The `resolve_wiki_path` step in the described chain is both incorrect (wrong arg type) and unnecessary (`load_config` resolves the wiki internally). The module-level docstring in `_config.py:6` also says `wiki_path` — a stale artifact that the discussion re-copied verbatim.
**Fix:** Replace the chain with `worktree_root = _paths.resolve_git_root(Path.cwd())` → `_config.load_config(worktree_root, worktree_root)`. Remove the `_paths.resolve_wiki_path(...)` step entirely.

### [NOTE] `session_id=None` return violates `tuple[str, str]` annotation
**Section:** `### response-extraction-psmux`
**Issue:** Discussion says "Session_id = the value we passed (or `None` if none passed)". With `session_id=None` (the default for all three public callers), the psmux branch would return `(text, None)`, violating `_invoke`'s `-> tuple[str, str]` annotation. The wrapper always assigns a UUID internally (`millpy-claude-sub.py:66-69`); that value is available in `result.stderr` JSON and could be used instead.
**Fix:** Decide whether the psmux path enforces non-null session_id (consistent with the direct path's existing check) or accepts `None` (requiring an annotation change). Either is fine; the ambiguity will land on the implementer.

## Verdict

GAPS_FOUND
Config load call chain is factually wrong; plan writer would implement an incorrect helper.