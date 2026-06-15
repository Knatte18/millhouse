---
name: mill-fold
description: Fold a GitHub issue or scope item into an existing Home.md backlog task. Accepts only unclaimed tasks (status is None AND not deferred); claimed, terminal, blocked, or deferred tasks reject fold-ins.
---

# mill-fold

A thin skill wrapping `millpy-fold.py`. Use it when the user wants to attach a GitHub issue or a free-form scope note to an existing backlog task in Home.md. The script acquires the wiki lock, appends one bullet to the target task's body, commits and pushes, then (GH path only) closes the issue with comment `"Folded into wiki task: <slug>"`. Fold targets must be unclaimed: `status is None AND not deferred`. Any claimed, terminal, blocked, or deferred task rejects the fold — the allowlist auto-refuses any future status value, which is safe in the event of silent GitHub issue loss on refused folds.

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
4. After the daemon commit/push succeeds (daemon auto-commits on each `_client` mutation) it calls `_gh_issues.close_with_comment(N, 'Folded into wiki task: <slug>', git_root=...)`.
5. If the close fails the wiki commit stands and a warning is printed to stderr — the operator can close the issue manually.

### `/mill-fold <target-slug> --scope "<text>"` — scope item

1. The script parses Home.md and runs the phase guard.
2. It appends `- Folded in: <text>` to the target body.
3. No GitHub side-effects.

## Unclaimed-only guard

Only unclaimed tasks (`status is None` and not `deferred`) accept folds. Any other task state rejects the fold with `SystemExit(1)`:

```
Cannot fold into '<slug>': task is not unclaimed (status: <status-or-'deferred'>). Only unclaimed backlog tasks accept fold-ins.
```

There is no `--force` flag. The rationale: folding closes the source GitHub issue with a pointer comment; folding into a claimed/terminal/blocked/deferred task silently loses the issue. The allowlist predicate — only unclaimed tasks — ensures that adding any new status value in the future will auto-refuse, which is safe in the event of silent issue loss.

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
Cannot fold into 'mill-fold': task is not unclaimed (status: 'active'). Only unclaimed backlog tasks accept fold-ins.
```

Exit code 1. No Home.md change.

## Error handling

| Script exit message | Operator meaning |
|---|---|
| `Slug 'X' not found in Home.md.` | The target slug doesn't exist in Home.md. Check spelling or run `/mill-add` first. |
| `Cannot fold into 'X': task is not unclaimed (status: <Y>). Only unclaimed backlog tasks accept fold-ins.` | Target is not unclaimed. Route the issue to a new task, handle it in a follow-up task, or skip it. |
| `issue #N is CLOSED; only OPEN issues can be folded` | The GH issue is already closed. No fold needed — it may have been handled elsewhere. |
| `gh issue view failed ...` | `gh` CLI error (network, auth, 404). Run `gh auth status` and retry. |

## Non-goals

- Editing the task title or summary — use manual wiki edit or `mill-groom`.
- Un-folding a previously appended bullet — edit the wiki manually.
- Batch input (multiple issues at once) — use `/mill-ghissues-to-tasks` for multi-issue triage.
