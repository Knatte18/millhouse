# Batch: skill-others

```yaml
task: "Replace subprocess LLM dispatch with the Claude Code Agent tool"
batch: skill-others
number: 6
cards: 3
verify: null
depends-on: [2, 3, 4]
```

## Batch Scope

Adds the agent-mode dispatch branch to the remaining three SKILLs:
`mill-start/SKILL.md` (discussion review, 2 dispatch points), `mill-plan/SKILL.md`
(plan review), and `mill-merge-in/SKILL.md` (merge-in sub-agent, conflicts +
verify-fix). Each reuses the same three-step flow defined in the overview's
Shared Decisions and mirrored in mill-go's "## Agent-mode dispatch" sub-section.
Pure documentation batch. Depends on batches 2-4 (subagent types + `--stage`
review/merge CLIs).

## Cards

### Card 22: mill-start agent-mode branch (discussion review)

- **Context:**
  - `_mill/plan/00-overview.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** At the Discussion Review dispatch (lines ~129-131) and the
  ERROR-only retry (lines ~149-151), wrap the existing `millpy-bg ->
  millpy-review-discussion.py` invocation in a dispatch-mode branch: `subprocess`/
  `psmux` keeps the existing bg flow verbatim; `agent` follows the three-step flow
  (prepare -> Agent tool with `subagent_type: mill-reviewer` and the prepare
  JSON's model -> finalize), reusing the same wording as mill-go's
  "## Agent-mode dispatch" (reference it; do not duplicate the full prose). State
  that in agent mode the dead-worker/`infrastructure` halt at line ~138 does not
  apply (no detached worker), but mill-start remains interactive and the
  GAPS_FOUND / APPROVE-with-NOTE branches (steps 4a/4b/5) are unchanged once the
  envelope is in hand. Preserve `--auto` mode behavior (it only changes
  gap/NOTE handling, not dispatch). Keep the existing `--slug` argument usage.
- **Commit:** `feat(mill-start): add agent-mode discussion-review branch`

### Card 23: mill-plan agent-mode branch (plan review)

- **Context:**
  - `_mill/plan/00-overview.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** At the plan-review dispatch (step 2, lines ~136-138) and the
  ERROR-only retry (step 4.5, lines ~160-162), add the dispatch-mode branch:
  `subprocess`/`psmux` unchanged; `agent` follows the three-step flow with
  `subagent_type: mill-reviewer`. Because plan batch review is disabled in this
  hub (`roles.plan-review.batch.reviewer: null`), the agent-mode branch targets
  the holistic scope (pass `--holistic-only` to `--stage prepare`/`finalize`);
  note that if per-batch plan review is ever enabled, the SKILL loops the
  three-step flow once per enabled scope. The pre-review validator gate (step 1.5)
  runs unchanged in BOTH modes -- it is a Python-only `_plan_validate` check that
  never dispatches an LLM, so it is independent of dispatch mode. Verdict branches
  4a-4d, the non-progress check, and the max-rounds escape are unchanged once the
  envelope is in hand.
- **Commit:** `feat(mill-plan): add agent-mode plan-review branch`

### Card 24: mill-merge-in agent-mode branch (conflicts + verify-fix)

- **Context:**
  - `_mill/plan/00-overview.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** At both merge-in-subagent dispatch points (conflicts mode,
  line ~48; verify-fix mode, line ~62), add the dispatch-mode branch:
  `subprocess`/`psmux` unchanged; `agent` follows the three-step flow with
  `subagent_type: mill-implementer` (merge work is mutating). Handle the
  verify-fix `dispatch_needed:false` case from Card 12: when `--stage prepare`
  reports `dispatch_needed:false` (verify already passed), the SKILL skips the
  Agent tool and the finalize call and uses the embedded success envelope
  directly. Keep the JSON-verdict handling (success/stuck) unchanged. mill-merge
  itself dispatches nothing directly (it calls the mill-merge-in skill), so no
  edit to `mill-merge/SKILL.md` is needed.
- **Commit:** `feat(mill-merge-in): add agent-mode merge-subagent branch`

## Batch Tests

`verify: null` -- this batch edits only SKILL.md orchestration docs (mill-start,
mill-plan, mill-merge-in), which have no runnable unit surface. The
`subprocess`/`psmux` flow text is preserved verbatim, and the agent-mode branches
reference the same `--stage` CLIs exercised by batch 7's parity test. Correctness
is by inspection against the overview Shared Decisions.
