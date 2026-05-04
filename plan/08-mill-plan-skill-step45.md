# Batch: mill-plan-skill-step45

```yaml
task: 'review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure'
batch: mill-plan-skill-step45
cards: 1
verify: null
depends-on: [review-plan-integration]
```

## Batch Scope

Adds Phase: Plan Review step 4.5 to `mill-plan/SKILL.md`: ERROR-only-aggregate retry with a two-pass cap. Closes the orchestrator side of #84. Depends on `review-plan-integration` because the SKILL.md prose references the JSON envelope behaviour B04's Card 17 enables — without the total-fail removal, step 4.5 has no JSON to evaluate.

Docs-only batch — `verify: null` because there's no runnable surface. mill-plan SKILL.md is only consumed by Claude Code at session start; the change takes effect the next time mill-plan runs.

## Cards

### Card 29: Add Phase: Plan Review step 4.5 (ERROR-only retry)

- **Reads:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Modifies:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Within `### Phase: Plan Review`, immediately after step 4c (`On REQUEST_CHANGES AND blocking_count > 0`) and BEFORE step 5 (`Non-progress check`), insert a new step labelled `4.5. **Step 4.5: ERROR-only-aggregate retry (no round consumed)**`. Body — written as a numbered or bullet list under the heading: when the JSON envelope from step 2 has a non-empty `reviews[]` array AND every entry's `verdict` is `"ERROR"`, skip the fix-pass entirely (do NOT enter step 4c) and immediately re-run `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py"`. The round counter is NOT consumed (the round produced no reviewable output). On the second consecutive ERROR-only round, halt with `BLOCKED: review ERROR-only round {N}` and surface the per-entry `error` strings to the user. Do NOT auto-retry beyond the second pass. The two-pass cap mirrors step 1.5's validator gate. Cross-reference the change in #84 (mention as a comment-style aside, not a YAML anchor). Match the heading style used for step 1.5 (bold, parenthesised "no round consumed"). Update step 5's "from round 2 onward" wording only if needed to make clear the non-progress check still applies AFTER step 4.5 has fired in a prior round (otherwise leave step 5 untouched). Do NOT touch the validator-fix mapping table; this batch adds no new check codes.
- **Commit:** `docs(mill-plan): add Phase: Plan Review step 4.5 ERROR-only retry`

## Batch Tests

No verify command (`verify: null`). The change is operator-facing prose; smoke-tested implicitly by the next mill-plan invocation. A future task could add a SKILL.md lint check, but that's out of scope here.
