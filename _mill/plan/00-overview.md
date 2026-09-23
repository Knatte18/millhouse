# Plan: Monitor tool: persistent:true still referenced in mill-go-base and mill-plan despite no such param

```yaml
task: 'Monitor tool: persistent:true still referenced in mill-go-base and mill-plan despite no such param'
slug: monitor-persistent-true-still-referenced
approved: true
started: '20260923-102007'
parent: main
root: ""
verify: null
discussion_sha: '8550c4e27acc56afbe922c422f80c8cd89cf01b9'
```

## Batch Index

```yaml
batches:
  - number: 1
    name: fix-monitor-persistent-refs
    file: 01-fix-monitor-persistent-refs.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: replace `persistent: true` with a fixed `timeout_ms: 1800000`

- **Decision:** Every `Monitor(...)` call this plan touches — initial call and every re-arm, in both entry-gate wait sections — passes `timeout_ms: 1800000` explicitly instead of `persistent: true`. Always the same constant, never a dynamically computed value.
- **Rationale:** `1800000` is the tool's effective cap (its own description states deadlines above that are capped down to it), so it minimizes re-arm frequency. The rebuilt poll script's own internal `remaining_s` timeout already enforces the real give-up point on the tail of a wait, so `Monitor`'s `timeout_ms` never needs separate arithmetic.
- **Applies to:** all batches (batch `fix-monitor-persistent-refs`).

### Decision: reframe the re-arm branch as the normal path, not an edge case

- **Decision:** The "any other notification content" branch in both entry-gate wait sections, and the matching bullet in `harness-tool-contracts.md`, is documented as the expected, normal outcome for any wait exceeding 1800 seconds — not an "unexpected"/build-specific early expiry. The branch's mechanics (recompute `remaining_s`, halt-or-rebuild) are unchanged; only the framing changes.
- **Rationale:** The old framing assumed `persistent: true` normally holds a wait open, making any expiry a build anomaly. That assumption is false — no `Monitor` build has ever had a `persistent` parameter — so the anomaly framing is dropped to avoid perpetuating it.
- **Applies to:** all batches (batch `fix-monitor-persistent-refs`).

### Decision: leave `pipeline.done_gate` untouched

- **Decision:** This plan does not set or change `pipeline.done_gate` in `mill-config.yaml`.
- **Rationale:** This batch edits three markdown files with no runnable code surface — there is no code regression a repo-wide test or lint gate could catch for this change. `pipeline.done_gate` is a hub-wide setting unrelated to this task's scope; changing it here would be an unrelated cross-cutting edit requiring its own justification, not a byproduct of this fix.
- **Applies to:** all batches (batch `fix-monitor-persistent-refs`).

## All Files Touched

- `plugins/mill/docs/harness-tool-contracts.md`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
