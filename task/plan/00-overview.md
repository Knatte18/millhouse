# Plan: 54 (A) — Bug-fix batch 6 (post-46/50 triage)

```yaml
task: 54 (A) — Bug-fix batch 6 (post-46/50 triage)
slug: mill-misc-fixes-6
approved: true
started: 20260512-091333
parent: main
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
    name: fixes
    file: 01-fixes.md
    depends-on: []
    verify: "python plugins/mill/unit_tests/run-all.py"
```

## Shared Decisions

### Decision: mock-over-real-git

- **Decision:** New `remove_safe` unit tests inject fake git output via `unittest.mock.patch("_worktree._subprocess_util.run", ...)` rather than creating real git worktrees.
- **Rationale:** Consistent with every existing `remove_safe` test case; avoids real-git overhead for error-path coverage.
- **Applies to:** batch 1 (card 5)

### Decision: test-framework

- **Decision:** New test functions follow the `main()` runner pattern already present in `test-worktree.py` and `test-marker.py`; no pytest, no new framework imports.
- **Rationale:** `run-all.py` discovers and runs each test file via `sys.executable`; the existing in-file runner pattern is the canonical style for this test suite.
- **Applies to:** batch 1 (cards 5 and 6)

## All Files Touched

- `plugins/mill/scripts/_marker.py`
- `plugins/mill/scripts/_reviewer_opushigh.py`
- `plugins/mill/scripts/_reviewer_opusmax.py`
- `plugins/mill/scripts/_reviewer_opusmid.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/unit_tests/test-marker.py`
- `plugins/mill/unit_tests/test-worktree.py`
