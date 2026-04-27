---
name: mill-groom
description: Interactive Home.md backlog cleanup. Shorten, fold, drop, or extract entries. Approval-gated — one commit per session.
---

# mill-groom

One-shot interactive cleanup of the `Home.md` backlog. Over time the backlog
accrues duplicate tasks, long-winded entries, done-but-not-cleaned residue, and
vague wishes that never got a slug. `mill-groom` lets you work through the list
with Claude and emit a cleaner Home.md in a single commit.

Claude proposes; you decide; nothing is written until you type `approve`.

## Entry checks

1. Verify `.millhouse/wiki/` junction exists. If not, stop:
   > `.millhouse/wiki/` junction missing. Run `/mill-setup` first.
2. Resolve the wiki path:
   ```bash
   PYTHONPATH=$CLAUDE_PLUGIN_ROOT/scripts python -c "
   import _paths; print(_paths.resolve_wiki_path(_paths.resolve_git_root()))
   "
   ```
   Store as `<WIKI_PATH>`.
3. `_wiki.sync_pull(<WIKI_PATH>)`:
   ```bash
   PYTHONPATH=$CLAUDE_PLUGIN_ROOT/scripts python -c "
   import _paths, _wiki
   wiki = _paths.resolve_wiki_path(_paths.resolve_git_root())
   _wiki.sync_pull(wiki)
   "
   ```

## Step 1 — Read config

Load `wiki/config.yaml` from `<WIKI_PATH>`. Extract:

- `groom.brevity-threshold-lines` — default **5**
- `groom.brevity-threshold-chars` — default **500**

Use these thresholds in Step 3.

## Step 2 — Parse Home.md

Read `<WIKI_PATH>/Home.md`. Parse with `_tasks_md.parse()`:

```bash
PYTHONPATH=$CLAUDE_PLUGIN_ROOT/scripts python -c "
import _paths, _tasks_md
wiki = _paths.resolve_wiki_path(_paths.resolve_git_root())
text = (wiki / 'Home.md').read_text(encoding='utf-8')
tasks = _tasks_md.parse(text)
import json
print(json.dumps([{'slug': t.slug, 'title': t.title, 'phase': t.phase} for t in tasks], indent=2))
"
```

**Scope rules:**

| `task.phase` | Listed? | Actions available |
|---|---|---|
| `None` (plain backlog) | Yes | keep / shorten / fold / drop / extract |
| `"s"` (spawn-ready) | Yes | keep / shorten / fold / drop / extract |
| `"active"` | Yes (listed, read-only) | none |
| `"done"` | Yes | drop only |
| (protected) | Yes (listed, read-only) | none |

To read the body of a task, read the lines in `Home.md` between its heading
and the next `##` heading (or end of file). A task is protected if its body
contains `<!-- protected -->`.

## Step 3 — List all tasks

Render every `Home.md` entry as a numbered list in file order. Show number, slug, and title. Append the appropriate suffix:

- `(active — read-only)` for `[active]` entries
- `(done — drop only)` for `[done]` entries
- `(proposal)` for entries with a proposal link
- `(protected — skipped)` if the body contains `<!-- protected -->`
- No suffix for plain backlog or `[s]` entries

Example output:

```
1. my-task — My Task Title (done — drop only)
2. big-feature — Big Feature Request
3. old-bug — Old Bug Report (active — read-only)
4. explore-x — Explore Topic X (proposal)
```

Print after the list:

```
Pick a task number to act on, or "done" to commit the proposal:
```

## Step 4 — Per-task action menu

When the user enters a number, look up the task at that position.

**Branch on phase / protection:**

- **Active or protected** → print:
  > Active/protected tasks are read-only — pick another.
  Return to Step 3.

- **`[done]`** → show only:
  ```
  1) Drop
  ```
  Confirm with the user. Record the drop decision. Return to Step 3.

- **Otherwise (unmarked, `[s]`)** → show the full action menu:
  ```
  1) Keep as-is
  2) Shorten
  3) Fold into <slug>
  4) Drop
  5) Extract to proposal
  ```
  Append `(Recommended)` to one action using these heuristics (at most one recommendation per task):
  - Body exceeds `groom.brevity-threshold-lines` lines OR `groom.brevity-threshold-chars` chars → `5) Extract to proposal (Recommended)`
  - Empty body → `4) Drop (Recommended)` (or `2) Shorten (Recommended)` if title hints at real content)
  - Otherwise → no Recommended tag

  **On user selection:**
  - `1` (Keep): record decision. Return to Step 3.
  - `2` (Shorten): prompt for the new body inline. Record decision. Return to Step 3.
  - `3` (Fold): prompt for target slug. Validate against existing slugs from the parse output — re-prompt if the slug is not found. Record decision. Return to Step 3.
  - `4` (Drop): prompt for a one-line reason (recorded in the commit message). Record decision. Return to Step 3.
  - `5` (Extract): flag if `proposal-<slug>.md` already exists in `<WIKI_PATH>` — warn the user now; Step 6 enforces the final guard. Record decision. Return to Step 3.

When the user types `done`, fall through to Step 5.

Do NOT modify Home.md during this step.

## Step 5 — Write proposal

After the user has worked through entries by number and typed `done`, write the consolidated proposal to
`.scratch/groom-proposal.md`:

```markdown
# mill-groom proposal

Candidates reviewed: <N>
Changes proposed: <shortened> shortened, <folded> folded, <dropped> dropped, <extracted> extracted

## Decisions

| Slug | Title | Current action |
|---|---|---|
| my-task | My Task Title | Shorten |
| old-task | Old Task | Drop — superseded by new-task |
| big-task | Big Exploratory Task | Extract to proposal-big-task.md |

## Shortened entries (before → after)

### my-task

**Before:**
<original body>

**After:**
<proposed shorter body>

## Extracted entries

### big-task → proposal-big-task.md

<first 3 lines of proposed proposal-big-task.md>
```

Print a one-line summary to chat and the path. User replies `approve` or `reject`.

On `reject`: ask what to change, revise decisions, rewrite the proposal, and ask again.

## Step 6 — Apply (on approve)

1. Read `<WIKI_PATH>/Home.md` again (in case of concurrent edits since Step 2).
2. For each **extract** decision: check whether `<WIKI_PATH>/proposal-<slug>.md`
   already exists. If it does, **stop** and ask the user:
   > `proposal-<slug>.md` already exists in the wiki. Overwrite, skip, or rename?
   Wait for instruction before proceeding.
3. Build the new `Home.md` content in memory:
   - **Shorten**: replace the entry body with the approved shorter text.
   - **Fold**: remove the entry; leave the target entry unchanged unless the
     user asked to append a note.
   - **Drop**: remove the entry.
   - **Extract**: replace the entry body with a 1-line link:
     `See [proposal-<slug>.md](proposal-<slug>.md).`; write the full body to
     `<WIKI_PATH>/proposal-<slug>.md`.
4. Write all changed files and push via `_wiki.write_commit_push`:
   ```bash
   PYTHONPATH=$CLAUDE_PLUGIN_ROOT/scripts python -c "
   import _paths, _wiki
   wiki = _paths.resolve_wiki_path(_paths.resolve_git_root())
   # Build relative_paths = ['Home.md'] + any 'proposal-<slug>.md' created
   _wiki.write_commit_push(wiki, relative_paths, commit_msg)
   "
   ```
   Commit message format: `chore: groom Home.md — N shortened, N folded, N dropped, N extracted`
   (omit zero-count terms, e.g. `chore: groom Home.md — 2 shortened, 1 dropped`).
5. Regenerate the sidebar:
   ```bash
   PYTHONPATH=$CLAUDE_PLUGIN_ROOT/scripts python -c "
   import _paths, _sidebar
   wiki = _paths.resolve_wiki_path(_paths.resolve_git_root())
   _sidebar.regenerate(wiki)
   "
   ```
6. Delete `.scratch/groom-proposal.md`.

## Step 7 — Report

```
Groom complete.
  <X> shortened
  <Y> folded
  <Z> dropped
  <W> extracted
  <N> kept as-is
```

## Rules

- **Never silently rewrite Home.md.** The proposal/approval gate is non-negotiable.
- **Protected tasks are never modified.** Any entry whose body contains
  `<!-- protected -->` is listed as read-only; no actions are offered.
- **`[active]` tasks are never modified.** Listed for context; all actions blocked.
- **`[done]` tasks get only the `drop` action** — never shorten, fold, or extract.
- **One commit per session** — all changes land in a single `_wiki.write_commit_push` call.
- **All-or-nothing approval** — the user approves or rejects the full proposal.
  Adjust individual decisions before approving if needed.

## Out of scope

- No GitHub issue integration. Use `/mill-ghissues-to-tasks` for that.
- No multi-machine coordination.
- No cross-wiki grooming.
