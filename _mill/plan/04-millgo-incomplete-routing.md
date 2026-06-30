# Batch: millgo-incomplete-routing

```yaml
task: "Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode"
batch: "millgo-incomplete-routing"
number: 4
cards: 1
verify: null
depends-on: [1, 2]
```

## Batch Scope

This batch documents the orchestration of `stuck_type: incomplete` in the mill-go SKILL: how the orchestrator recovers a partial-batch stop. It depends on batch 1 (the `incomplete` envelope must exist) and batch 2 (the `--resume-incomplete` path and the `<START_SHA>` brief mechanics it references). It is a documentation-only change to one markdown SKILL file; no code and no verify.

## Cards

### Card 11: Document `incomplete` routing and agent-ID retention in mill-go

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Edit `mill-go/SKILL.md`'s `## Agent-mode dispatch` (including the "Clean mid-work stop (implementer only)" block at ~line 129) and `### Stuck escalation` sections to add `stuck_type: incomplete` handling: (a) In step 3 (the Agent-tool call, ~lines 118-123): record the `agentId` the Agent tool returns at dispatch and retain it for the duration of the batch (today's text treats dispatch as fire-and-forget); state that this `agentId` is the harness runtime handle, distinct from the brief `session_id`/`implementer_session`. (a2) **Rewrite the "Clean mid-work stop (implementer only)" block (~line 129):** today it states finalize emits `stuck_type: transient` with `commits_made` and routes `commits_made > 0` to the Stuck-escalation skip-to-cleanliness path. After Batch 1, a partial clean stop yields `stuck_type: incomplete` on this exact path. Update the block so a clean mid-work stop runs `--stage finalize` and, when finalize returns `stuck_type: incomplete`, routes to the warm-`SendMessage` / `--resume-incomplete` recovery defined below — NOT transient skip-to-cleanliness (which would accept the partial batch as done, the #574 bug). Keep the transient handling for genuine raw-API-error/interruption stops unchanged. (b) Add an `incomplete` recovery: in agent mode, on `stuck_type: incomplete`, `SendMessage(to: <agentId>, "Finish any remaining cards in this batch, run verify, then emit the required JSON report as your final line.")`, capture the resulting notification to `.out.md`, and re-run `--stage finalize`. The warm-`SendMessage` path bypasses prepare so status.md's original `start_sha` is preserved. (c) Fallback: when no `agentId` is retained, the `SendMessage` call errors because the agent already terminated (the stop was `status: completed`), or the resumed agent again stops without JSON — fall back to a re-dispatch via the new `--resume-incomplete` path (preserves the original `start_sha`; never a fresh `start_sha`). (d) In subprocess/psmux mode, route `incomplete` to a one-time `--resume-incomplete` re-dispatch — NOT the `commits_made > 0` skip-to-cleanliness branch and NOT today's running-state re-fire (which re-captures `start_sha`). (e) In `### Stuck escalation`, add an `incomplete` branch consistent with the above: interactive mode resumes once then escalates; `autonomous_mode: true` auto-resumes once and, if still `incomplete`, sets batch state blocked with `blocked_reason: "incomplete after resume"`. Keep wording consistent with the existing section style; reference the discussion decisions by name where helpful (`warm-resume-mechanism`, `start-sha-preserving-resume`).
- **Commit:** `docs(mill-go): document incomplete stuck_type routing and resume`

## Batch Tests

`verify: null` — the only edited file is `mill-go/SKILL.md`, a markdown skill document with no runnable surface. Correctness is validated by plan/code review reading the routing prose for consistency with the `incomplete` envelope (batch 1) and the `--resume-incomplete` path (batch 2). No code path executes this text directly.
