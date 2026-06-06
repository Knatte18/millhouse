---
name: mill-ghissues-to-tasks
description: Drain the GitHub issue queue into Home.md. One-shot: the assistant groups all open issues into a few tasks (new or folded-in) and asks for one combined approval, then closes consumed issues with a pointer comment. Skipped issues are left alone.
---

# mill-ghissues-to-tasks

One-shot triage of the repo's open GitHub issues into `Home.md` task entries.

The assistant fetches all open issues, analyzes the full set, and proposes a natural grouping of related issues into a small number of tasks (plus fold-ins and skips), presented as a single consolidated proposal. The operator gives one combined approval. On approval, the grouped tasks are written to Home.md, committed and pushed via the wiki, and every consumed issue is closed with a comment pointing at its task slug. Skipped issues are untouched.

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

## Step 2 — Read the current task list

Resolve the wiki path and load all tasks via the client API:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import json, _paths
from wiki import _client
wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
print(_paths.resolve_git_root())  # for repo name detection below
tasks = _client.list_tasks_brief(wiki_path)
print(json.dumps(tasks, indent=2))
" > .scratch/wiki-tasks.json
```

Store `wiki_path` for later `_client` calls. Parse `.scratch/wiki-tasks.json` — each task dict has keys `{id, slug, title, layer, brief, status, has_proposal}`.

## Step 3 — Analyse and group

Read all fetched issues from `.scratch/issues.json` plus the current task list from `.scratch/wiki-tasks.json`. Using judgment, propose a grouping of the open issues into a small number of **new** tasks (soft target 2-3, natural grouping by theme, no hard cap — do not force unrelated issues together or over-split tightly-related ones), plus a set of fold-in candidates (overlapping with existing unlocked backlog tasks) and skips (non-actionable issues).

For each grouped **new** task, draft:
- A slug (validate `[a-z][a-z0-9-]*`; must not collide with an existing slug from Step 2).
- A title (free text).
- A brief theme statement (1–2 sentences).

For each fold-in candidate, the locked-phase guard applies: call `task = _client.get_task(wiki_path, target_slug)` and inspect `task["status"]`. When the status is in the locked set `{"active", "ready-to-merge", "pr-pending"}`, refuse the fold for those issues — route them to a new task or skip instead. The locked set `{"active", "ready-to-merge", "pr-pending"}` is the source of truth.

**There is NO per-issue decision menu and NO per-issue prompting.** The assistant makes all grouping decisions at once and presents them in Step 4.

## Step 4 — Propose

Write the consolidated proposal to `.scratch/ghissues-to-tasks-proposal.md`. The proposal must include:

1. A decisions table listing every fetched issue and its routing (New task, Fold-in, or Skip).
2. A "New tasks (grouped)" section listing each drafted slug, title, and brief, with the source issues grouped under each.
3. A "Fold-ins" section listing each target slug and its source issues.
4. A "Skipped" section listing skipped issues and their skip reasons.
5. For each consumed issue (new/grouped or fold-in), the **exact** close-comment string that will be posted on approval:
   - New/grouped-task issues: `Consolidated into wiki task: <slug>`
   - Fold-in issues: `Folded into wiki task: <slug>`
   - Skipped issues: no comment.

Print a one-line summary to chat + the path. The operator replies `approve` or gives feedback.

**One-shot model:** there is no per-issue prompting; all decisions are presented at once. "One-shot" means no resumable state, NOT no iteration. On feedback the assistant revises the grouping and re-presents the full proposal, looping until `approve` or an explicit abort. **Nothing is written to the wiki or closed on GitHub until `approve`.**

## Step 5 — Apply (on approve)

1. For each grouped **new** task, call:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   from wiki import _client
   _client.upsert_task(
       <wiki_path>,
       '<slug>',
       title='<title>',
       brief='<theme>',
       body='''- Sources: #N — <issue title>\n- Sources: #M — <issue title>\n...\nRun 'gh issue view #N' for full detail.'''
   )
   "
   ```
   Per `wiki/_render.py`, a non-empty `body` renders to `proposal-<slug>.md` and the Home.md slug line becomes a link to that file. This minimal manifest is intended — the implementer fetches full issue detail via `gh issue view #N` rather than duplicating the issue text into the wiki. Optionally, call `_client.upsert_tasks_batch(wiki_path, tasks, message=...)` to create all grouped tasks in one commit instead of sequential `upsert_task` calls. The daemon commits and pushes automatically on each mutation.

2. For each fold-in, call:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   from wiki import _client
   task = _client.get_task(<wiki_path>, '<target_slug>')
   if task is None:
       # Stale or typo'd target — report error for this fold-in and continue
       print('ERROR: target task <target_slug> not found')
   else:
       # Re-check locked-phase guard
       if task['status'] in {'active', 'ready-to-merge', 'pr-pending'}:
           print('ERROR: Cannot fold into <target_slug>: task is locked')
       else:
           new_body = (task['body'] or '') + '\n- Sources: #N — <issue title>'
           _client.upsert_task(<wiki_path>, '<target_slug>', body=new_body)
   "
   ```

3. For each consumed issue, close it on GitHub after the wiki write succeeds:
   - For **new/grouped-task** issues:
     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
     import _gh_issues, _paths
     _gh_issues.close_with_comment(<N>, 'Consolidated into wiki task: <slug>', git_root=_paths.resolve_git_root())
     "
     ```
   - For **fold-in** issues:
     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
     import _gh_issues, _paths
     _gh_issues.close_with_comment(<N>, 'Folded into wiki task: <slug>', git_root=_paths.resolve_git_root())
     "
     ```
   The fold-in close-comment string MUST match `/mill-fold` verbatim: `Folded into wiki task: <slug>`.
   On any close failure, log the issue number + error and continue; report all failures at the end.

## Step 6 — Report

Summarize the applied changes:

```
Revision applied.
  <X> new grouped tasks created
  <Y> fold-ins appended
  <Z> issues closed on GitHub
  <S> skipped (untouched)
  <F> failed to close (see stderr)
```

## Rules

- **One-shot, no resumable state** — the proposal file at `.scratch/ghissues-to-tasks-proposal.md` is the only intermediate artefact. If the user closes mid-flow, starting over is fine.
- **Skipped issues are untouched** — no comment, no label, no close. Forgetting is better than lingering "tracked" state.
- **Close only on approval + actual write** — never close an issue before the task is committed to the wiki.
- **Pointer comment is the invariant** — every closed issue gets a reference comment so someone browsing closed issues later can find where it went. New/grouped-task issues close with `Consolidated into wiki task: <slug>`; fold-in issues close with `Folded into wiki task: <slug>`.
- **Locked-phase guard** — fold targets must be in an unlocked phase. The locked set `{"active", "ready-to-merge", "pr-pending"}` is the source of truth; issues destined for locked tasks are routed to a new task or skipped instead.
- **Fold-in format** — each fold-in appends a `- Sources: #N — <issue title>` bullet via `_client.get_task` + `_client.upsert_task(..., body=...)`. The Home.md output is identical to `/mill-fold`.
- **Close-comment strings** — new/grouped-task → `Consolidated into wiki task: <slug>`; fold-in → `Folded into wiki task: <slug>` (byte-identical to `/mill-fold`'s comment).
