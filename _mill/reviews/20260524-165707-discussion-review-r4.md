# Review: Adopt V3 wiki module in V2 scripts

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-24
```

## Findings

### [GAP] `list_tasks_brief()` omits `title`; picker callers break

**Section:** § Scope — `wiki/_store.py` and `_spawn_core.py` migration

**Issue:** The discussion explicitly defines `list_tasks_brief()` as returning `{id, slug, group, brief, status}` (no `title`, no `has_proposal`). Source verification confirms all four picker functions in `_spawn_core.py` need these missing fields: `_prompt_numbered:236` (`t.title`, `t.has_proposal`), `_prompt_numbered_multi:344-345` (same), `prompt_merged_entry:558` (`t.title`), `discover_active_worktrees:216` (`task.title`). Downstream callers `millpy-claim.py:221` (`picked.title`), `millpy-vscode.py:203`, and `millpy-terminal.py:81` destructure the tuple returned by `discover_active_worktrees` and use `title`. Switching all `_spawn_core` consumers to `list_tasks_brief()` would produce `KeyError` at runtime on every task-pick and worktree-discovery call.

**Fix:** Decide and record: either add `title` to the brief shape (contradicts the spec sentence "no `title`") or declare that picker functions use `list_tasks_full()` with `has_proposal` derived from `bool(task["body"])`. Whichever choice is made, enumerate the specific `_spawn_core` functions that must use `full` vs `brief`.

### [NOTE] "Task dataclass moves to wiki/__init__.py" contradicts dict migration

**Section:** § Scope — delete-v2-wiki-layer bullet; § Decision `delete-v2-wiki-layer`

**Issue:** The scope says "The `Task` dataclass and `LOCKED_FOLD_PHASES` constant move into `wiki/__init__.py`", but the rest of the scope replaces every `_tasks_md.Task` type hint with `dict` or `list[dict]`. A plan writer reading both could conclude `Task` is simultaneously deleted and moved.

**Fix:** Clarify the sentence to read "The `LOCKED_FOLD_PHASES` constant moves into `wiki/__init__.py`; the `Task` dataclass is deleted outright (all callers shift to dicts)."

## Verdict

GAPS_FOUND
One GAP: `list_tasks_brief()` brief-shape versus picker callers' need for `title` and `has_proposal` is unresolved and will break the implementation.