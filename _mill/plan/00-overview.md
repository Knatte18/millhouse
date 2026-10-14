# Plan: Instrument and bound the verify runner

```yaml
task: Instrument and bound the verify runner
slug: verify-runner-instrumentation
approved: false
started: 20261014-112550
parent_branch: main
root: ""
verify: null
skip_checks: ["wiki-config-mutation"]
discussion_sha: 6229c15d3d1e999f9ece71efc219b91e9394d961
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: verify-run-core
    file: 01-verify-run-core.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-verify-run.py test-status.py test-merge-in-subagent.py test-millpy-merge-in-subagent.py test-millpy-bg.py test-implementer-common.py
  - number: 2
    name: cleanliness-status-exclusion
    file: 02-cleanliness-status-exclusion.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanliness.py
  - number: 3
    name: implementer-gates
    file: 03-implementer-gates.md
    depends-on: [1, 2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-verify-run.py
  - number: 4
    name: gate-callers
    file: 04-gate-callers.md
    depends-on: [3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py test-millpy-fix.py test-fix-finalize.py test-done-gate.py
  - number: 5
    name: merge-in
    file: 05-merge-in.md
    depends-on: [3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-merge-in-subagent.py test-merge-in-subagent.py test-millpy-verify-run.py test-implementer-common.py
  - number: 6
    name: skill-docs
    file: 06-skill-docs.md
    depends-on: [4, 5]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-brief-commit.py test-skill-helper-drift.py test-mill-go-base-agent-only.py test-agent-mode-dispatch.py
```

## Shared Decisions

### Decision: one runner module, one seam

- **Decision:** every verify command runs through `_verify_run.run_verify` (created in batch 1).
  It owns the `Popen`, the output file, the env keys, the timeout and tree kill, the START/HEARTBEAT/END lines, the first-run marker and the `## Verify log` row.
  Callers never call `subprocess.run` for a verify command again.
  The `dotnet build-server shutdown` post-steps stay plain `subprocess.run` calls, untouched.
- **Rationale:** the discussion's "Shared runner module" decision; one place for the instrumentation.
- **Applies to:** all batches

### Decision: tests mock at the `run_verify` seam

- **Decision:** unit tests of gate sites patch `_verify_run.run_verify` and return canned `_verify_run.VerifyRun` records.
  Only `test-verify-run.py` and `test-millpy-verify-run.py` spawn real short-lived children (`sys.executable` scripts written to a temp dir, to avoid shell-quoting differences across platforms).
  Tests that count `subprocess.run` calls keep doing so only for the `dotnet build-server shutdown` call.
- **Rationale:** the discussion's Testing section; it keeps gate tests deterministic and keeps `.scratch/verify/` artifacts and `## Verify log` rows out of fixture repos.
- **Applies to:** all batches with tests

### Decision: shared names every batch uses

- **Decision:** batch 1 defines these public names in `plugins/mill/scripts/_verify_run.py`, and later batches use them verbatim:
  `VerifyRun` (dataclass: `label`, `cmd`, `cwd`, `exit_code`, `wall_s`, `first_run`, `timed_out`, `output`, `output_path`, `timeout_s`),
  `VerifyRun.summary() -> dict` (the `verify_runs` element: `label`, `cmd`, `exit_code`, `wall_s`, `first_run`, `timed_out`),
  `run_verify(cmd, *, cwd, label, git_root, timeout_s, shell_mode, env=None, status_path=None) -> VerifyRun`,
  `timeout_seconds(cfg) -> float`, `resolve_status_path(hub_root, cfg) -> Path | None`,
  `timeout_prefix(run) -> str` (returns `"[verify timed out after <N>s: <label>] "`, N an integer),
  `output_suffix(run) -> str` (returns `"\n[verify output: <output_path>]"`),
  `DEFAULT_TIMEOUT_MINUTES = 20`, `HEARTBEAT_INTERVAL_S = 30`.
  Batch 3 adds `_implementer_common._truncate_verify_output(text) -> str` (the existing 2000-char truncation, extracted), which batch 5 reuses.
- **Rationale:** cards in different batches must agree on names without re-reading each other.
- **Applies to:** all batches

### Decision: holistic fixer replay budget

- **Decision:** `millpy-fix.py` keeps its joined holistic replay (`_resolve_holistic_verify` joins every batch's `verify:` into one `(a) && (b) && ...` chain run as one command) and passes `verify_timeout_s * max(1, len(batch_verifies))` as that command's timeout.
  The same scaled value also bounds the fixer's module-wide gate, which is only looser, never tighter.
  The `## Verify log` row for that run carries the joined command cut to 300 characters.
- **Rationale:** the discussion bounds each verify command; the joined chain is N commands in one process, so a flat per-command budget would false-time-out multi-batch plans.
  Splitting the chain into per-batch runner calls would change `_forward_output`'s single-command contract, a larger change than this task needs.
- **Applies to:** gate-callers

### Decision: every failure reason uses one shape

- **Decision:** a failed or timed-out verify's reason is `[timeout_prefix(run) when timed_out] + truncated output + output_suffix(run)`.
  The done gate's timeout reason therefore also carries the label (`[verify timed out after 1200s: done-gate] ...`), a small widening of the discussion's label-less example kept for one consistent shape.
  A launch failure (`exit_code is None and not timed_out`) keeps today's `verify gate raised: <message>` wording in `_run_verify_gate` and `<message>` in `_done_gate`.
- **Rationale:** the discussion requires the output path appended to every failure reason and one prefix the self-resolver can recognise.
- **Applies to:** implementer-gates, gate-callers, merge-in

### Decision: status.md is excluded from every dirty-tree gate

- **Decision:** `## Verify log` rows make `status.md` dirty between a finalize and the next orchestrator status commit.
  The discussion assumed `_in_scope_dirty_stuck` already excludes the task dir; it does not (it excludes only `_mill/briefs/`), and mill-go step 2b's `_cleanliness.revert_out_of_scope_drift` counts every dirty `_mill/` path as in-scope dirt, which would block every batch.
  So `_mill/status.md` (at any depth, matched like `_implementer_common._is_brief_path`) is excluded from:
  `_cleanliness.compute_new_dirt`, `_cleanliness.compute_terminal_dirt`, `_cleanliness.revert_out_of_scope_drift` (batch 2);
  `_implementer_common._in_scope_dirty_stuck`, the `git status --porcelain --untracked-files=no` checks inside `_forward_output`'s inference paths and `_fixer_logic_ancestor_override`, and `_is_formatter_drift_only`'s two `git diff` calls (batch 3).
- **Rationale:** status.md is orchestrator-owned; its dirt is never implementer work, and it is staged by the orchestrator's own status commits.
- **Applies to:** cleanliness-status-exclusion, implementer-gates

### Decision: commit coverage of verify-log rows

- **Decision:** rows become durable at these existing or added commits:
  batch gates and finalize replays -- mill-go's approve-batch, stuck self-resolve, blocked and holistic commits, all of which stage `status_path`;
  `run_preflight` in mill-go Prepare -- `millpy-implement.py --stage prepare`'s start-batch commit, which stages `status_path`;
  `run_preflight` in mill-quick -- its `done` and `blocked` commits;
  `run_gate` at Handoff -- the `done` commit, plus a new status-only commit on the done-gate blocked halt (batch 6);
  merge-in replays -- `mill-merge-in` step 5 newly stages `_mill/status.md`, and the Rollback block captures and restores rows around `git reset --hard` (batch 6).
- **Rationale:** the discussion's "Commit coverage" audit, completed against the SKILL text.
- **Applies to:** skill-docs

### Decision: `_done_gate` takes an optional `hub_root`

- **Decision:** `run_preflight(gate_cmd, git_root, *, hub_root=None)` and `run_gate(gate_cmd, git_root, *, hub_root=None)`.
  When `hub_root` is `None` they use `_paths.resolve_hub_path(git_root)`; the SKILL snippets, which already bind `hub_root = _paths.resolve_hub_path()`, pass `hub_root=hub_root`.
  Positional shape is unchanged.
- **Rationale:** `resolve_hub_path(git_root)` cannot find a nested hub that has no root stub, which would silently drop the status row; the snippets already hold the right hub.
- **Applies to:** gate-callers, skill-docs

### Decision: hub mill-config.yaml edit is safe mid-flight

- **Decision:** batch 1 card 3 adds `pipeline.verify_timeout_minutes: 20` to the hub `mill-config.yaml`; the plan carries `skip_checks: ["wiki-config-mutation"]`.
- **Rationale:** the key is additive and `_verify_run.timeout_seconds` defaults to the same value when it is absent.
  This task's own mill-go runs from the deployed plugin copy, which has no reader for the key yet, so the key is inert until a deploy, and identical in effect afterwards.
- **Applies to:** verify-run-core

### Decision: no done_gate or lint recommendation

- **Decision:** recommend no `pipeline.done_gate` change (effective value `null`).
  `run-all.py` reports 13 of 125 files failing on `main`, and `uvx ruff check .` exits 1 at this worktree's tip with 1957 pre-existing findings, so neither is usable as a gate without unrelated cleanup.
- **Rationale:** mill-plan's done-gate advisory: never recommend a command that already fails on pre-existing debt.
- **Applies to:** all batches

### Decision: verify scopes avoid pre-existing red tests

- **Decision:** every batch `verify:` names only test files that pass on this branch's base (checked at plan time: `test-implementer-common.py`, `test-done-gate.py`, `test-millpy-merge-in-subagent.py`, `test-merge-in-subagent.py`, `test-millpy-bg.py`, `test-status.py`, `test-millpy-implement.py`, `test-millpy-fix.py`, `test-fix-finalize.py`, `test-cleanliness.py`, `test-brief-commit.py`, `test-skill-helper-drift.py`, `test-mill-go-base-agent-only.py`, `test-agent-mode-dispatch.py` all pass) plus the new files this plan creates.
  `test-bg-liveness.py` and `test-ask-thread.py` are never verify targets.
- **Rationale:** the discussion's "Pre-existing red tests on `main`" constraint.
- **Applies to:** all batches

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/scripts/_cleanliness.py`
- `plugins/mill/scripts/_done_gate.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/_verify_run.py`
- `plugins/mill/scripts/millpy-bg.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/scripts/millpy-verify-run.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go-base/handoff.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-quick/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-cleanliness.py`
- `plugins/mill/unit_tests/test-done-gate.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-millpy-bg.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-millpy-verify-run.py`
- `plugins/mill/unit_tests/test-status.py`
- `plugins/mill/unit_tests/test-verify-run.py`
