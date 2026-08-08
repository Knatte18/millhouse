# Plan: Unit test suite: hangs, unmocked-path errors, and stuck/success envelope bug found in piecewise sweep

```yaml
task: 'Unit test suite: hangs, unmocked-path errors, and stuck/success envelope bug found in piecewise sweep'
slug: 'mill-unit-test-suite-breakage'
approved: false
started: '20260808-172311'
parent: 'main'
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: claude-sub-idle-mock
    file: 01-claude-sub-idle-mock.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --sequential --only test-claude-sub.py
  - number: 2
    name: wiki-stub-fixes
    file: 02-wiki-stub-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-claim.py test-millpy-spawn.py
  - number: 3
    name: forward-output-stuck-passthrough
    file: 03-forward-output-stuck-passthrough.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-bg-json-contract.py test-agent-mode-dispatch.py test-millpy-merge-in-subagent.py
  - number: 4
    name: full-suite-regression
    file: 04-full-suite-regression.md
    depends-on: [1, 2, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: wiki-stub injection mechanic

- **Decision:** Every fix for a `from wiki import _client as wiki`-reaching test gap uses the identical three-step mechanic already proven in `test-millpy-spawn.py`'s `test_spawn_rolls_back_when_write_initial_status_fails` (`:1301-1339`): save `sys.modules.get("wiki._client")`, inject a fresh `MagicMock()` at `sys.modules["wiki._client"]` before `spec.loader.exec_module(mod)`, set `mod.wiki` to that same mock immediately after `exec_module`, and restore the saved value in the existing `finally` block.
- **Rationale:** `from wiki import _client as wiki` resolves via `sys.modules["wiki._client"]`, but Python's `_handle_fromlist` skips the injected-module lookup entirely if the real, already-imported `wiki` package object already carries a `_client` attribute from an earlier test in the same process — the `mod.wiki =` assignment is the belt-and-suspenders step that makes the fix reliable regardless of import order across the suite.
- **Applies to:** wiki-stub-fixes (batch 2) only.

### Decision: commit-SHA-correction gating is a passthrough, not a rewrite

- **Decision:** `_forward_output`'s corrective `git rev-parse HEAD` / `_is_valid_commit_sha` block only ever executes on the `status == "success"` input path. Every other status (already-classified `stuck/*`, or anything else) prints unchanged.
- **Rationale:** preserves the `6d92c82d`/#744 postmortem fix's intent on the actual success path while eliminating the latent defect where an already-correctly-classified `stuck/transient` or `stuck/verify` report could be silently corrupted into `stuck/logic` by an unrelated corrective-SHA failure.
- **Applies to:** forward-output-stuck-passthrough (batch 3) only.

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/unit_tests/test-agent-mode-dispatch.py`
- `plugins/mill/unit_tests/test-bg-json-contract.py`
- `plugins/mill/unit_tests/test-claude-sub.py`
- `plugins/mill/unit_tests/test-millpy-claim.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
