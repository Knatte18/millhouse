# Plan: mill-go/millpy-implement: Windows dotnet build-server file-lock races in verify/baseline stages

```yaml
task: "mill-go/millpy-implement: Windows dotnet build-server file-lock races in verify/baseline stages"
slug: mill-go-windows-buildserver-lock-hygiene
approved: true
started: 20260814-090726
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
    name: dotnet-verify-lock-retry
    file: 01-dotnet-verify-lock-retry.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
  - number: 2
    name: baseline-teardown-defense-in-depth
    file: 02-baseline-teardown-defense-in-depth.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-worktree.py test-millpy-implement.py
```

## Shared Decisions

### Decision: dotnet-lock-signature-vs-cleanup-race-signature

- **Decision:** the new MSB3021/MSB3027/"is locked by:" signature check
  (`_has_dotnet_lock_race_signature`, batch 1) is a distinct helper from the existing
  `_has_windows_cleanup_race_signature` (`unlinkat`/`access is denied`/`winerror 5`/`winerror 32`).
  The two are never merged and never share a signature list.
- **Rationale:** the two signatures drive opposite responses. A cleanup-race signature with no
  failure markers is treated as benign pass (`_is_benign_windows_cleanup`). A dotnet-lock
  signature always coincides with `Build FAILED.` in the output — which already matches the
  existing `has_failure_marker` check — so the benign-pass branch structurally can never fire for
  it; treating it as benign-pass would also be unsafe, since a genuine (non-lock) compile failure
  produces the same "no test ran" shape. The dotnet-lock signature instead triggers a real
  retry-and-judge-the-retry response (batch 1, Card 1).
- **Applies to:** batch 1 (`_implementer_common.py`).

### Decision: baseline-shutdown-and-verify-shutdown-are-independent-call-sites

- **Decision:** batch 1's verify-gate retry and batch 2's baseline-teardown retry each run their
  own `dotnet build-server shutdown` best-effort call. Neither batch reuses or shares a helper
  with the other for this.
- **Rationale:** the two racing code paths (a finalize-stage verify replay vs. a disposable
  worktree's `git worktree remove`/`safe_rmtree` teardown) have different call shapes — one has
  the verify command string available to gate the shutdown on `"dotnet" in cmd`, the other
  (`_worktree.remove_safe`) only has a worktree path with no equivalent per-command signal, so its
  shutdown call is unconditional (see batch 2's own `baseline-shutdown-unconditional` framing in
  `_mill/discussion.md`). Sharing one helper across two different gating rules would obscure the
  gating difference for no benefit — each caller's shutdown block is ~6 lines, not worth
  extracting.
- **Applies to:** batch 1 (`_implementer_common.py`), batch 2 (`_worktree.py`).

### Decision: python-project-verify-and-pythonpath-prefix

- **Decision:** every batch's `verify:` command in this plan is prefixed with the literal
  `PYTHONPATH= ` token per this repo's own Python-project convention (this repo has
  `plugins/mill/pyproject.toml`), so the verify subprocess does not inherit the mill cache's
  `PYTHONPATH` and loads worktree modules instead of stale cache modules.
- **Rationale:** required by `CLAUDE.md`'s "Verify command shape" rule and enforced by
  `_plan_validate.py`'s `verify-not-isolated` check.
- **Applies to:** all batches.

### Decision: done-gate-stays-null

- **Decision:** this plan does NOT set `pipeline.done_gate` in `mill-config.yaml`, despite
  `mill-plan/SKILL.md`'s "Done-gate reminder" generally defaulting it to the language's lint
  command (`ruff check .` for Python) whenever batch-verify scopes are narrow and `done_gate` is
  currently `null` (both true here).
- **Rationale:** verified directly against the current tree (`PYTHONPATH= uvx ruff check .` run
  from `git_root` before writing this plan) -- `ruff check .` currently reports 1902 pre-existing
  errors across the repo, unrelated to this task. Setting `done_gate: "ruff check ."` would make
  `mill-go-base/handoff.md`'s terminal Handoff gate fail for every task in this hub from that point
  forward, not just this one, since the gate runs unconditionally at `done`-marking time regardless
  of which task is finishing -- the opposite of the guidance's intent (catching *new* regressions
  outside batch-verify scope). The SKILL's guidance does not anticipate a lint command that is
  itself not yet clean repo-wide; bringing the repo to a ruff-clean state is an unrelated,
  large-scope cleanup with no connection to Windows dotnet build-server lock hygiene and is not
  planned here (YAGNI -- out of this task's scope per `_mill/discussion.md`'s own `## Scope`
  section, which does not mention linting).
- **Applies to:** repo-wide config; no batch in this plan touches `mill-config.yaml`.

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-worktree.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
