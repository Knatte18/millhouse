# Plan: mill-go's one-shot pre-batch-1 baseline can't cover a task's own later per-batch-baseline capability

```yaml
task: mill-go's one-shot pre-batch-1 baseline can't cover a task's own later per-batch-baseline capability
slug: mill-go-per-batch-baseline-preflight-gap
approved: false
started: 20260805-181448
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
    name: self-hosting-detection-helper
    file: 01-self-hosting-detection-helper.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-paths.py
  - number: 2
    name: per-batch-baseline-recapture-hook
    file: 02-per-batch-baseline-recapture-hook.md
    depends-on: [1]
    verify: null
```

## Shared Decisions

_Cross-cutting decisions every batch inherits. Batch-local decisions live in each batch file._

### Decision: cache-vs-worktree execution path for the retry

- **Decision:** The batch-2 recapture invocation runs the task worktree's own copy of `millpy-implement.py` via `PYTHONPATH="<git_root>/plugins/mill/scripts"`, never `${CLAUDE_PLUGIN_ROOT}`.
- **Rationale:** `${CLAUDE_PLUGIN_ROOT}` is frozen for the whole mill-go run and never reflects this self-hosting task's own in-progress commits. Re-invoking the cache copy later in the run is provably a no-op. See `_mill/discussion.md`'s "cache-vs-worktree execution path for the retry" Decision and root `CLAUDE.md`'s "Hard constraints" / "Path invariants" sections for the precedent this narrowly departs from.
- **Applies to:** batch 2 (per-batch-baseline-recapture-hook)

### Decision: self-hosting gate, no new config key

- **Decision:** The recapture is gated entirely on the new `_paths.is_self_hosting_task(git_root)` helper (batch 1). No `mill-config.yaml` / `config.local.yaml` key is added.
- **Rationale:** For any non-millhouse target repo, `plugins/mill/scripts/` is never part of that repo's own tree, so the existence check is a clean, silent, always-correct skip. See `_mill/discussion.md`'s "self-hosting gate" Decision (cites `0467ba27` on the maintenance cost of unnecessary config keys).
- **Applies to:** all batches

### Decision: retry trigger condition

- **Decision:** The recapture fires only when, at its dispatch-mode-specific hook point, the batch's own `verify_baseline_failures` is still unset in status.md **and** the batch's own resolved `verify:` command is non-`None`.
- **Rationale:** `_enumerate_batch_verify_triples` (`plugins/mill/scripts/millpy-implement.py`) permanently skips any batch whose `verify:` resolves to `None`, so such a batch's baseline field stays unset forever regardless of retries — without the non-`None` half of the condition, a no-verify batch reaching its hook point first would consume the single once-per-run attempt on a batch that could never benefit. See `_mill/discussion.md`'s "retry trigger condition (no file-diff detection)" Decision.
- **Applies to:** batch 2 (per-batch-baseline-recapture-hook)

### Decision: retry cadence — once per session, in-memory only

- **Decision:** The recapture attempts at most once per mill-go session, tracked by a local Builder variable (never written to status.md), initialized before "## Execute — sequential loop" begins.
- **Rationale:** The recapture does a full parent-branch checkout; a persistent failure shouldn't repeat that cost on every subsequent batch's finalize. A mill-go restart resets the flag — an accepted, harmless limitation (a second attempt is idempotent if a baseline already exists, or a fresh useful attempt otherwise). See `_mill/discussion.md`'s "retry cadence — once per task run" Decision.
- **Applies to:** batch 2 (per-batch-baseline-recapture-hook)

### Decision: failure handling is always non-blocking

- **Decision:** Any failure of the recapture invocation itself (non-zero exit, timeout, malformed/missing JSON, `--stage baseline` not yet supported by the in-development worktree code) is logged (ASCII-only) and the batch loop proceeds to that batch's normal strict-mode finalize exactly as if no recapture had been attempted. It never blocks or marks the task `stuck`.
- **Rationale:** Matches `_run_baseline_stage`'s own "never raises, never blocks" contract. See `_mill/discussion.md`'s "failure handling" Decision.
- **Applies to:** batch 2 (per-batch-baseline-recapture-hook)

### Decision: hook placement is dispatch-mode-specific, not one shared call point

- **Decision:** One shared check-and-invoke block (new `### 0.6.` subsection), referenced from two different insertion points in `### 1. Implement`: locally within the Agent-mode dispatch instance, immediately before that instance's step-6 `--stage finalize` call; and immediately before the backgrounded `millpy-implement.py <batch_name>` dispatch in the subprocess/psmux branch (which has no separate finalize call to insert before).
- **Rationale:** `--stage full` (subprocess/psmux) runs implement-then-finalize inside one synchronous process with no external call boundary, so "before finalize" is not a meaningful insertion point there. The two insertion points share one block's logic rather than duplicating it. This means the two modes are NOT functionally equivalent — under subprocess/psmux the recapture can only ever see prior batches' commits, never the current batch's own in-flight changes, because its hook necessarily runs before that batch's implementer starts. This asymmetry is an accepted limitation, not a gap to close in this task (closing it would require moving the retry logic into `millpy-implement.py` itself and persisting the cadence flag to status.md — deferred). See `_mill/discussion.md`'s "hook placement" Decision for the full accepted-limitation writeup.
- **Applies to:** batch 2 (per-batch-baseline-recapture-hook)

## All Files Touched

- `plugins/mill/scripts/_paths.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/unit_tests/test-paths.py`
