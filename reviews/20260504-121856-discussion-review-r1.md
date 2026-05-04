I have enough information to write the review.

---

# Review: script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: discussion.md
date: 2026-05-04
```

## Findings

### [GAP] Spawn fix breaks terminal/vscode bootstrap for subfolder-install

**Section:** § Decisions — Mirror `hub_subpath` in spawn / worktree dst; § Problem

**Issue:** The spawn Decision places `.millhouse/` at `worktree_path / hub_subpath / ".millhouse"` for subfolder-install. The terminal "reference correct pattern" (line 83 of `millpy-terminal.py`) reads from `selected_path / ".millhouse"` = `worktree_path / ".millhouse"`. After the fix, that path doesn't exist for subfolder-install task worktrees; `_load_config` returns empty, `hub_subpath` defaults to `"."`, and `launch_path = worktree_path` — the git root, not the hub. The discussion claims terminal/vscode "already resolve correctly," which is only true for standard layout; the fix introduces a regression for the exact use case it intends to enable. Testing item 3 ("confirms terminal/vscode launch path remains correct") only checks the portal junction target, not the launch path, so the regression would go undetected.

**Fix:** Either (a) describe how terminal/vscode will be updated to locate `.millhouse/` when it is at a hub subpath in a task worktree (resolving the bootstrap chicken-and-egg), or (b) specify that spawn writes a minimal `config.local.yaml` at `worktree_root / ".millhouse"` for bootstrap and places the full config at `dest_hub / ".millhouse"`, and confirm this fits the layout invariants. Correct or remove testing item 3's claim about terminal/vscode.

---

### [NOTE] `resolve_wiki_path` line 303 — in-scope but fix not described

**Section:** § Technical Context — Affected files; § Q&A log

**Issue:** Q&A says `resolve_wiki_path` line 303 (reads `git_toplevel / ".millhouse" / "config.local.yaml"`) is "silently in scope," but it is absent from the "Fix all 8 cwd-vs-git-root sites" In list, and no fix approach is stated. The function's docstring also asserts "The local config file is read from `git_toplevel` (correct)" — contradicting the Q&A. The approach (change the read to `resolve_hub_path() / ".millhouse" / "config.local.yaml"` inside the helper, preserving `git_toplevel` only for the `resolve_main_worktree_root` call) is derivable but not written down.

**Fix:** Add `resolve_wiki_path` line 303 to the In scope list with a one-line fix description, and note that the docstring's "correct" assertion will be removed.

## Verdict

GAPS_FOUND  
The spawn fix and the terminal/vscode "reference correct pattern" are incompatible for subfolder-install task worktrees; the discussion does not resolve this.