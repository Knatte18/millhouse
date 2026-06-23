# Plan: Fix agent-dispatch cwd guard, implementer self-termination, and false-success contracts

```yaml
task: "Fix agent-dispatch cwd guard, implementer self-termination, and false-success contracts"
slug: mill-implementer-and-dispatch-quality
approved: true
started: "20260623-084125"
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
    name: hub-cwd-resolution
    file: 01-hub-cwd-resolution.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-paths.py test-millpy-implement.py"
  - number: 2
    name: implementer-finalize-contract
    file: 02-implementer-finalize-contract.md
    depends-on: [1]
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py"
  - number: 3
    name: implementer-model-tier
    file: 03-implementer-model-tier.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py"
  - number: 4
    name: workflow-memory-note
    file: 04-workflow-memory-note.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: cwd-independent hub resolution

- **Decision:** Stage CLIs (`millpy-implement.py`, `millpy-fix.py`, `millpy-review-code.py`) must anchor `project_root` on `_paths.resolve_hub_path()` (a cwd walk up to the `.millhouse/config.local.yaml` marker, stub-aware — it tolerates cwd being a subdir or the git-root-with-stub of a nested-hub repo) rather than on a raw `Path.cwd()` literal. (`resolve_hub_path()` does seed its walk from `Path.cwd()`; the point is it resolves to the same hub from any descendant, which a bare `Path.cwd()` does not.) When the resolved `_mill/status.md` is missing, emit a clear actionable error via the new `_paths.TaskHubError` / `_paths.require_status_path` helper — never let `_status.read_full` raise a raw `ValueError`.
- **Rationale:** Agent-dispatch invokes these CLIs directly, bypassing `millpy-bg`'s cwd guard; on nested-hub repos (hub is a git subdir) a git-root cwd crashed with an unguarded traceback (#514/#520).
- **Applies to:** hub-cwd-resolution (and consumed by implementer-finalize-contract via the same `millpy-implement.py` setup).

### Decision: success contracts are enforced mechanically, not by model self-policing

- **Decision:** An implementer report (self-reported OR inferred) may only resolve to `success` when (a) the number of content commits since `start_sha` is `>= card_count` for the batch, and (b) the in-scope working tree is clean per `_cleanliness.compute_terminal_dirt`. Otherwise demote to `stuck`. The brief is strengthened in parallel, but the gate is the backstop.
- **Rationale:** #521 (agent self-terminates mid-batch, no report) and #516 (success with dirty in-scope tree) both stem from trusting the model; verify-green gave no corrective signal.
- **Applies to:** implementer-finalize-contract.

### Decision: raw commit count, no filtering

- **Decision:** The completeness gate uses the raw `git rev-list --count <start_sha>..HEAD`, exactly as `millpy-implement.py` already does on `LLMError` (line ~295). No attempt to exclude the `mill-go: start batch` commit or formatter-drift commits.
- **Rationale:** `start_sha` predates the start-batch commit, so the raw count over-counts — and over-count can never falsely demote a complete batch. The `commits < cards` lower-bound is what matters; a filtering scheme would only add inconsistency risk.
- **Applies to:** implementer-finalize-contract.

### Decision: finalize dirty-tree check is read-only (reject, never revert)

- **Decision:** The finalize-path dirty check uses the **read-only** `_cleanliness.compute_terminal_dirt(worktree, task_dir, parent_branch)` and only demotes to stuck. Reverting out-of-scope drift remains mill-go's 2b cleanliness gate's sole responsibility. Resolve `parent_branch` via `_parent_branch.resolve(status_path, interactive=False)` (no operator attached at finalize).
- **Rationale:** Avoids surprising double-reverts; keeps the authoritative revert+block in one place.
- **Applies to:** implementer-finalize-contract.

### Decision: ASCII-only stdout, backward-compatible signatures

- **Decision:** All new `print`/error strings are ASCII (` -- `, ` -> `). New parameters on `_forward_output` / `finalize_from_output` are keyword-only with `None` defaults so existing callers and tests keep working.
- **Rationale:** Windows cp1252 stdout crashes on non-ASCII; existing unit tests call these helpers without the new kwargs.
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/skills/workflow/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-paths.py`
- `mill-config.yaml`
