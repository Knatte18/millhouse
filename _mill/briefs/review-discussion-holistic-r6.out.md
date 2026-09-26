MILL_REVIEW_BEGIN
# Review: Unify ask-parent into ask-thread: ask any named session, default parent

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-26
```

Scope, decisions, and constraints checked against source: `plugins/mill/skills/ask-parent/SKILL.md`, `_ask_parent.py`, `millpy-ask-parent.py`, `test-ask-parent.py`, `harness-tool-contracts.md`, `orch-wait/SKILL.md`, `_status.read_parent_thread`, `_paths.resolve_task_path`, `_vscode_tasks.session_prefix`, `mill-config.yaml` + template, `mill-start/SKILL.md`'s batch-of-5 and `mill:conversation` AskUserQuestion ban, `mill-plan/SKILL.md`'s two prose mentions, and `SKILLS.md`'s row. A repo-wide grep for `ask-parent|ask_parent|parent-reply` returns exactly the files the In-scope list names, no more, no fewer. Every checked claim (SITES keys, `read_parent_thread` signature, `resolve_task_path` fallback behaviour, `MH:orch`/lower-cased prefix asymmetry, `parent_escalation_timeout_minutes` default and comment location, `ListAgents` having no prior caller) matches the source.

Reply-protocol race handling (ask-id-first-line tiebreak between message and file), the automatic/direct fallback split, and the explicit "works correctly either way" framing for unverified message wake-up are internally consistent. Every `### Decision:` carries a rejected alternative; two decisions (`Target context growth`, `Delivery tests`) fold their rationale into the decision bullet rather than a separate `Rationale:` line, but the reasoning is present and unambiguous.

No BLOCKING or NIT findings.

## Verdict

APPROVE
No undecided items, scope gaps, or source contradictions found on a fresh pass.
MILL_REVIEW_END
