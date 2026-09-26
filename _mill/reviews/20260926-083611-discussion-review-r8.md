MILL_REVIEW_BEGIN
# Review: Unify ask-parent into ask-thread: ask any named session, default parent

```yaml
duration_s: 221.4
verdict: APPROVE
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-09-26
```

Verified against source: the 12-file rename enumeration (`grep -rn "ask-parent\|ask_parent\|parent-reply" plugins SKILLS.md`) matches every hit found independently, including both `mill-plan/SKILL.md` prose mentions (lines 462, 699); `harness-tool-contracts.md`'s ListAgents/SendMessage/Monitor sections and the "five consumers" list match the planned rename and rewrite; `_vscode_tasks.session_prefix` lower-casing and the `conversation/SKILL.md` numbered-options/AskUserQuestion-ban claims are accurate; the round-5 blocking finding on `parent_escalation_timeout_minutes: 0` silently downgrading direct mode is resolved by the current "automatic-mode kill switch only" decision, with direct mode falling back to `DEFAULT_TIMEOUT_MINUTES`.

Every `### Decision:` carries rationale and a rejected alternative. Scope in/out lists are unambiguous and match the actual caller/file inventory. The ask-id race handling (message vs. file, Monitor re-arm, stale-batch rejection), the automatic/direct fallback split, and the "questions file, not shell args" rationale are internally consistent and cover empty/timeout/error/concurrency cases. Testing section names concrete TDD cases for both new and renamed test files, including the config-comment and open-mode-timeout edge cases.

No BLOCKING or NIT findings.

## Verdict

APPROVE
Decisions are complete, source-grounded, and internally consistent; no undecided items remain.
MILL_REVIEW_END
