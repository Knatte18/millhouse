---
name: mill-ghissues-to-tasks
description: Drain the GitHub issue queue into Home.md. One-shot. Proposes a task per issue (new or folded-in), closes consumed issues with a pointer comment, leaves skipped ones alone.
---

# mill-ghissues-to-tasks

One-shot triage of the repo's open GitHub issues into `Home.md` task entries.

For every open issue, work interactively with the user to decide whether it becomes a new task, folds into an existing task, or is skipped. On user approval, write the resulting `Home.md`, commit+push via the wiki, and **close every consumed issue** with a comment pointing at the task slug. Skipped issues are untouched.

Leaving claimed-but-open issues on GitHub is a forgetting hazard — that's why the closed-with-comment model is preferred over a "tracked" label.

## Entry checks

1. `gh auth status` must succeed. If not, stop:
   > `gh` is not authenticated. Run `gh auth login` and re-invoke `/mill-ghissues-to-tasks`.
2. `.millhouse/wiki/` junction must exist. If not, stop and tell the user to run `mill-setup`.

## Step 1 — Fetch all open issues

Use the `_gh_issues` library. From the hub root:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import json, _gh_issues, _paths
issues = _gh_issues.fetch(limit=100, git_root=_paths.resolve_git_root())
print(json.dumps(issues, indent=2))
" > .scratch/issues.json
```

Read `.scratch/issues.json`. Record the repo name (`_gh_issues.detect_repo(git_root=_paths.resolve_git_root())`) for the close step.

## Step 2 — Read the current Home.md

Resolve the wiki path:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import _paths; print(_paths.resolve_wiki_path(_paths.resolve_git_root()))
"
```

Store as `<WIKI_PATH>`. Read `<WIKI_PATH>/Home.md` and parse task entries — headings matching `## <Title> [<slug>]` or `## <Title> [[<slug>]](proposal-<slug>)`.

You don't need a parser helper; a targeted regex is fine — this skill is interactive and the user is in the loop.

## Step 3 — Interactive decisions (per issue)

For each fetched issue, show the issue number, title, and a brief summary of its body. Then present the decision menu:

```
1) New task — you draft a slug + summary
2) Fold into existing task
3) Skip
```

If the issue does not overlap with any current Home.md task, present: `1) New task (Recommended) / 2) Fold into existing task / 3) Skip`. If it overlaps, present: `1) Fold into <slug> (Recommended) / 2) New task / 3) Skip`. The recommended option is always at position 1; overlap is detected by assistant judgement, not a hard heuristic.

**On selection 1 (New task):**
- Prompt for slug (validate `[a-z][a-z0-9-]*`; re-prompt on invalid).
- Prompt for title (free text).
- Prompt for summary (1–2 sentences).
- Ask: `Extract to proposal? (y/N)`.
- Record the decision.

**On selection 2 (Fold into existing):**
- Prompt for target slug (free text).
- Validate against the parsed Home.md slug list; re-prompt if not found.
- Phase check: parse Home.md via `_tasks_md.parse()` and inspect the target Task's phase. When the phase is in `_tasks_md.LOCKED_FOLD_PHASES` (i.e. one of `"active"`, `"ready-to-merge"`, `"pr-pending"`), refuse the fold for this issue: print `"Cannot fold #<N> into <slug>: task is [<phase>]. Plan is frozen — scope additions silently invalidate it. Pick a different action for this issue."` and re-present the decision menu with option 2 omitted (struck-through or disabled). Use `_tasks_md.LOCKED_FOLD_PHASES` as the source of truth — never duplicate the tuple in this SKILL.md or anywhere else.
- Record the decision.

**On selection 3 (Skip):**
- Prompt for a short reason (for the final report).
- Record the decision. No comment is posted to GitHub.

Process issues one at a time. Do NOT auto-decide; the user chooses for every issue.

## Step 4 — Propose

Write the consolidated proposal to `.scratch/ghissues-to-tasks-proposal.md`:

```markdown
# mill-ghissues-to-tasks proposal

Issues fetched: <N>
Repo: <owner/repo>

## Decisions

| Issue | Title | Decision | Target task |
|---|---|---|---|
| #12 | Bug X | New task | `bug-x` |
| #15 | Feature Y | Fold into | `feature-y-existing` |
| #18 | Cleanup Z | Skip | (reason) |

## New tasks (drafted)

### bug-x — "Fix Bug X"
- Summary: <one or two sentences>
- Proposal doc: yes / no
- Sources: #12

## Fold-ins

### feature-y-existing
- Additional sources: #15

## GitHub close commitments

For each New and Fold-in entry above, the corresponding issue will be closed on approval with:
- `Consolidated into wiki task: <slug>`
```

Print a one-line summary to chat + the path. User replies `approve` or `reject`.

## Step 5 — Apply (on approve)

1. Build the updated `Home.md` content:
   - Append new task entries using the mill-add format (`## <Title> [<slug>]` or bracketed-proposal form).
   - For each fold-in, call `_tasks_md.append_to_body(home_text, target_slug, f"- Sources: #{N} — {issue_title}")` to add a Sources: bullet to the target body. The append is unconditional — there is no longer a "leave unchanged" path. Each fold-in produces the same Home.md output as a `/mill-fold #N <slug>` invocation.
2. Write Home.md + any new `proposal-<slug>.md` files to the wiki and push via `_wiki.write_commit_push`.
3. Regenerate the sidebar (`_sidebar.regenerate`) and commit if it changed.
4. For each consumed issue, close it on GitHub with the per-decision comment string:
   - For each consumed **New-task** issue, call:
     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
     import _gh_issues, _paths
     _gh_issues.close_with_comment(<N>, 'Consolidated into wiki task: <slug>', git_root=_paths.resolve_git_root())
     "
     ```
   - For each consumed **Fold-in** issue, call:
     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
     import _gh_issues, _paths
     _gh_issues.close_with_comment(<N>, 'Folded into wiki task: <slug>', git_root=_paths.resolve_git_root())
     "
     ```
     The Fold-in close-comment string MUST match `/mill-fold`'s exactly — see `plugins/mill/skills/mill-fold/SKILL.md`.
   On any failure, log the issue number + error and continue; report at the end.

## Step 6 — Report

```
Revision applied.
  <X> new tasks
  <Y> fold-ins
  <Z> issues closed on GitHub
  <S> skipped (untouched)
  <F> failed to close (see stderr)
```

## Rules

- **One-shot** — there is no resumable intermediate state. If the user closes mid-flow, the proposal file at `.scratch/ghissues-to-tasks-proposal.md` is the only artefact; starting over is fine.
- **Skipped issues are untouched** — no comment, no label, no close. Forgetting is better than lingering "tracked" state.
- **Close only on approval + actual write** — never close an issue before the task is committed to Home.md.
- **Pointer comment is the invariant** — every closed issue gets `Consolidated into wiki task: <slug>` so someone browsing closed issues later can find where it went.
- Fold targets must be in an unlocked phase. `_tasks_md.LOCKED_FOLD_PHASES` is the source of truth — never duplicate the tuple.
- Fold-in always appends a `"- Sources: #N — <issue title>"` bullet to the target body via `_tasks_md.append_to_body`. The Home.md output of a fold-in is identical between this skill and `/mill-fold`.
- Close-comment strings: New-task → `"Consolidated into wiki task: <slug>"`; Fold-in → `"Folded into wiki task: <slug>"`. The Fold-in string matches `/mill-fold`'s comment verbatim.
