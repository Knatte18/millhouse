MILL_REVIEW_BEGIN
# Review: pipeline.autonomous_mode warns as unknown config key on every mill invocation — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-02
```

## Findings

None. Implementation matches the plan exactly.

Verification performed:
- `_config.py:122` — `deprecated_keys = {"llm.claude.psmux.via_psmux", "pipeline.autonomous_mode"}`, exactly as Card 1 specifies; no other changes to the file.
- `warn_unknown_keys`/`walk_unknown_keys` (`_config.py:89-127`) unchanged aside from the set literal, confirming the suppression mechanism is reused rather than reimplemented.
- `test-config.py:1350-1399` — new test `test_pipeline_autonomous_mode_does_not_trigger_unknown_key_warning` matches Card 2's required body verbatim, including the deliberate inline template (not `_setup_plugin_template`) so the assertion is non-vacuous — confirmed `_setup_plugin_template` (`test-config.py:56-84`) has no top-level `pipeline:` key, validating the plan's stated rationale.
- Test registered in the module-level `tests = [...]` list at `test-config.py:1609`, immediately after `test_via_psmux_does_not_trigger_unknown_key_warning`, per spec.
- Repo-wide grep for `autonomous_mode` returns only the two files in the plan's "All Files Touched" list — no out-of-plan files.
- Single batch, no cross-batch contracts to check; no shared-decision deviation (the one Shared Decision — suppress via `deprecated_keys`, no shim — is applied as-is).

## Verdict

APPROVE
Implementation matches the plan exactly; suppression added correctly, test is non-vacuous, no out-of-plan files.
MILL_REVIEW_END
