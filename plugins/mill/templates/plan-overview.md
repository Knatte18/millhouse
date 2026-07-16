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

`verify:` (top-level, in the frontmatter below) is an OPTIONAL module-wide
check run at each batch boundary AFTER the batch's own `verify:` passes.
`null` means skip (the default; no behavior change for existing plans). When
set, it follows the same `PYTHONPATH= ` shape rule as per-batch `verify:`
commands and should be a cheap whole-module compile/vet/smoke command (e.g.
`PYTHONPATH= go vet ./...` or a scoped `run-all.py`) that catches
cross-package regressions from shared-helper edits at the introducing batch.
A module-wide failure propagates a `stuck_type: verify` stuck dict with
the reason prefixed to indicate module-wide scope so the operator can
distinguish the two gates.

Both the per-batch `verify:` and this module-wide `verify:` also accept
the `{cwd: hub|git_root, command: <string>}` mapping form as an
alternative to the plain string (normalized by
`_plan_dag.parse_verify_field`). The plain string implies `cwd:
git_root`. In a nested layout (`_paths.resolve_hub_path() !=
_paths.resolve_git_root()`), if the command being authored is naturally
hub-relative, write it as the mapping form with `cwd: hub` instead of
the plain-string form. If it is naturally git-root-relative, keep the
plain-string form (or an explicit `cwd: git_root` mapping) — the field
describes how the command is actually written, not a forced choice.

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

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path
across every batch, sorted alphabetically (Move **source** paths are
excluded — they disappear, like `Deletes:` tokens). Cards are the
source of truth; this section is the input `_plan_validate.py`'s
`all-files-touched-mismatch` check cross-references against the derived
union of every card's `Edits:`/`Creates:`/Move-target paths, to catch
drift between the hand/agent-maintained list here and that derived
union._

- `path/to/file.py`
