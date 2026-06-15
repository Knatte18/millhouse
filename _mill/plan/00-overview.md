# Plan: Fix mill-ghissues-to-tasks to refuse fold-ins into done and deferred tasks

```yaml
task: "Fix mill-ghissues-to-tasks to refuse fold-ins into done and deferred tasks"
slug: "ghissues-skill-fold-guard"
approved: false
started: "20260615-125443"
parent: "main"
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: fold-guard-allowlist
    file: 01-fold-guard-allowlist.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-fold.py
```

## Shared Decisions

### Decision: unclaimed-only allowlist predicate

- **Decision:** A fold target is foldable **iff** `status is None AND not deferred`. Every other state (`active`, `ready-to-merge`, `pr-pending`, `done`, `blocked`, `abandoned`, or any task with `deferred = True`) is refused. This is an allowlist (default-deny), not a denylist.
- **Rationale:** Folding closes the source GitHub issue with a pointer comment; folding into a claimed/terminal/blocked/deferred task silently loses the issue. An allowlist auto-refuses any future status value, which is the safe direction for a guard whose failure mode is silent issue loss. `status is None` is exactly "unclaimed" because `wiki/_parse.py` collapses both the `[s]` spawn-ready marker and the no-marker backlog to `None`; a claimed task always carries a concrete status.
- **Applies to:** all batches

### Decision: read status/deferred with .get(), never subscript

- **Decision:** Read the target task's state as `task.get("status")` and `task.get("deferred", False)`. Never subscript (`task["deferred"]`).
- **Rationale:** `get_task` / `list_tasks_brief` return the raw stored doc; a doc written without a `deferred` key would lack it (upsert defaults `deferred=False` today, but that is an implicit invariant). The `.get()` form is robust to a missing key.
- **Applies to:** all batches

### Decision: remove LOCKED_FOLD_PHASES entirely

- **Decision:** Delete the `LOCKED_FOLD_PHASES` constant from `wiki/__init__.py` and every reference to it (import in `millpy-fold.py`, import + value-assertion in `test-fold.py`, prose pointers in docstrings/SKILLs/CLAUDE.md). The allowlist predicate replaces it and lives in the fold code, not the wiki package.
- **Rationale:** With the allowlist the denylist tuple is dead; keeping it invites two-sources-of-truth drift, and fold policy should not live in the wiki data layer.
- **Applies to:** all batches

### Decision: refusal message names the blocking state

- **Decision:** On refusal, `millpy-fold.py` raises `SystemExit` with a single reason-bearing message, e.g. `Cannot fold into '<slug>': task is not unclaimed (status: <status-or-'deferred'>). Only unclaimed backlog tasks accept fold-ins.` Exit code 1, no Home.md mutation, no GitHub close.
- **Rationale:** One uniform message is natural under an allowlist; surfacing the actual blocking state tells the operator why and what to do (route to a new task or skip).
- **Applies to:** all batches

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/scripts/millpy-fold.py`
- `plugins/mill/scripts/wiki/__init__.py`
- `plugins/mill/skills/mill-fold/SKILL.md`
- `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- `plugins/mill/unit_tests/test-fold.py`
