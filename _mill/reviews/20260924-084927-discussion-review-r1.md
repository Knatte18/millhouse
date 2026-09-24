# Review: Prefix session names with repo short name; add mh:orch session

```yaml
verdict: REQUEST_CHANGES
reviewer_model: orchestrator
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

## Findings

### [BLOCKING:design] Derived short-name fallback is wrong on a task worktree
**Section:** Decisions / Where the prefix is built; Fallback warning
**Issue:** `millpy-session-tasks.py` would pass `f"{short}:{slug}"` on a task worktree, but the only existing short-name call there is `resolve_short_name(cfg, git_root.name)`.
On a worktree `git_root.name` is the slug directory (`wts/<slug>`), not the repo name, so with `repo.short_name` unset the fallback derives `SE` from `session-name-short-prefix`.
The new warning would also name that wrong derived value.
`millpy-spawn.py` is only correct because it normally runs from the hub.
**Suggested fix:** State that the short name is derived from the main worktree's directory name (`_paths.resolve_main_worktree_root(git_root).name`) in `millpy-session-tasks.py` on a worktree, in `short_name_is_derived`'s warning, and in `millpy-spawn.py`, and add a test with a slug-named worktree and no `repo.short_name`.

### [NIT:scope] `millpy-terminal.py` names sessions a third way and is not mentioned
**Demoted-from:** BLOCKING
**Section:** Scope (In and Out)
**Issue:** `scripts/millpy-terminal.py` lines 119 and 123 start `claude --name <selected_slug>`, a bare slug with no repo prefix and no phase.
It collides across repos exactly as the Problem describes, yet it is in neither In nor Out, so a plan writer could go either way.
`millpy-vscode.py` does not launch `claude`.
**Suggested fix:** Decide explicitly: either name that session `<short>:<slug>` (lower-cased, via the same helper) or list `millpy-terminal.py` under Out with the reason.

### [NIT:consistency] Title and heading still say `MH:orch`
**Section:** Title (line 1 and yaml `task:`)
**Issue:** The decisions lower-case every session name, but the task title in the heading and yaml still reads `MH:orch`.
`status.md` carries the same string.
**Suggested fix:** Use `mh:orch` in the discussion heading; leave `status.md`, which the worker owns.

### [NIT:consistency] Leading comma of `<HUB_TASKS>` should live in the fragment
**Section:** Decisions / Orch task rendering through the template
**Issue:** The text says `<HUB_TASKS>` renders as `,` plus the orch fragment, but the rationale is that format-specific JSON belongs in templates, not Python.
A comma added in Python contradicts that.
**Suggested fix:** Put the leading `,` inside `vscode-tasks-orch.json` and render `<HUB_TASKS>` as the fragment or an empty string.

### [NIT:design] Only the mill-setup prompt validates the short name
**Section:** Decisions / Explicit short_name in mill-setup
**Issue:** `^[A-Za-z0-9]{2,4}$` applies to the prompt only.
A hand-edited `repo.short_name` containing `:` passes `_validate_name` (which forbids `"`, backslash, `$`, backtick and control characters) and would make `<short>:<slug>:<phase>` ambiguous.
**Suggested fix:** Either also reject `:` in `_validate_name`'s prefix check or note that hand-edited values are the operator's responsibility.

## Verdict

REQUEST_CHANGES
The design is sound, but the worktree short-name derivation is wrong and `millpy-terminal.py` needs a stated disposition.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 1._
