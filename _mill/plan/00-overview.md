# Plan: Entry-gate wait: drop nonexistent Monitor persistent:true

```yaml
task: 'Entry-gate wait: drop nonexistent Monitor persistent:true'
slug: 'monitor-persistent-entry-wait'
approved: false
discussion_sha: '115b7c097bc755266a68b307fa9c833101034c9d'
started: '20260924-060354'
parent: 'main'
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: orch-wait-monitor-rearm
    file: 01-orch-wait-monitor-rearm.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-orch-review-mill-path.py
```

## Shared Decisions

### Decision: reference-dont-duplicate

- **Decision:** The two orch skills point at `mill-go-base/SKILL.md`'s "Entry-gate wait for upstream mill-plan" section for the branch-on-`<event>` and re-arm rule and state only what differs: the file-exists poll script and, for `orch-review`, per-slug `wait_started_epoch`/`task_id`.
- **Rationale:** One canonical write-up; a third and fourth full copy would drift.
- **Applies to:** all batches

### Decision: inline-file-exists-poll

- **Decision:** The poll is an inline bash loop echoing `READY` or `TIMEOUT after <N>s ...` on stdout, so the event vocabulary matches the phase-poll waits.
  `_phase_wait.py` is not touched.
- **Rationale:** Docs-only defect; `build_wait_command` only polls `status.md` phases.
- **Applies to:** all batches

### Decision: done-gate-left-null

- **Decision:** `pipeline.done_gate` stays `null` and no config file is edited.
- **Rationale:** The change is markdown-only; batch verify covers the one test that reads the edited skills.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/docs/harness-tool-contracts.md`
- `plugins/mill/skills/orch-review/SKILL.md`
- `plugins/mill/skills/orch-wait/SKILL.md`
