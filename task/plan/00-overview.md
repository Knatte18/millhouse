# Plan: 46 (A) — Home.md state machine + split mill-merge teardown into mill-cleanup

```yaml
task: "46 (A) — Home.md state machine + split mill-merge teardown into mill-cleanup"
slug: home-md-states-teardown-split
approved: false
started: "20260511-181145"
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches. Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: foundation
    file: 01-foundation.md
    depends-on: []
    verify: "python plugins/mill/unit_tests/test-tasks-md.py && python plugins/mill/unit_tests/test-marker.py && python plugins/mill/unit_tests/test-worktree.py"
  - number: 2
    name: state-machine-skills
    file: 02-state-machine-skills.md
    depends-on: [1]
    verify: null
  - number: 3
    name: mill-cleanup-logic
    file: 03-mill-cleanup-logic.md
    depends-on: [1]
    verify: "python plugins/mill/unit_tests/test-cleanup.py"
  - number: 4
    name: docs-integration
    file: 04-docs-integration.md
    depends-on: [2, 3]
    verify: null
```

## Shared Decisions

### Decision: status.md is the lifecycle source of truth; Home.md is the coordination index

- **Decision:** Skills that need lifecycle-phase information read `task/status.md`. Home.md markers are the coordination/ownership signal. `_marker.slug_from_branch` validates only slug existence, not phase.
- **Rationale:** The premature `[done]` flip in mill-go (#230) cascaded into multiple skills because they used Home.md as a phase oracle. Splitting authority eliminates this class of bug.
- **Applies to:** all batches

### Decision: New Home.md phases must round-trip through `_tasks_md` parse/set

- **Decision:** Any code that writes a Home.md marker uses `_tasks_md.set_phase` or `set_phase_at`. Never construct slug-line text manually. Phase validation lives in `_tasks_md._VALID_PHASES`.
- **Rationale:** Centralised regex + validation means a phase typo fails loudly, and the parser stays the single source of truth for marker syntax.
- **Applies to:** all batches

### Decision: Archive tag is the canonical "squash landed" signal for cleanup

- **Decision:** mill-cleanup gates teardown on `git tag -l archive/<slug>`. The legacy `git log parent..child_branch` guard is replaced — it returns false-positives for squash merges (child branch stays ahead of parent in history).
- **Rationale:** Archive tags are created by mill-merge Step 6 immediately before the Home.md `[done]` flip; their presence proves the squash landed. For PR-reap, mill-cleanup creates the tag pointing to the child branch tip or the PR's `mergeCommit` SHA (fallback when GitHub auto-deletes the branch).
- **Applies to:** batch 3

### Decision: PR-pending detection reads status.md `phase`, not Home.md marker

- **Decision:** `build_plan` detects PR-reap candidates via `status.md phase: pr-pending` (set by mill-merge Step 5 in BOTH PR-creation paths). Home.md `[pr-pending]` is the human-visible coordination signal; it is not the code-level detection gate.
- **Rationale:** status.md is already the authoritative lifecycle source; reading the same source for the PR-reap trigger keeps the gate consistent with how `[done]`-vs-`[ready-to-merge]` is resolved (status.md phase + Home.md marker together).
- **Applies to:** batch 3

### Decision: Markdown-only batches (2 and 4) have no automated verify

- **Decision:** Batches 2 and 4 produce SKILL.md and integration-test text changes only. `verify: null`. Reviewer is sufficient; running the integration test (`test-merge.py`) requires real `git` + LLM and is operator-driven.
- **Rationale:** YAGNI — no markdown linter is wired into the codebase, and the integration test is not part of the normal unit-test suite.
- **Applies to:** batches 2 and 4

## All Files Touched

- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/scripts/_marker.py`
- `plugins/mill/scripts/_tasks_md.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/skills/mill-cleanup/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-status/SKILL.md`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-marker.py`
- `plugins/mill/unit_tests/test-tasks-md.py`
- `plugins/mill/unit_tests/test-worktree.py`
