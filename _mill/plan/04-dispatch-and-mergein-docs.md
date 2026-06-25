# Batch: dispatch-and-mergein-docs

```yaml
task: Fix spawn lifecycle integrity, agent-mode async assumption, merge-in conflicts, and pre-existing failure validation
batch: dispatch-and-mergein-docs
number: 4
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-merge-in-subagent.py
depends-on: []
```

## Batch Scope

Delivers the two documentation/prompt-integrity fixes: #537 rewrites mill-go's
"Agent-mode dispatch" pattern to reflect the harness's actual asynchronous Agent
launch (and reconciles the inheritor SKILLs), and #540 sharpens the merge-in
conflict brief to combine non-overlapping intra-hunk edits and adds a
discarded-content reporting path the operator sees. Concentrated in the four
dispatch SKILLs, the `merge-in-conflict-brief.md` template, and
`millpy-merge-in-subagent.py`. Independent of all other batches (no shared files).

Batch-local decision: #537 and the brief changes are prose; the only runnable
surface is #540's `discarded`-field preservation in `millpy-merge-in-subagent.py`,
which is what `verify:` exercises. The SKILL prose is verified by the code-review
gate.

## Cards

### Card 13: Rewrite mill-go Agent-mode dispatch for async
- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Rewrite the "## Agent-mode dispatch" section. Step 3: the Agent tool launches a BACKGROUND subagent and returns immediately ("Async agent launched..."); the orchestrator must wait for that agent's completion `<task-notification>` and read the subagent's final message from the notification (not from the tool's return value). Step 5: write the message captured from the notification to `<brief_path>.out.md`. "Agent-mode properties": correct the assertions "the Agent tool is synchronous" and "No detached worker" — a background agent IS a detached worker that can be stopped/interrupted; document re-dispatch of a stopped/interrupted background agent via the existing `transient` one-retry path (step 4). Preserve the semantics of steps 1, 2, 4, 6, 7 (prepare envelope, raw-API-error recovery, finalize, verdict branching) — only the synchronous-capture assumptions change. Documentation edit only.
- **Commit:** `docs(mill-go): document asynchronous Agent-mode dispatch (#537)`

### Card 14: Reconcile inheritor SKILLs to async dispatch
- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the three SKILLs that reference "follow the Agent-mode dispatch pattern" (mill-plan, mill-start, mill-merge-in), ensure no local wording re-asserts synchronous Agent return or an inline "the Agent returns its final message text" capture. Where such wording exists, update it to delegate to mill-go's corrected async section (result arrives via task-notification). Do not duplicate the full async procedure — point to mill-go's "## Agent-mode dispatch" as the single source of truth. Documentation edit only.
- **Commit:** `docs(dispatch): reconcile inheritor SKILLs to async Agent dispatch (#537)`

### Card 15: Sharpen merge-in conflict combine + add discarded schema
- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/templates/merge-in-conflict-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `merge-in-conflict-brief.md`, sharpen the existing step-3 instruction ("Write a resolution that preserves the intent of both sides") with a concrete worked example: when both sides modify different, NON-OVERLAPPING parts of the same conflict region (e.g. different columns of one table row, different keys of one object), COMBINE both edits into a single resolved line/structure; picking one side wholesale is correct only when the two sides are genuinely mutually exclusive. Extend the `## Report` success schema with an optional `discarded` (array of short strings) field: if the resolver must drop any content from one side, it MUST list what was dropped (`{"status":"success","discarded":["..."]}`); an empty/absent `discarded` means nothing was lost. Documentation edit only.
- **Commit:** `docs(merge-in): combine non-overlapping conflict edits and report discards (#540)`

### Card 16: Preserve the `discarded` field through forwarding
- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Ensure the optional `discarded` field emitted by the conflict sub-agent's success JSON survives the verdict forwarding in `_run_conflicts` (`_forward_output` / `finalize_from_output`) and appears in the JSON envelope printed on stdout, so the `mill-merge-in` frontend can read it. If the forwarding path reshapes the verdict to a fixed schema and would drop unknown keys, thread `discarded` through explicitly. Note: the conflicts-mode success path in `_forward_output` already prints the whole parsed dict verbatim (`print(json.dumps(parsed))` around `_implementer_common.py:632`), so `discarded` very likely survives WITHOUT any threading change — do NOT invent a needless reshape. The load-bearing deliverable is the regression TEST that pins the contract. Add a test in `test-millpy-merge-in-subagent.py` asserting a success verdict carrying `discarded: ["..."]` is preserved (non-empty) in the emitted envelope, and that a verdict without it still emits clean success.
- **Commit:** `feat(merge-in): preserve discarded-content field in conflict verdict (#540)`

### Card 17: Surface discarded content to the operator
- **Context:**
  - `plugins/mill/templates/merge-in-conflict-brief.md`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-merge-in/SKILL.md` Step 3 ("Merge parent into current", the conflict-resolution dispatch), on `{"status":"success"}` read the optional `discarded` field from the sub-agent's JSON envelope; if it is non-empty, surface the dropped content to the operator (report what was discarded and recommend a manual diff against the parent) instead of silently running `git merge --continue`. An empty/absent `discarded` keeps the existing silent-continue behavior. Documentation edit only.
- **Commit:** `docs(merge-in): surface discarded conflict content to operator (#540)`

## Batch Tests

`verify:` runs `test-millpy-merge-in-subagent.py`, exercising the only runnable surface in
this batch — the `discarded`-field preservation through the conflict verdict forwarding
(card 16). Cards 13, 14, 15, and 17 are SKILL/template documentation edits with no runnable
surface; they are verified by the code-review gate and leave `verify:` green. Scope is the
merge-in CLI only — focused `--only` is correct.
