# Plan: Add mill-quick: skip-review pipeline for simple tasks

```yaml
task: 'Add mill-quick: skip-review pipeline for simple tasks'
slug: mill-quick
approved: false
started: '20260801-090725'
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: mill-quick-skill
    file: 01-mill-quick-skill.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: no new Python script code

- **Decision:** `mill-quick` is authored entirely as `SKILL.md` prose (orchestration steps the invoking Claude session runs directly), reusing existing, already-unit-tested helper modules verbatim: `_paths.py`, `_config.py`, `_marker.py`, `_status.py`, `_builder_lock.py` (via `millpy-builder-lock.py`), `_done_gate.py` (`run_preflight`), `wiki/_client.py` (`get_task`, `set_phase`). No new `.py` file is created.
- **Rationale:** `_mill/discussion.md`'s `single-inline-agent` Decision establishes that `mill-quick` is "a linear script the orchestrating session runs top to bottom" with no dispatch machinery — this is the same shape as `mill-start`/`mill-plan`/`mill-abandon`/`mill-pause`/`mill-resume`, none of which have a dedicated backend script. Every helper `mill-quick` needs already exists with the exact signature needed (verified by reading each module directly): `_status.append_phase(status_path, phase, timestamp)`, `_status.set_blocked(status_path, reason, *, timestamp)`, `_status.read(status_path) -> dict`, `_builder_lock.acquire`/`release` (via the `millpy-builder-lock.py acquire <slug>` / `release` CLI, exit 1 on `LockBusy`), `_marker.slug_from_branch(git_root, wiki_path, cfg) -> str`, `_paths.resolve_git_root()` / `resolve_wiki_path(git_toplevel)` / `resolve_hub_path(cwd=None)` / `resolve_task_path(worktree_root, cfg_relative_path)`, `_done_gate.run_preflight(gate_cmd, git_root) -> dict` (returns `{"result": "ok"}` / `{"result": "blocked", "reason": ...}` / `{"result": "skipped", ...}`, never raises), `wiki._client.get_task(wiki_path, id_or_slug) -> dict | None`, `wiki._client.set_phase(wiki_path, id_or_slug, phase)`.
- **Applies to:** all batches (there is only one).

### Decision: reuse `_done_gate.run_preflight` for the verify step

- **Decision:** `mill-quick`'s verify step calls `_done_gate.run_preflight(gate_cmd, git_root)` — the exact helper `mill-go`'s "0.55. Done-gate baseline pre-flight" step already uses — rather than hand-rolling a new `subprocess.run` call.
- **Rationale:** `run_preflight` already implements the exact subprocess-construction / stdout+stderr-concatenation / 2000-char-tail-truncation shape `_mill/discussion.md`'s Technical Context says `mill-quick` must mirror from `mill-go`'s Pre-done gate, and it is already covered by `plugins/mill/unit_tests/test-done-gate.py`. Reusing it means `mill-quick` adds zero new subprocess-invocation code and inherits existing test coverage for the success/blocked paths for free. `mill-quick`'s own null-handling still diverges from `mill-go`'s (per discussion): `mill-quick` never calls `run_preflight` with a `None` `gate_cmd` at all, because Entry step 2 (see batch 01, Card 1) hard-halts before any edit when `pipeline.done_gate` is unset — `run_preflight`'s own `"skipped"` branch (used by `mill-go` for its skip-on-null behavior) is therefore dead code on `mill-quick`'s call path, reached only defensively.
- **Applies to:** batch 01 (the only batch).

### Decision: no dedicated unit/integration test file for `mill-quick`

- **Decision:** This plan adds no new test file (`unit_tests/test-mill-quick*.py` or `integration_tests/test-mill-quick*.py`).
- **Rationale:** Per the "no new Python script code" decision above, `mill-quick` introduces zero new functions to unit-test — every helper it calls already has dedicated coverage (`test-status.py`, `test-builder-lock.py`, `test-marker.py`, `test-paths.py`, `test-done-gate.py`). The entry-phase-gate and `done_gate`-null-precondition logic `_mill/discussion.md`'s Testing section names as "TDD candidates" are orchestration prose executed by the invoking Claude session itself, not Python functions — there is no function boundary to attach a unit test to. This matches the existing precedent of every other prose-only mill skill (`mill-start`, `mill-abandon`, `mill-pause`, `mill-resume`, `mill-resume`) — verified by `grep -rl` across `unit_tests/` and `integration_tests/`: none of those skill names appear, confirming no mill skill's own `SKILL.md` orchestration flow (as opposed to the backend scripts it calls) carries a dedicated test file in this codebase. A true end-to-end exercise of the `SKILL.md` flow would require actually running a Claude session through it, which is not automatable as a deterministic test; validation happens the same way it does for `mill-start`/`mill-plan`/`mill-go`'s own prose — first real-world invocation.
- **Applies to:** batch 01 (the only batch).

### Decision: no mill-status / mill-cleanup / mill-spawn changes

- **Decision:** No file under `mill-status/`, `mill-cleanup/`, or `mill-spawn/` is touched.
- **Rationale:** Verified directly: `mill-status/SKILL.md`'s phase-reference table already maps `[active]` + any of `discussing`/`discussed`/`planning`/`planned`/`implementing`/`reviewing`/`fixing`/`blocked` to "continue work" (covers `mill-quick`'s intermediate `implementing` and `blocked` states), and `[ready-to-merge]` + `done` to "run `/mill-merge`" (covers `mill-quick`'s success terminal state — identical to what `mill-go`'s own Handoff already produces). `mill-cleanup/SKILL.md`'s states-handled table has the matching `[ready-to-merge]` + `done` row ("Skip — waiting on mill-merge"). Every state `mill-quick` can leave a task in is therefore already correctly recognized by both skills with zero changes. `mill-spawn` is not touched either — `_mill/discussion.md`'s eligibility decision is "pure operator trust... matching mill-start's existing precedent of not second-guessing why the operator started a task a particular way," so `mill-quick` needs no announcement or discoverability hook at spawn time; the operator invokes `/mill-quick` in place of `/mill-start` by their own choice.
- **Applies to:** all batches (there is only one).

## All Files Touched

- `SKILLS.md`
- `plugins/mill/skills/mill-quick/SKILL.md`
