# Plan: mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution

```yaml
task: 'mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution'
slug: mill-merge-and-merge-in-bugs
approved: false
started: '2026-08-12T18:30:03Z'
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: parent-liveness-module
    file: 01-parent-liveness-module.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-parent-branch.py
  - number: 2
    name: mill-merge-skill-fixes
    file: 02-mill-merge-skill-fixes.md
    depends-on: [1]
    verify: null
  - number: 3
    name: mill-merge-in-and-conflict-brief
    file: 03-mill-merge-in-and-conflict-brief.md
    depends-on: [1]
    verify: null
  - number: 4
    name: integration-tests
    file: 04-integration-tests.md
    depends-on: [1, 2, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions, error-handling posture, test frameworks, style/lint constraints.
One subsection per decision.
Batch-local decisions live in each batch file._

### Decision: liveness-check-contract

- **Decision:** `_parent_branch.check_liveness(branch: str, git_root: Path) -> bool` and `_parent_branch.resolve_dead_parent(dead_branch: str, git_root: Path, cfg: dict, *, max_hops: int = 10) -> dict` (batch 1) are the single source of truth for #817's dead-parent-branch detection. `resolve_dead_parent` returns exactly one of three outcome shapes: `{"outcome": "resolved", "branch": <live-branch>, "hops": [<slug>, ...]}`, `{"outcome": "fallback", "reason": "no-tag" | "chain-end", "branch": <base_branch>, "hops": [...]}`, or `{"outcome": "cycle", "hops": [...]}` (the 10-hop cap was hit with no resolution). Both `mill-merge/SKILL.md` Entry Step 4 and `mill-merge-in/SKILL.md` Entry step 2 (batches 2 and 3) call these two functions identically; the integration tests (batch 4) assert against these same three outcome shapes directly.
- **Rationale:** one contract, defined once, keeps both SKILL.md call sites and the tests describing the same behavior instead of drifting.
- **Applies to:** parent-liveness-module, mill-merge-skill-fixes, mill-merge-in-and-conflict-brief, integration-tests.

### Decision: rollback-target-and-ff-only

- **Decision:** the Steps 1-5 rollback in `mill-merge/SKILL.md` always resets the parent worktree to `origin/<parent_branch>` — never `mill-checkpoint-<name>` (that ref belongs to the child worktree's own pre-merge-in history). The new pre-squash parent-advance step always uses `git merge --ff-only origin/<parent_branch>` — never `git reset --hard` — so a parent worktree with local-only commits fails loudly (halt, rollback-exempt) instead of silently discarding them.
- **Rationale:** `reset --hard` silently destroys local-only commits; `merge --ff-only` fails safely instead. A rollback that resets to child history is actively destructive to the parent worktree regardless of which Steps 1-5 failure triggered it.
- **Applies to:** mill-merge-skill-fixes, integration-tests.

## All Files Touched

- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/scripts/_parent_branch.py`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/templates/merge-in-conflict-brief.md`
