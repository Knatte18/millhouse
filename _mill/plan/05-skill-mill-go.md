# Batch: skill-mill-go

```yaml
task: "Replace subprocess LLM dispatch with the Claude Code Agent tool"
batch: skill-mill-go
number: 5
cards: 2
verify: null
depends-on: [2, 3, 4]
```

## Batch Scope

Adds the agent-mode dispatch branch to `mill-go/SKILL.md` at all seven dispatch
points (per-batch implement; per-batch code review; per-batch NIT-fix and
REQUEST_CHANGES-fix; per-batch and holistic code-review ERROR retries; holistic
code review; holistic fixes; plus the resume paths). A single shared
"Agent-mode dispatch" sub-section defines the three-step flow once
(prepare CLI -> Agent tool -> finalize CLI); each dispatch point gains a short
"if dispatch == agent" branch that references it, leaving the existing
`millpy-bg` flow as the `subprocess`/`psmux` branch verbatim. Pure documentation
batch (SKILL.md is interpreted by the orchestrator, not unit-tested). Depends on
batches 2-4 so the referenced subagent types and `--stage` CLIs exist.

## Cards

### Card 20: Shared Agent-mode dispatch sub-section + Execute-phase branches

- **Context:**
  - `_mill/plan/00-overview.md`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/agents/mill-reviewer.md`
  - `plugins/mill/agents/mill-implementer.md`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new sub-section "## Agent-mode dispatch" near the top of
  the Execute phase that defines the reusable three-step flow exactly as the
  overview's "SKILL agent-mode three-step flow" Shared Decision: (1) resolve mode
  via `_agent_dispatch.resolve_dispatch_mode(cfg)` (only `agent` triggers this
  flow; provider must be Claude); (2) run `<cli> --stage prepare <same args>`,
  parse the one-line JSON for `brief_path`, `subagent_type`, `model`; (3) call the
  **Agent tool** synchronously with `subagent_type` and `model` from the prepare
  JSON and prompt `"Read this file and follow the instructions exactly: <brief_path>"`;
  (4) write the Agent's final message to `<brief_path>.out`; (5) run
  `<cli> --stage finalize <same args> --agent-output <brief_path>.out` and parse
  its JSON envelope; (6) branch on the envelope EXACTLY as the existing bg path.
  State that agent mode has no log-poll, no liveness check, and no
  `infrastructure` stuck path (no detached worker); the `transient` stuck path
  still applies via finalize's synthetic stuck JSON, handled by the existing
  one-retry policy. Then, at the per-batch Implement (lines ~162-165), per-batch
  Code Review (lines ~235-238), NIT-fix (lines ~252-254), REQUEST_CHANGES-fix
  (lines ~268-270), and both ERROR-retry blocks (lines ~287-290), wrap each
  existing `millpy-bg` invocation in an explicit "if dispatch is `subprocess`/
  `psmux`: <existing bg flow unchanged>; if dispatch is `agent`: follow
  ## Agent-mode dispatch with `<cli>` and `<args>`" branch. Do not alter the
  verdict-branch logic, the per-batch session-cleanup blocks, or the
  ERROR-two-pass caps -- they run identically once the envelope is in hand.
- **Commit:** `feat(mill-go): add agent-mode dispatch branch (execute phase)`

### Card 21: Holistic review + holistic fixes + resume-path branches

- **Context:**
  - `_mill/plan/00-overview.md`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Apply the same "if dispatch == agent: follow
  ## Agent-mode dispatch" branch (referencing the sub-section added in Card 20) to
  the holistic code-review dispatch (lines ~463-466), the holistic ERROR-retry
  (lines ~483-485), the holistic NIT-fix (line ~513) and holistic
  REQUEST_CHANGES-fix (line ~523), and the resume-path re-invocations
  (lines ~328-357: `running`/`reviewing`/`fixing` states). For the resume paths,
  state that in agent mode the SKILL re-runs the same prepare -> Agent -> finalize
  flow for the current on-disk state (the prepare-stage pre-commit makes this
  idempotent; the brief at `_mill/briefs/<role>-<scope>-rN.md` is reused/
  re-rendered). Keep the holistic session-cleanup blocks and rate-limit fallback
  (lines ~497-505) intact for the subprocess/psmux branch; note they are no-ops in
  agent mode (no psmux session, no detached worker). Do not change any
  verdict-branch behavior.
- **Commit:** `feat(mill-go): add agent-mode branch (holistic + resume)`

## Batch Tests

`verify: null` -- this batch edits only `mill-go/SKILL.md`, which is orchestration
documentation interpreted by the mill-go session, not runnable code with a unit
surface. Correctness is validated by inspection against the overview's Shared
Decisions and by the end-to-end parity test in batch 7 (which exercises the
`--stage prepare`/`finalize` CLIs the SKILL branch calls). The existing
`subprocess`/`psmux` flow text is preserved verbatim, so no regression to the
default path.
