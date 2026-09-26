MILL_REVIEW_BEGIN
# Review: Ask the parent session when stuck (parent_thread) — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-26
```

## Findings

None.

Checks performed against source:
- The ask-parent return contract (`action`, `guidance`, `halt_suffix`) is produced by `_ask_parent.consume` and `unreachable_suffix`, printed by `millpy-ask-parent.py`, and consumed consistently at every wired site.
- All seven `_ask_parent.SITES` keys have a caller with a matching action set: `go-batch` (mill-go-base SKILL.md Blocked step 1), `go-holistic-cap`, `go-handoff-nits`, `go-handoff-done-gate`, `plan-cap`, `start-cap`, `quick-gate`.
- Each caller sets its session-local one-escalation variable before loading the skill.
- The load happens before `set_blocked`, notify and builder-lock release at each site.
- `--parent-guidance` flows from the callers through `millpy-fix.py` (`PARENT_GUIDANCE` token) into `fixer-holistic-brief.md`, with a `(none)` fallback for an absent or blank file.
- `parent_escalation_timeout_minutes` is present in both `mill-config.yaml` and `plugins/mill/templates/mill-config.yaml`, and `_ask_parent.timeout_minutes` defaults to 60 when the key is absent.
- `_config.load_config`, `_paths.resolve_task_path`, `_paths.status_path`, `_status.read_parent_thread` and `_status.read_slug` all exist with the signatures the new modules use.
- Every file in the plan's "All Files Touched" list is present, and no out-of-plan source file is present.

## Verdict

APPROVE
No blocking findings; all batches are realised and the cross-batch contracts are compatible.
MILL_REVIEW_END
