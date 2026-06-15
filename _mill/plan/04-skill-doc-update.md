# Batch: skill-doc-update

```yaml
task: Fix millpy-review-plan validator gaps and resolve_ref_paths path-doubling
batch: skill-doc-update
number: 4
cards: 1
verify: null
depends-on: [3]
```

## Batch Scope

Documents the new `--stage prepare` validator-gate behaviour (batch 3) in the mill-plan SKILL so the agent-mode orchestrator branches correctly on the prepare envelope. Pure documentation batch: no runnable surface, so `verify: null`. Depends on batch 3 because the prepare-failure envelope it describes only exists after batch 3 ships. The SKILL.md:133 "runs unchanged in BOTH modes" claim — false before this task — becomes accurate once the gate runs in prepare; this card keeps it and adds the missing envelope-handling instruction.

## Cards

### Card 9: document prepare-stage validator gate in agent mode

- **Context:**
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-plan/SKILL.md` Phase: Plan Review, update the agent-mode dispatch handling so the orchestrator branches on the `--stage prepare` envelope: when the prepare JSON contains an `errors` key (validator failure), route into the existing Step 1.5 mechanical-fix loop (apply one mechanical fix per error dict per the fix table, commit with the `validator-fix` message, re-run `--stage prepare`), honoring the two-pass cap; when it contains `stage: "prepare"` / `brief_path` (success), proceed with the Agent -> finalize flow as today. State explicitly that the discriminator is the PRESENCE OF THE `errors` KEY, not the exit code alone. Keep the existing "Pre-review validator gate" note (SKILL.md:133) that the validator "runs unchanged in BOTH modes" — it is now accurate. Do NOT modify SKILL.md:104 ("The CLI auto-runs `_plan_validate` before invoking the LLM"); it stays correct as-is. Make the edit consistent with the existing Step 1.5 wording so the JSON parser + fix table description remain the single source of fix semantics (reference Step 1.5 rather than duplicating the fix table).
- **Commit:** `docs(mill-plan): document prepare-stage validator gate in agent mode`

## Batch Tests

No runnable surface — this batch edits a SKILL.md only, so `verify: null`. Correctness is checked by the plan reviewer confirming the agent-mode branch now describes the prepare-envelope discriminator and that lines 104/133 are handled per the discussion's "SKILL edit scope" note.
