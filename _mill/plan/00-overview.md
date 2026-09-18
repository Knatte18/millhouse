# Plan: millpy-implement.py / _done_gate.py: Windows baseline teardown, truncated failure reason, ignored --start-sha

```yaml
task: "millpy-implement.py / _done_gate.py: Windows baseline teardown, truncated failure reason, ignored --start-sha"
slug: millpy-implement-and-done-gate-cli-bugs
approved: false
started: "20260918-175826"
parent: main
root: ""
verify: null
discussion_sha: 9cd36818483e92a5ff24b9dcc933cbbe2d9fa88d
```

## Batch Index

```yaml
batches:
  - number: 1
    name: worktree-winerror32-retry
    file: 01-worktree-winerror32-retry.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-worktree.py
  - number: 2
    name: done-gate-reason-priority
    file: 02-done-gate-reason-priority.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-done-gate.py
  - number: 3
    name: implement-finalize-start-sha
    file: 03-implement-finalize-start-sha.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-implement.py
```

## Shared Decisions

### Decision: three-independent-bug-batches

- **Decision:** Each batch maps 1:1 to one of the three independently-reported bugs (#1032, #1020, #1012). No batch edits a file another batch also edits, and no batch's fix depends on another batch's fix landing first.
- **Rationale:** The three bugs were only bundled into one wiki task because they share the `millpy-implement.py`/`_done_gate.py` CLI surface, not because they interact. Keeping them as independent, dependency-free batches lets each land, get reviewed, and verify in isolation, matching `_mill/discussion.md`'s Scope section (each fix is scoped to its own module).
- **Applies to:** all batches

### Decision: done-gate-left-null

- **Decision:** `pipeline.done_gate` stays `null` (unchanged from the hub's current `mill-config.yaml`). This plan does not set it.
- **Rationale:** mill-plan's own "Done-gate reminder" guidance suggests considering a repo-wide lint/test `done_gate` when batch-verify scopes are narrow (true here — each batch's `verify:` targets one test file). But `mill-config.yaml` is a shared hub file outside this task's `_mill/discussion.md` Scope/Out (which scopes this task to three CLI bug fixes only), and opting the whole hub into a new `done_gate` policy as a side effect of an unrelated hotfix task is scope creep this task's own discussion never authorized. Declined per the guidance's own escape valve ("record the finding in the plan overview's Shared Decisions instead").
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_done_gate.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/unit_tests/test-done-gate.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-worktree.py`
