# Plan: Finish V3 wiki adoption — complete batch 3 port and test sweep

```yaml
task: "Finish V3 wiki adoption — complete batch 3 port and test sweep"
slug: wiki-v3-batch3-finish
approved: true
started: '20260525-132035'
parent: hanf/wiki-v3-adoption
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: daemon-startup-diagnose-and-fix
    file: 01-daemon-startup-diagnose-and-fix.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-claim.py"
  - number: 2
    name: spawn-core-v2-elimination
    file: 02-spawn-core-v2-elimination.md
    depends-on: [1]
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-color.py"
  - number: 3
    name: millpy-spawn-v2-elimination
    file: 03-millpy-spawn-v2-elimination.md
    depends-on: [2]
    verify: "PYTHONPATH= uv run --project plugins/mill python -c \"import sys, importlib.util; sys.path.insert(0, 'plugins/mill/scripts'); spec = importlib.util.spec_from_file_location('m', 'plugins/mill/scripts/millpy-spawn.py'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); print('ok')\""
  - number: 4
    name: small-clis-and-surface-fixes
    file: 04-small-clis-and-surface-fixes.md
    depends-on: [1]
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-terminal.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-vscode.py"
  - number: 5
    name: test-sweep-heavy
    file: 05-test-sweep-heavy.md
    depends-on: [3, 4]
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-fold.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-spawn-core.py"
  - number: 6
    name: test-sweep-light-and-finalize
    file: 06-test-sweep-light-and-finalize.md
    depends-on: [5]
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py"
```

## Shared Decisions

### Decision: implementer-model-is-sonnet

- **Decision:** All batches target the sonnet implementer model.
- **Rationale:** Issue [#371](https://github.com/Knatte18/millhouse/issues/371) was filed for haiku print-mode context exhaustion on this exact corpus. Sonnet has the context headroom for the V2-elimination port + test-sweep work and avoids re-triggering #371.
- **Applies to:** all batches

### Decision: stuck-policy-pause-for-human

- **Decision:** Stuck-handling policy is **pause for human input** (mill-go's `pipeline.autonomous_mode: false`).
- **Rationale:** Several cards (notably card 3's daemon-fix and card 4's `_spawn_core.merge_tasks` adoption) touch design judgement calls. Pause-and-ask is cheap; wrong-direction auto-fix compounds.
- **Applies to:** all batches

### Decision: effort-tagged-cards-with-4-unit-batch-ceiling

- **Decision:** Every card carries an explicit `**Effort:**` tag with one of `S` (1 unit; small, < 50 LOC diff, single concept), `M` (2 units; 50–200 LOC, one decision), `L` (4 units; > 200 LOC or cross-file refactor, multiple decisions). Each batch sums effort units; **the sum MUST NOT exceed 4**. The plan reviewer must compute the sum and reject batches over 4.
- **Rationale:** #371's root cause was implementer context exhaustion, not raw card count. Weighted ceiling lets the planner split work where it actually costs context.
- **Applies to:** all batches

### Decision: verify-isolation-pythonpath-prefix

- **Decision:** Every batch's `verify:` command MUST start with the literal `PYTHONPATH= ` (empty value, single space) so the test subprocess does not inherit the cache `PYTHONPATH` and load V2-cache modules instead of worktree code. The validator's `verify-not-isolated` check enforces this.
- **Rationale:** This was the prerequisite (`wiki-v3-verify-isolation`, commit `7e10ddb`) for this task to be diagnosable. Without it, test failures were masked by V2-cache leakage.
- **Applies to:** all batches

### Decision: surfaced-bug-policy

- **Decision:** Any test failure reasonably attributable to the V2→V3 port (e.g. a fixture that worked under V2 but breaks under V3 because of a different API contract) is fixed in-scope, by adding a card to the appropriate batch. Truly orthogonal bugs (e.g. an unrelated bug in `wiki._sync`) get a GitHub issue + a `pytest.skip("see #NNN")` mark with the issue link.
- **Rationale:** Discussion-level policy. The handoff anticipated this — `test-wiki-noop-commit`'s push-destination failure (handled by card 11) is exactly this kind of case.
- **Applies to:** all batches

### Decision: card-4-deletes-_task_to_dict-helper

- **Decision:** The `_task_to_dict` helper at `_spawn_core.py:257-268` (introduced in commit `a1f7aac` as a partial-port scaffold) is **deleted** as part of card 4's last step. Once `_spawn_core.py` consumes `wiki.list_tasks_brief` directly, no V2 `Task` objects flow through the system, so no conversion helper is needed.
- **Rationale:** Keeping the helper forever would be dead code. Deleting it is part of the "eliminate V2" goal. The same principle applies generally: any V2-only scaffolding (helper, test case, fixture) introduced as a transition aid gets deleted, not bent to fit V3.
- **Applies to:** batch 2 (card 4); the deletion principle extends to V2-only test cases in batch 5 (cards 8, 9) and batch 6 (card 12).

### Decision: drop-heading_line_no-and-s-phase-everywhere

- **Decision:** Remove all references to V2's `heading_line_no` field from `_spawn_core.py` and any test that asserts on it. Error messages that quoted line numbers become slug-based (e.g. `f"task {slug}: ..."`). Similarly, remove the `[s]` (spawn-ready) phase fast-paths in `_spawn_core` — V3 has no `[s]` phase.
- **Rationale:** V3 stores tasks in TinyDB; no text positions to track. `[s]` is not a V3 status.
- **Applies to:** batch 2 (card 4); batch 5 / 6 (any test that asserts on the dropped fields)

## All Files Touched

- `_mill/plan/01-daemon-startup-diagnose-and-fix.md`
- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/integration_tests/test-spawn-units.py`
- `plugins/mill/integration_tests/test-spawn.py`
- `plugins/mill/integration_tests/test-wiki-concurrency.py`
- `plugins/mill/scripts/_junction.py`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_spawn_core.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/scripts/millpy-inspect.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/scripts/millpy-status.py`
- `plugins/mill/scripts/millpy-terminal.py`
- `plugins/mill/scripts/millpy-vscode.py`
- `plugins/mill/scripts/millpy-wikipush.py`
- `plugins/mill/scripts/wiki/_client.py`
- `plugins/mill/scripts/wiki/_parse.py`
- `plugins/mill/unit_tests/_test_helpers.py`
- `plugins/mill/unit_tests/test-fold.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-spawn-core.py`
- `plugins/mill/unit_tests/test-wiki-noop-commit.py`
