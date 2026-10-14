# Plan: Drop the eager verify-baseline pre-flight

```yaml
task: "Drop the eager verify-baseline pre-flight"
slug: "drop-verify-baseline-preflight"
approved: true
started: "20261014-090105"
parent_branch: "main"
root: ""
verify: null
skip_checks: ["wiki-config-mutation"]
discussion_sha: "f73a04e55b00f58583d0296f28f357a8b962ab14"
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: implement-stage-removal
    file: 01-implement-stage-removal.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py
  - number: 2
    name: fix-finalize-strict
    file: 02-fix-finalize-strict.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-fix.py test-fix-finalize.py
  - number: 3
    name: merge-in-recompute-removal
    file: 03-merge-in-recompute-removal.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-merge-in-subagent.py test-brief-commit.py
  - number: 4
    name: status-and-module-removal
    file: 04-status-and-module-removal.md
    depends-on: [1, 2, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py test-millpy-implement.py test-millpy-merge-in-subagent.py test-millpy-fix.py
  - number: 5
    name: strict-verify-gates
    file: 05-strict-verify-gates.md
    depends-on: [1, 2, 4]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-done-gate.py test-millpy-implement.py test-fix-finalize.py
  - number: 6
    name: docs-and-comments
    file: 06-docs-and-comments.md
    depends-on: [1, 2, 3, 4, 5]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-worktree.py test-plan-dag.py test-guards.py test-done-gate.py
```

## Shared Decisions

### Decision: removal-order

- **Decision:** callers stop using the mechanism first (batches 1-3), then the shared modules lose it (batch 4: `_status.py` functions, `_verify_baseline.py`; batch 5: `_implementer_common.py` parameters and helpers), then docs and the final grep (batch 6).
- **Rationale:** every intermediate commit stays importable and green.
  The removed `_implementer_common` kwargs default to `None`, so callers can drop them before the parameters go.
  `_verify_baseline.py` imports `_extract_failure_signatures` and calls it with `returncode=`, so it must be deleted (batch 4) before batch 5 removes that parameter.
- **Applies to:** all batches

### Decision: strict-gate-semantics

- **Decision:** after this task, `_implementer_common._run_verify_gates` runs the batch verify and returns its stuck dict on any failure; if the batch verify passes and a module-wide verify is configured, it runs that and returns its stuck dict (reason prefixed `[module-wide verify] `) on failure; otherwise `None`.
  No waiver, no skip.
- **Rationale:** discussion Decision `strict-gate-semantics` and `outright-removal`; nothing replaces the removed mechanism.
- **Applies to:** all batches

### Decision: verify-scope-avoids-known-red-tests

- **Decision:** every batch `verify:` is a `run-all.py --only` list of files this batch edits or whose behaviour depends on what it edits.
  None of `main`'s nine known-red files (`test-bg-liveness.py`, `test-long-path.py`, `test-mill-go-base-agent-only.py`, `test-junction.py`, `test-millpy-validate-plan.py`, `test-phase-wait.py`, `test-shortcut-wrapper.py`, `test-safe-rmtree.py`, `test-plan-validate.py`) appears in any verify.
  All listed files were confirmed green on the task branch tip before planning.
- **Rationale:** discussion Constraints; with strict gates a red parent test halts the batch.
- **Applies to:** all batches

### Decision: unused-import-check

- **Decision:** every card that deletes code from a script under `plugins/mill/scripts/` finishes by running `uvx ruff check --select F401,F841,F811 <edited script>` and removing any import or local the deletion left unused.
  Only names this task made unused are removed.
- **Rationale:** the repo-wide `ruff check .` carries pre-existing debt (see `no-lint-done-gate`), so a scoped, rule-limited check on each edited file is the only lint signal that isolates this task's own leftovers.
- **Applies to:** all batches

### Decision: no-lint-done-gate

- **Decision:** recommend no `pipeline.done_gate` change (currently `null`).
- **Rationale:** a repo-wide `run-all.py` fails on `main`'s nine known-red tests (out of scope here).
  `uvx ruff check .` run at the task branch tip reported 1981 pre-existing errors, so no lint command is recommended either.
  Not applied: mill-go gates on the effective config value, not this Decision.
- **Applies to:** all batches

### Decision: config-key-removal-is-safe-mid-flight

- **Decision:** batch 4 removes `pipeline.baseline_verify_timeout_minutes` from the hub `mill-config.yaml` and the plugin template in one card; the validator's `wiki-config-mutation` check is skipped for this plan.
- **Rationale:** key removal only.
  The sole reader is `millpy-implement.py`'s `--stage baseline` branch, removed in batch 1 before batch 4 runs.
  The deployed copy a running mill-go uses reads the key via `pipeline_cfg.get(...)`, so an absent key resolves to `None` (no ceiling), which is that key's current value — the in-flight run behaves identically.
- **Applies to:** status-and-module-removal

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_long_path.py`
- `plugins/mill/scripts/_plan_dag.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-done-gate.py`
- `plugins/mill/unit_tests/test-fix-finalize.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-status.py`
- `plugins/mill/unit_tests/test-worktree.py`
