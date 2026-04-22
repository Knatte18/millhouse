---
name: mill-revise-tasks
description: Drain the GitHub issue queue into Home.md. One-shot. Proposes a task per issue (new or folded-in), closes consumed issues with a pointer comment, leaves skipped ones alone.
---

# mill-revise-tasks

One-shot triage of the repo's open GitHub issues into `Home.md` task entries.

For every open issue, work interactively with the user to decide whether it becomes a new task, folds into an existing task, or is skipped. On user approval, write the resulting `Home.md`, commit+push via the wiki, and **close every consumed issue** with a comment pointing at the task slug. Skipped issues are untouched.

Leaving claimed-but-open issues on GitHub is a forgetting hazard — that's why the closed-with-comment model is preferred over a "tracked" label.

## Entry checks

1. `gh auth status` must succeed. If not, stop:
   > `gh` is not authenticated. Run `gh auth login` and re-invoke `/mill-revise-tasks`.
2. `.millhouse/wiki/` junction must exist. If not, stop and tell the user to run `mill-setup`.

## Step 1 — Fetch all open issues

Use the `_gh_issues` library. From the hub root:

```bash
PYTHONPATH=plugins/mill/scripts python -c "
import json, _gh_issues
issues = _gh_issues.fetch(limit=100)
print(json.dumps(issues, indent=2))
" > .millhouse/scratch/issues.json
```

Read `.millhouse/scratch/issues.json`. Record the repo name (`_gh_issues.detect_repo()`) for the close step.

## Step 2 — Read the current Home.md

Resolve the wiki path via the `junctions:` block in `<wiki>/config.yaml` (see `CLAUDE.md` for tokens). Read `Home.md` and parse task entries — headings matching `## <Title> [<slug>]` or `## <Title> [[<slug>]](proposal-<slug>)`.

You don't need a parser helper; a targeted regex is fine — this skill is interactive and the user is in the loop.

## Step 3 — Interactive decisions (per issue)

For each fetched issue, present it to the user and ask for a decision:

- **New task** — you draft a title and a 1–2 sentence summary from the issue body. User edits if needed.
- **Fold into existing task `<slug>`** — issue is covered by an existing entry; record the reference. Multiple issues can fold into the same task.
- **Skip** — leave the issue alone on GitHub. No comment, no close. (Keep a short note of why for the final report.)

Process issues one at a time or in small batches — whatever lets the user keep context. Do NOT auto-decide; the user chooses for every issue.

For each "new task", decide together whether it needs a `proposal-<slug>.md` at the wiki root (long-form background).

## Step 4 — Propose

Write the consolidated proposal to `.millhouse/scratch/revise-proposal.md`:

```markdown
# mill-revise-tasks proposal

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
   - For each fold-in, leave existing task text unchanged unless the user asked to append a note.
2. Write Home.md + any new `proposal-<slug>.md` files to the wiki and push via `_wiki.write_commit_push`.
3. Regenerate the sidebar (`_sidebar.regenerate`) and commit if it changed.
4. For each consumed issue (new or fold-in), call:
   ```bash
   PYTHONPATH=plugins/mill/scripts python -c "
   import _gh_issues
   _gh_issues.close_with_comment(<N>, 'Consolidated into wiki task: <slug>')
   "
   ```
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

- **One-shot** — there is no resumable intermediate state. If the user closes mid-flow, the proposal file at `.millhouse/scratch/revise-proposal.md` is the only artefact; starting over is fine.
- **Skipped issues are untouched** — no comment, no label, no close. Forgetting is better than lingering "tracked" state.
- **Close only on approval + actual write** — never close an issue before the task is committed to Home.md.
- **Pointer comment is the invariant** — every closed issue gets `Consolidated into wiki task: <slug>` so someone browsing closed issues later can find where it went.
