# Plan: compute_baseline: use the task worktree's own pre-edit state, not a parent-branch checkout

```yaml
task: 'compute_baseline: use the task worktree''s own pre-edit state, not a parent-branch checkout'
slug: baseline-uses-worktree-not-checkout
approved: false
started: 20260923-091042
parent: main
root: ""
verify: null
discussion_sha: 5de408e5c686d5349a912f064c5850e3b3d05139
skip_checks: ["wiki-config-mutation"]
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: status-baseline-fields
    file: 01-status-baseline-fields.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py
  - number: 2
    name: verify-baseline-core
    file: 02-verify-baseline-core.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-verify-baseline.py test-worktree.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-verify-baseline.py
  - number: 3
    name: implement-baseline-stage
    file: 03-implement-baseline-stage.md
    depends-on: [1, 2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py
  - number: 4
    name: implementer-gate-cleanup
    file: 04-implementer-gate-cleanup.md
    depends-on: [3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-fix-finalize.py test-millpy-fix.py
  - number: 5
    name: merge-in-baseline-recompute
    file: 05-merge-in-baseline-recompute.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-merge-in-subagent.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-baseline-waiver.py
  - number: 6
    name: cleanup-orphan-removal
    file: 06-cleanup-orphan-removal.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanup.py
  - number: 7
    name: skill-docs-baseline
    file: 07-skill-docs-baseline.md
    depends-on: [3, 5]
    verify: null
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions, error-handling posture, test frameworks, style/lint constraints.
One subsection per decision.
Batch-local decisions live in each batch file._

### Decision: no-checkout-anywhere

- **Decision:** No batch reintroduces a `git worktree add` / transient-checkout of any kind for baseline computation. `compute_baseline` and the per-batch capture run exclusively against already-resolved, already-on-disk cwds (`git_root`, `hub_root`, or a batch's explicit `cwd:` override) — never a path under `.scratch/`.
- **Rationale:** This is the single premise the whole task rests on (`_mill/discussion.md`'s "Problem" section): the task worktree at `--stage baseline` time already *is* the pre-edit tree, so re-deriving it via a checkout is pure waste and the source of the sibling-merge-drift and cold-build-cost bugs in issue #1130.
- **Applies to:** all batches.

### Decision: mid-flight-config-key-removal-is-safe

- **Decision:** Batch 3 removes `pipeline.baseline_prepare_cmd` from both `mill-config.yaml` (hub) and `plugins/mill/templates/mill-config.yaml` in the same batch that deletes the key's last two readers (`millpy-implement.py`'s `main()` and `_run_baseline_stage`) — see Card 17/18/19. This satisfies the `wiki-config-mutation` validator check's condition (a) (a bootstrap card explaining the change is safe mid-flight): by the time this batch's implementer reaches the config cards, the code that ever read the removed key no longer exists anywhere in this same batch's own diff.
- **Rationale:** Splitting the config edit into a separate, later-dependent batch would leave a window where the config template and the hub config disagree with each other for no benefit — the key has exactly one consumer, and that consumer is deleted in the same batch.
- **Applies to:** implement-baseline-stage (batch 3).

### Decision: done-gate-is-full-suite-not-lint

- **Decision:** `pipeline.done_gate` is set to the repo-wide unit-test runner (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`), not the project's lint command. `uvx ruff check .` was probed against the current worktree tip and exits 1 (pre-existing lint debt: 2009 findings, unrelated to this task), so per mill-plan's "Done-gate reminder" it is NOT defaulted into `done_gate`.
- **Rationale:** This task's own discussion explicitly calls out `run-all.py` passing as the acceptance bar ("Full-suite gate"), and per-batch `verify:` scopes above are deliberately narrow (`--only <file>`), so nothing else catches a regression in a file this task touches but a given batch's own scope doesn't re-run (e.g. a batch-3 edit breaking a batch-1 test after batch 1 already completed). Defaulting `done_gate` to the failing lint command would make every future task in this hub depend on unrelated pre-existing lint debt being fixed first.
- **Applies to:** all batches (checked once, by mill-go, at Handoff time — not a per-batch `verify:`).

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path across every batch, sorted alphabetically (Move **source** paths are excluded — they disappear, like `Deletes:` tokens).
Cards are the source of truth;
this section is the input `_plan_validate.py`'s `all-files-touched-mismatch` check cross-references against the derived union of every card's `Edits:`/`Creates:`/Move-target paths, to catch drift between the hand/agent-maintained list here and that derived union._

- `mill-config.yaml`
- `plugins/mill/integration_tests/test-baseline-waiver.py`
- `plugins/mill/integration_tests/test-verify-baseline.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/_verify_baseline.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-fix-finalize.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-status.py`
- `plugins/mill/unit_tests/test-verify-baseline.py`
- `plugins/mill/unit_tests/test-worktree.py`
