---
name: mill-fold
description: Fold a GitHub issue or scope item into an existing Home.md backlog task. Hard-refuses locked-phase targets ([active], [ready-to-merge], [pr-pending]) so a frozen plan is never invalidated by silent scope creep.
---

# mill-fold

A thin skill wrapping `millpy-fold.py`. Use it when the user wants to attach a GitHub issue or a free-form scope note to an existing backlog task in Home.md. The script acquires the wiki lock, appends one bullet to the target task's body, commits and pushes, then (GH path only) closes the issue with comment `"Folded into wiki task: <slug>"`. Locked-phase targets (`[active]`, `[ready-to-merge]`, `[pr-pending]`) are refused outright — the plan was frozen at spawn time and silent scope additions would invalidate it. `_tasks_md.LOCKED_FOLD_PHASES` is the single source of truth for the locked-phase set.

## When the user invokes me

Typical triggers:

- "Fold #99 into mill-misc-fixes-7."
- "Fold this issue into the cluster-reviewer task."
- "Legg det inn under cluster-reviewer."
- "Add this scope item to fix-foo."

## Preconditions

- `.millhouse/wiki` junction exists in the current clone (if not: run `/mill-setup` first).
- Working directory is a mill-enabled clone (hub or any worktree).
- For the GH path (`--issue`): `gh auth status` must succeed.

## Two invocation forms

### `/mill-fold <target-slug> --issue <N>` — GH issue

1. The script parses Home.md, runs the phase guard, then calls `_gh_issues.fetch_one(N)` to retrieve the issue title.
2. It prints the draft Sources line and (when stdin is a tty) prompts: `1) Use as-is (Recommended) / 2) Edit / 3) Abort`.
3. On confirmation it appends `- Sources: #N — <title>` to the target body.
4. After `_wiki.write_commit_push` succeeds it calls `_gh_issues.close_with_comment(N, 'Folded into wiki task: <slug>', git_root=...)`.
5. If the close fails the wiki commit stands and a warning is printed to stderr — the operator can close the issue manually.

### `/mill-fold <target-slug> --scope "<text>"` — scope item

1. The script parses Home.md and runs the phase guard.
2. It appends `- Folded in: <text>` to the target body.
3. No GitHub side-effects.

## Locked-phase guard

Tasks marked `[active]`, `[ready-to-merge]`, or `[pr-pending]` reject the fold with `SystemExit(1)`:

```
Cannot fold into '<slug>': task is [<phase>]. Plan is frozen — scope additions silently invalidate it.
```

There is no `--force` flag. The rationale: mill-spawn commits a frozen plan at the time a task enters `[active]`; appending scope after that point silently invalidates the plan that the implementer is following. Pick a different action: skip the issue, handle it in a follow-up task, or wait until the current task merges. `_tasks_md.LOCKED_FOLD_PHASES` is the source of truth — never duplicate the tuple in operator instructions or scripts.

## How to call the script

```bash
# WRONG — invokes from source tree
uv run --project plugins/mill plugins/mill/scripts/millpy-fold.py <slug> --issue <N>

# RIGHT — invokes from cache
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fold.py" <slug> --issue <N>
```

```powershell
# GH issue path
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" `
    "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fold.py" mill-misc-fixes-7 --issue 99

# Scope path
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" `
    "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fold.py" cluster-reviewer --scope "Support async batch calls"
```

Source-tree form (for testing in the millhouse repo):

```powershell
uv run --project plugins/mill plugins/mill/scripts/millpy-fold.py mill-misc-fixes-7 --issue 99
```

## Examples

### (a) Fold GH issue #99 into `mill-misc-fixes-7`

```powershell
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" `
    "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fold.py" mill-misc-fixes-7 --issue 99
```

Expected output (interactive):

```
- Sources: #99 — Fix sidebar ordering regression
1) Use as-is (Recommended) / 2) Edit / 3) Abort
> 1
Folded into wiki task: 'mill-misc-fixes-7'
```

Home.md now contains `- Sources: #99 — Fix sidebar ordering regression` in the `mill-misc-fixes-7` body, and issue #99 is closed with comment `Folded into wiki task: mill-misc-fixes-7`.

### (b) Fold scope text into `cluster-reviewer`

```powershell
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" `
    "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fold.py" cluster-reviewer --scope "Support async batch calls"
```

Expected output:

```
Folded into wiki task: 'cluster-reviewer'
```

Home.md now contains `- Folded in: Support async batch calls` in the `cluster-reviewer` body.

### (c) Attempted fold into `[active]` task — error shown verbatim

```powershell
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" `
    "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fold.py" mill-fold --issue 42
```

```
Cannot fold into 'mill-fold': task is [active]. Plan is frozen — scope additions silently invalidate it.
```

Exit code 1. No Home.md change.

## Error handling

| Script exit message | Operator meaning |
|---|---|
| `Slug 'X' not found in Home.md.` | The target slug doesn't exist in Home.md. Check spelling or run `/mill-add` first. |
| `Cannot fold into 'X': task is [Y]. Plan is frozen — scope additions silently invalidate it.` | Target is in a locked phase. Wait until the task merges, or pick a different target. |
| `issue #N is CLOSED; only OPEN issues can be folded` | The GH issue is already closed. No fold needed — it may have been handled elsewhere. |
| `gh issue view failed ...` | `gh` CLI error (network, auth, 404). Run `gh auth status` and retry. |

## Non-goals

- Editing the task title or summary — use manual wiki edit or `mill-groom`.
- Un-folding a previously appended bullet — edit the wiki manually.
- Batch input (multiple issues at once) — use `/mill-ghissues-to-tasks` for multi-issue triage.
