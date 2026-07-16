MILL_REVIEW_BEGIN
# Review: Agent-mode dispatch: envelope fields and session/runtime state are unreliable

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-16
```

## Findings

### [GAP] --actual-model wiring can't reach #644's actual scenario
**Section:** Decisions -> reviewer_model / audit-trail accuracy; Scope In
**Issue:** The decision says the orchestrator "should always pass `--actual-model` derived from whatever the prepare envelope's `model` field actually says," but the same decision states envelope `model` is only the config-resolved tier and "never reflects a manual operator override at Agent-tool-call time, which is exactly the scenario #644 reports" — so the prescribed derivation provably cannot capture the case the fix targets, and no other source for the override value is specified.
**Fix:** State concretely where the orchestrator obtains the actually-dispatched model for the manual-override case (it makes the Agent tool call, so it knows the value it passed), and add a mill-go/SKILL.md step-3/step-6 edit to Scope In that captures the dispatched model and forwards it as `--actual-model`.

### [GAP] Orchestrator finalize step never told to pass --actual-model
**Section:** Scope In; Technical context (mill-go/SKILL.md)
**Issue:** The audit-trail fix adds an `--actual-model` flag to finalize, but Scope In's only SKILL.md edit is the effort documentation in step 2/3; mill-go/SKILL.md step 6 (lines 153-155, the finalize-field-threading list) is not listed for update, so the new flag is never passed and the reviewer_model fix stays inert end-to-end.
**Fix:** Add "update mill-go/SKILL.md step 6 to thread `--actual-model` into review-CLI finalize calls" to Scope In.

### [GAP] Permission-allowlist derivation depends on a nonexistent skill
**Section:** Decisions -> Permission allowlist; Testing
**Issue:** Both the decision and the testing section instruct deriving/verifying the Bash pattern list "using the `fewer-permission-prompts` skill's transcript-scan approach," but that skill does not exist under plugins/mill/skills/ nor under ~/.claude (Glob and Grep find it only in this discussion and prior review artefacts) — so the prescribed derivation method is unavailable to a plan writer.
**Fix:** Point to the skill's real location, or replace the reference with a concrete, self-contained derivation/verification procedure for the allowlist patterns.

### [NOTE] Implementer-side reviewer_model equivalent left unresolved
**Section:** Scope In; Decisions -> reviewer_model
**Issue:** Both scope and decision hedge "the equivalent implementer-side field, if a parallel one exists," leaving whether millpy-implement's finalize writes a model field an open discovery for the plan writer rather than a decided fact.
**Fix:** Resolve now whether `finalize_from_output` stamps a model field and state in/out explicitly, so the plan writer isn't left to guess scope.

## Verdict

GAPS_FOUND
Audit-trail wiring and the permission-allowlist derivation method are underspecified or unrealizable as written.
MILL_REVIEW_END
