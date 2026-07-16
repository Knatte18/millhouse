# Plan: mill-finalize/mill-merge corrupt or mishandle _mill/status.md and task_dir on stacked branches

```yaml
task: "mill-finalize/mill-merge corrupt or mishandle _mill/status.md and task_dir on stacked branches"
slug: mill-merge-stacked-branch-status-corruption
approved: false
started: "20260716-111113"
parent: "hanf/linux-port-more"
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: parent-branch-identity
    file: 01-parent-branch-identity.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-parent-branch.py
  - number: 2
    name: finalize-step3-restore
    file: 02-finalize-step3-restore.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-finalize-cleanup.py
  - number: 3
    name: merge-slug-check-and-pathspec
    file: 03-merge-slug-check-and-pathspec.md
    depends-on: [1]
    verify: null
  - number: 4
    name: integration-test-coverage
    file: 04-integration-test-coverage.md
    depends-on: [1, 2, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py
```

## Shared Decisions

### Decision: expected_slug is a backward-compatible optional kwarg

- **Decision:** every new `expected_slug` parameter introduced by this plan (on `_parent_branch._read_parent_from_status`, `resolve`, `resolve_for_codeguide`) is keyword-only and defaults to `None`. `None` means "no check requested" — behavior is byte-for-byte identical to today for any caller that doesn't pass it.
- **Rationale:** minimal blast radius (discussion.md `identity-check-scope` Decision) — this plan touches only the call sites that need stacked-branch protection (mill-merge, mill-merge-in, mill-finalize's Dispatch step); every other existing or future caller is unaffected by construction, not by convention.
- **Applies to:** parent-branch-identity, finalize-step3-restore, merge-slug-check-and-pathspec.

### Decision: slug mismatch is treated identically to "field/file absent"

- **Decision:** nowhere in this plan does a slug mismatch introduce a NEW halt path or a NEW fallback source. `_parent_branch.resolve()` on mismatch falls through to its existing "no `parent:` row" prompt/`ParentBranchError` logic. mill-merge's Entry Step 5 phase gate on mismatch falls through to its existing "no `_mill/status.md`" wiki-lookup logic.
- **Rationale:** discussion.md `mismatch-fallback-behavior` Decision — reuses fallback paths that already exist and are already covered by tests, instead of inventing new failure modes.
- **Applies to:** parent-branch-identity, merge-slug-check-and-pathspec.

### Decision: ASCII-only messages

- **Decision:** any new or edited halt/warning message text stays ASCII (`->` not `→`, `--` not `—`).
- **Rationale:** repo-wide convention (CLAUDE.md) — Windows cp1252 stdout crashes on non-ASCII.
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/scripts/_parent_branch.py`
- `plugins/mill/skills/mill-finalize/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/unit_tests/test-finalize-cleanup.py`
- `plugins/mill/unit_tests/test-parent-branch.py`
