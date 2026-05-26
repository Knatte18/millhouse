<!--
Template: `<WIKI_PATH>/active/<slug>/plan/00-overview.md` — written by
mill-plan at the start of Phase: Plan.

Tokens: <TASK_TITLE>, <TASK_TITLE_YAML>, <SLUG>, <STARTED>, <PARENT_BRANCH>.

The rendered file is the entry point for the whole plan. Every batch
file refers back to the Batch Index here, and mill-go reads the DAG
from here to schedule work. Fill every section in place — the file
must be self-sufficient for a fresh mill-plan/mill-go session.

`root:` is a filesystem sub-path from the worktree root to where code
lives, used by reviewers when resolving card-level `Context:`/`Edits:`
paths. In the typical mill-v2 worktree where the code IS the worktree
root, leave `root:` empty. Set it only for repos where the worktree
contains multiple roots (rare).

Each batch entry has `number:` (the NN integer prefix, for DAG navigation),
`name:`, `file:`, `depends-on:` (list of integers referencing other batch
`number:` values), and `verify:`.

Strip this HTML comment before writing.
-->
# Plan: <TASK_TITLE>

```yaml
task: <TASK_TITLE_YAML>
slug: <SLUG>
approved: false
started: <STARTED>
parent: <PARENT_BRANCH>
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: NN
    name: <batch-name>
    file: NN-<batch-slug>.md
    depends-on: []
    verify: PYTHONPATH= <command> or null
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: <short-name>

- **Decision:** …
- **Rationale:** …
- **Applies to:** all batches | <batch-name>, <batch-name>

## All Files Touched

_Full union of every `Creates:` / `Edits:` across every batch, sorted
alphabetically. mill-go reads this to warn if two parallel batches
touch the same file — a sign of a misplaced dependency._

- `path/to/file.py`
