# Plan: 'mill-go-base: take the subagent report from the SubagentHandback message'

```yaml
task: 'mill-go-base: take the subagent report from the SubagentHandback message'
slug: 'subagent-handback-report'
approved: true
started: '20260926-090746'
parent_branch: 'main'
root: ""
verify: null
discussion_sha: 'c6406a9d7fca5e0d288f7bcce656dc41ecdcd926'
```

## Batch Index

```yaml
batches:
  - number: 1
    name: agent-dispatch-core
    file: 01-agent-dispatch-core.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-mill-go-variants.py
  - number: 2
    name: sibling-skill-wording
    file: 02-sibling-skill-wording.md
    depends-on: [1]
    verify: null
  - number: 3
    name: script-wording
    file: 03-script-wording.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-finalize.py
  - number: 4
    name: test-comments
    file: 04-test-comments.md
    depends-on: [3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-review-finalize.py
```

## Shared Decisions

### Decision: report-source-and-event-order

- **Decision:** The subagent report is the text of the SubagentHandback message; the task-notification payload is a fallback report source only.
  The hand-back message arrives before the notification in every observed run, and the orchestrator proceeds on it without waiting for the notification.
  A later notification is acted on only when its status tag is not completed.
  A completed notification whose result only points at a hand-back message, with no hand-back message in context, falls through immediately to step 3's existing empty/no-structured-report handling.
  A hand-back message with no structured status block (implementer) gets the same handling.
- **Rationale:** matches the harness behaviour reported in three GitHub issues and keeps the status tag as the only carrier of failed/stopped/interrupted signals.
- **Applies to:** all batches

### Decision: liveness-probe-wait-wording

- **Decision:** Every place that says to wait for "the agent's own next task-notification" after a probe reports the agent still running becomes "the next terminal event for that agentId (a hand-back message or a task-notification)".
  The probe mechanism itself is unchanged.
- **Rationale:** the next terminal event can be either, so naming only the notification recreates the bug.
- **Applies to:** agent-dispatch-core

### Decision: code-changes-are-wording-only

- **Decision:** No logic change in any Python file.
  The html.unescape calls at the finalize read sites stay; only error-message text and comments are reworded.
  The residual risk that a hand-back report quoting a literal entity is altered is accepted (only the machine-read status JSON block drives behaviour).
- **Rationale:** the unescape is still needed for the notification fallback path.
- **Applies to:** script-wording, test-comments

### Decision: verification-is-grep-plus-existing-tests

- **Decision:** No new unit test.
  Skill prose is verified by grep for remaining notification mentions; Python batches run the existing tests that cover the touched modules.
- **Rationale:** discussion decision; no existing test pins this SKILL prose.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/docs/harness-tool-contracts.md`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go-base/holistic-review.md`
- `plugins/mill/skills/mill-pause/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-review-finalize.py`
