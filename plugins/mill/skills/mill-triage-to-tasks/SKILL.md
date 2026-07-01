---
name: mill-triage-to-tasks
description: Source-agnostic triage-report analysis (group -> compare-vs-wiki -> propose -> approve -> upsert) loaded by entry skills after they write .scratch/triage-contract.json; never references gh.
---

# mill-triage-to-tasks

This skill is **not invoked directly by an operator**. It is loaded via the Skill tool by source-specific entry skills — today `mill-ghissues-to-tasks` and `mill-report-to-tasks` — after each has written `.scratch/triage-contract.json` in the contract envelope shape documented in `plugins/mill/templates/triage-report.schema.md`. Mirroring how `mill-receiving-review` is "loaded by other skills, never run standalone": this skill holds the entire source-agnostic half of triage — read the contract, read current wiki tasks, group into new tasks / fold-ins / skips, present one consolidated proposal, and on approval write the wiki and a results file. It never imports or shells out to `gh` and never branches on `contract["source"]` anywhere in its logic — that boundary is the reason this skill exists as a separate file from its callers.

## Step 1 — Read the contract

Read and parse `.scratch/triage-contract.json` from the current worktree. The calling entry skill is responsible for having written it before invoking this skill. Halt with a clear message if the file is missing or fails to parse as the expected envelope shape:

```
.scratch/triage-contract.json is missing or invalid. The calling entry skill must write a valid triage-report
contract (source, meta, items, ref_prefix, detail_hint, embed_body) before invoking mill-triage-to-tasks.
```

The expected shape — same field names as `plugins/mill/templates/triage-report.schema.md` — is:

```json
{
  "source": "ghissues" | "sandbox-report",
  "meta": {"...": "adapter-owned passthrough, never read by this skill"},
  "items": [{"ref": "...", "title": "...", "body": "..."}],
  "ref_prefix": "...",
  "detail_hint": "..." | null,
  "embed_body": true | false
}
```

## Step 2 — Read the current task list

Resolve the wiki path and load all tasks via the client API:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import json, _paths
from wiki import _client
wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
tasks = _client.list_tasks_brief(wiki_path)
print(json.dumps(tasks, indent=2))
" > .scratch/wiki-tasks.json
```

Store `wiki_path` for later `_client` calls. Parse `.scratch/wiki-tasks.json` — each task dict has keys `{id, slug, title, layer, brief, status, has_proposal}`.

## Step 3 — Analyse and group

Read the contract's `items` (from Step 1) plus the current task list (from Step 2). Using judgment, group `items` into a small number of **new** tasks (soft target 2–3, natural grouping by theme, no hard cap — do not force unrelated items together or over-split tightly-related ones), plus a set of fold-in candidates (overlapping with existing unclaimed backlog tasks), plus skips (non-actionable items).

For each grouped **new** task, draft:
- A slug (validate `[a-z][a-z0-9-]*`; must not collide with an existing slug from Step 2).
- A title (free text).
- A brief theme statement (1–2 sentences).

For each fold-in candidate, apply the **unchanged** unclaimed-only guard from `millpy-fold.py`'s `unclaimed-only-allowlist` decision: from the already-loaded task list (Step 2), find the task with matching slug and inspect its `status` and `deferred` flag. A fold target must be unclaimed: `status is None and not deferred`. Any other state (claimed, terminal, blocked, or deferred) routes the item to a new task or a skip instead.

**There is NO per-item decision menu and NO per-item prompting.** All grouping decisions are made at once and presented together in Step 4.

## Step 3.5 — All-items-skipped short-circuit

If, after grouping, there are zero new tasks AND zero fold-ins (every item routed to skip), do NOT write `.scratch/triage-proposal.md` and do NOT write anything to the wiki. Print a one-line status message to chat:

```
nothing to do -- N item(s), all skipped
```

Then stop — return control to the calling entry skill without writing `.scratch/triage-result.json` either. The entry skill must treat "no results file written" as "nothing was consumed."

## Step 4 — Propose

Write the consolidated proposal to `.scratch/triage-proposal.md` (note: NOT `.scratch/ghissues-to-tasks-proposal.md` — that filename is retired by this skill). The proposal must include:

1. A decisions table listing every item — displayed as `contract["ref_prefix"] + ref` — and its routing (New task / Fold-in / Skip).
2. A "New tasks (grouped)" section listing each drafted slug, title, and brief, with the source items grouped under each.
3. A "Fold-ins" section listing each target slug and its source items.
4. A "Skipped" section listing skipped items and their skip reasons.

Unlike `mill-ghissues-to-tasks`'s proposal, do NOT include any close-comment string here — this skill never writes GitHub-specific text; closing (if applicable) is entirely the calling entry skill's job, driven by `.scratch/triage-result.json` (Step 6).

Print a one-line summary to chat plus the file path. The operator replies `approve` or gives feedback.

**One-shot model:** there is no per-item prompting; all decisions are presented at once. "One-shot" means no resumable state, NOT no iteration. On feedback, revise the grouping and re-present the full proposal, looping until `approve` or an explicit abort. **Nothing is written to the wiki until `approve`.**

## Step 5 — Apply (on approve)

For each item, the body block written under its `- Sources: ...` bullet is built the same way regardless of whether the bullet lands on a new task or a fold-in target:

```
- Sources: {contract["ref_prefix"]}{item["ref"]} — {item["title"]}
```

Immediately after that bullet:
- When `contract["detail_hint"]` is non-null, write the hint line with `{ref}` substituted from that same item's own `ref` — never from any other item's `ref`, even when multiple items share a task.
- When `contract["embed_body"]` is true, write that item's `body` text immediately after the bullet (and after the hint line, when one was written).

1. **New tasks.** For each grouped new task, concatenate every source item's block (in grouping order) to form the full task body, then call:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   from wiki import _client
   _client.upsert_task(
       <wiki_path>,
       '<slug>',
       title='<title>',
       brief='<theme>',
       body='''<concatenated per-item blocks>'''
   )
   "
   ```
   Optionally, call `_client.upsert_tasks_batch(wiki_path, tasks, message=...)` to create all grouped tasks in one commit instead of sequential `upsert_task` calls. The daemon commits and pushes automatically on each mutation.

2. **Fold-ins.** For each fold-in candidate:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   from wiki import _client
   task = _client.get_task(<wiki_path>, '<target_slug>')
   if task is None:
       # Stale or typo'd target -- record an error for this item and continue
       print('ERROR: target task <target_slug> not found')
   else:
       # Re-check unclaimed-only guard -- status could have changed since Step 3
       if task.get('status') is not None or task.get('deferred', False):
           print('ERROR: Cannot fold into <target_slug>: task is not unclaimed')
       else:
           new_body = (task['body'] or '') + '<this item per-item block>'
           _client.upsert_task(<wiki_path>, '<target_slug>', body=new_body)
   "
   ```
   Note: this appends to the task's `body` field, not its `brief` field. `/mill-fold` appends its equivalent bullet to `brief`; this skill matches today's `mill-ghissues-to-tasks` body-placement behavior instead, only reusing `/mill-fold`'s bullet-string format (`- Sources: <ref> — <title>`).

## Step 6 — Write results

After all wiki writes succeed, write `.scratch/triage-result.json` as a JSON array, one entry per consumed item (new-task and fold-in items only — skipped items are NOT listed):

```json
[
  {"ref": "<item ref>", "route": "new_task", "slug": "<slug>"},
  {"ref": "<item ref>", "route": "fold_in", "slug": "<target_slug>"}
]
```

This is the only file the calling entry skill reads back to learn what happened.

## Step 7 — Report

Print a one-line summary:

```
Triage applied.
  <X> new grouped tasks created
  <Y> fold-ins appended
  <S> skipped (untouched)
  <F> fold-in errors (target not found / guard re-check failed)
```

## Rules

- **One-shot, no resumable state** — `.scratch/triage-proposal.md` is the only intermediate artefact. Feedback loops by revising and re-presenting the full proposal; there is no per-item resumable state.
- **Skipped items are untouched** — no wiki write, nothing to undo.
- **Writes only happen after explicit `approve`** — nothing touches the wiki before that.
- **Unclaimed-only guard is non-negotiable** — fold targets must be unclaimed (`status is None and not deferred`). Any claimed, terminal, blocked, or deferred task is routed to a new task or skipped instead, both at Step 3 and on the Step 5 re-check.
- **Never references `gh`, never branches on `contract["source"]`** — this is the one invariant the whole task exists to enforce. All source-specific behavior (fetching, closing, etc.) lives entirely in the calling entry skill.
