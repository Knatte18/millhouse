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
   PYTHONPATH=plugins/mill/scripts python -c "
   import _paths; print(_paths.resolve_wiki_path(_paths.resolve_git_root()))
   "
   ```
   Store as `<WIKI_PATH>`.
3. `_wiki.sync_pull(<WIKI_PATH>)`:
   ```bash
   PYTHONPATH=plugins/mill/scripts python -c "
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
PYTHONPATH=plugins/mill/scripts python -c "
import _paths, _tasks_md
wiki = _paths.resolve_wiki_path(_paths.resolve_git_root())
text = (wiki / 'Home.md').read_text(encoding='utf-8')
tasks = _tasks_md.parse(text)
import json
print(json.dumps([{'slug': t.slug, 'title': t.title, 'phase': t.phase} for t in tasks], indent=2))
"
```

**Scope rules:**

| `task.phase` | In scope? | Actions available |
|---|---|---|
| `None` (plain backlog) | Yes | keep / shorten / fold / drop / extract |
| `"s"` (spawn-ready) | Yes | keep / shorten / fold / drop / extract |
| `"active"` | **Never** | — (skip entirely) |
| `"done"` | Yes (drop only) | drop (with confirmation) |

Skip any entry whose body contains `<!-- protected -->`.

To read the body of a task, read the lines in `Home.md` between its heading
and the next `##` heading (or end of file).

## Step 3 — Identify candidates

Flag entries that warrant attention:

- **Long**: body exceeds `groom.brevity-threshold-lines` lines OR
  `groom.brevity-threshold-chars` characters.
- **Possible duplicate**: title or body overlap with another entry — use your
  judgment; no heuristic required.
- **No summary**: heading exists but body is empty or only whitespace.

Entries that don't match any flag can still be presented if the user asks, but
by default focus on flagged candidates.

## Step 4 — Interactive decisions

Present candidates to the user in small batches (3–5 at a time). For each entry:

1. Show the current heading + body (truncated to ~5 lines if long).
2. Propose a default action with your reasoning.
3. List alternatives.

**Actions:**

- **Keep as-is** — no change.
- **Shorten** — you draft a tighter summary; user approves or edits inline.
- **Fold into `<slug>`** — merge this entry into an existing one; this entry is
  removed. Ask the user which slug to fold into if not obvious.
- **Drop** — remove the entry. Note why in the commit message.
- **Extract to proposal** — move the body to `<WIKI_PATH>/proposal-<slug>.md`
  and replace the Home.md entry with a 1-line summary linking to it.

Do NOT auto-decide. Record every decision as you go.

## Step 5 — Write proposal

After working through all candidates, write the consolidated proposal to
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
   PYTHONPATH=plugins/mill/scripts python -c "
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
   PYTHONPATH=plugins/mill/scripts python -c "
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
  `<!-- protected -->` is skipped without being presented to the user.
- **`[active]` tasks are never modified.** Live work is out of scope.
- **`[done]` tasks get only the `drop` action** — never shorten, fold, or extract.
- **One commit per session** — all changes land in a single `_wiki.write_commit_push` call.
- **All-or-nothing approval** — the user approves or rejects the full proposal.
  Adjust individual decisions before approving if needed.

## Out of scope

- No GitHub issue integration. Use `/mill-ghissues-to-tasks` for that.
- No multi-machine coordination.
- No cross-wiki grooming.
