MILL_REVIEW_BEGIN
# Review: mill-start Explore: Agent(subagent_type: fork) dispatch fails to perform assigned investigation

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: /home/knatte/Code/millhouse/wts/mill-start-explore-fork-dispatch-failure/_mill/discussion.md
date: 2026-09-18
```

All three Decisions carry rationale and rejected alternatives; no unresolved TBDs. Scope in/out is unambiguous and self-consistent with the Out-of-scope exclusions. Quoted "Fork echo caution" current text (line 58) matches `plugins/mill/skills/mill-start/SKILL.md` line 204 verbatim. The `general-purpose`/`Explore` cold-agent vocabulary claim matches `mill-plan/SKILL.md` line 152 exactly, and mill-start's "Sub-investigation guidance" bullet (line 193) confirmed to name only `Explore`, not `general-purpose`, as claimed. The three-fork-site enumeration matches `mill-go-base/SKILL.md` line 448 verbatim. The `verify:` field claim (Testing section) matches `_plan_validate.py`'s `_check_verify_not_isolated`/`_is_python_project` and `_plan_dag.parse_verify_field` exactly: absent/None/blank all normalize to `command=None`, which skips the PYTHONPATH= check regardless of Python-project status. No CONSTRAINTS.md exists at hub root, so constraint-coverage criterion is not applicable. Testing strategy (manual read-through, no unit test) is justified and consistent with the stated non-code scope.

## Verdict

APPROVE
All claims verified against source; decisions complete with rationale and rejected alternatives.
MILL_REVIEW_END
