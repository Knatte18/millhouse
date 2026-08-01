# Plan: Non-interactive pipeline: only mill-start's interview may prompt the operator

```yaml
task: 'Non-interactive pipeline: only mill-start''s interview may prompt the operator'
slug: pipeline-walkaway-mode
approved: false
started: '2026-08-01T15:51:41Z'
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: mill-plan-autonomous-collapse
    file: 01-mill-plan-autonomous-collapse.md
    depends-on: []
    verify: null
  - number: 2
    name: mill-go-stuck-escalation
    file: 02-mill-go-stuck-escalation.md
    depends-on: []
    verify: null
  - number: 3
    name: mill-go-holistic-review
    file: 03-mill-go-holistic-review.md
    depends-on: [2]
    verify: null
  - number: 4
    name: mill-go-handoff-gates
    file: 04-mill-go-handoff-gates.md
    depends-on: [3]
    verify: null
  - number: 5
    name: mill-merge-self-resolve
    file: 05-mill-merge-self-resolve.md
    depends-on: []
    verify: null
  - number: 6
    name: cleanup-dead-autonomous-mode
    file: 06-cleanup-dead-autonomous-mode.md
    depends-on: [1, 2, 3, 4]
    verify: null
```

## Shared Decisions

### Decision: unconditional-default-not-a-flag

- **Decision:** Self-resolving/always-halting behavior is the *only* behavior for mill-plan and mill-go after this task — there is no flag, no config key, and no distinction between an "interactive" and an "autonomous" session for these two skills. Every edit in batches 1-4 removes an `if pipeline.autonomous_mode: true` (or equivalent) gate and keeps only the body that gate used to guard, rather than adding any new gate.
- **Rationale:** See `_mill/discussion.md` Decision `unconditional-default-not-a-flag`. `_autonomous.py` is dead code with zero callers; `pipeline.autonomous_mode` is the live mechanism being made unconditional and then deleted (batch 6).
- **Applies to:** all batches.

### Decision: self-resolve-then-escalate-on-repeat

- **Decision:** A site with no existing autonomous-mode branch gets ONE self-resolve attempt (retry, plan edit + retry, commit, or classify-and-clean, depending on the site) using the agent's own judgment — never a numbered prompt to the operator. If the *same* failure recurs after that one attempt, escalate to a genuine halt (`_status.set_blocked` or the gate's existing `BLOCKED:` message), matching the existing one-retry shape already used elsewhere (e.g. `transient`/`infrastructure`).
- **Rationale:** See `_mill/discussion.md` Decision `self-resolve-then-escalate-on-repeat`. This is not "build a menu and auto-pick the Recommended option" — no numbered-options prompt is built at all for these sites.
- **Applies to:** mill-go-stuck-escalation, mill-go-holistic-review, mill-go-handoff-gates.

### Decision: no-new-permission-prompting-tool-calls

- **Decision:** Any new or rewritten self-resolve logic sticks to non-interactive, non-permission-prompting tool calls (`git`, `Read`/`Edit`/`Write`, `Grep`/`Glob`, non-interactive Bash) — never `sed` or any other command that triggers a Claude Code permission prompt.
- **Rationale:** `sed` is banned project-wide (`CLAUDE.md`, commit `64adbbf6`); a permission prompt is the same "pipeline stops and waits" failure this task exists to eliminate, just triggered by the harness instead of a question.
- **Applies to:** all batches.

### Decision: audit-trail-via-status-timeline

- **Decision:** Every self-resolve action appends a `_status.append_phase(status_path, "<short-reason>", timestamp)`-style row to `status.md`'s existing timeline — no new dedicated field or section.
- **Rationale:** Reuses the mechanism every other phase transition already uses; the operator reviews auto-decisions the same way they review everything else.
- **Applies to:** mill-go-stuck-escalation, mill-go-holistic-review, mill-go-handoff-gates, mill-merge-self-resolve.

## All Files Touched

- `plugins/mill/skills/mill-autofix/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/_test_cfg.py`
- `plugins/mill/unit_tests/test-config.py`
