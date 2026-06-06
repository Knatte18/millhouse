# Review: Replace subprocess LLM dispatch with the Claude Code Agent tool

```yaml
verdict: GAPS_FOUND
reviewer_model: agent-tool/general-purpose
reviewed_file: _mill/discussion.md
date: 2026-06-06
round: 1
dispatch: agent-tool (dogfooded; read-only subagent via Agent tool, orchestrator wrote this file)
```

## Findings

### [GAP] via_psmux migration still undecided
**Section:** Decisions / dispatch-config-flag and Testing
**Issue:** The discussion never picks one behavior for the legacy `via_psmux` key: Scope says "remove/retire," dispatch-config-flag says "superseding," and Testing says "handled per the chosen migration (rejected or mapped)."
**Fix:** Decide one rule and state it once.

### [GAP] Agent-tool model parameter format unspecified
**Section:** Decisions / model-and-effort
**Issue:** Reviewer specs resolve to provider-specific model strings (e.g. `claude-sonnet-4-6`), but the discussion does not say whether the Agent tool's `model` parameter accepts a raw model id, a tier alias (`sonnet`/`opus`/`haiku`), or a fixed set -- so the plan author cannot know how `impl_spec["model"]` is passed.
**Fix:** State the accepted `model` value form and any mapping from the resolved registry model string.

### [GAP] subagent_type definition format not pinned
**Section:** Decisions / subagent-types
**Issue:** Names `.claude/agents/mill-reviewer` and `mill-implementer` and lists tool sets, but does not specify the file format (frontmatter fields), location (which repo/worktree), or whether checked in vs templated.
**Fix:** Specify the agent-definition file format, required fields, and where the files live / how they reach each worktree.

### [GAP] Brief-file path collisions and cleanup unspecified
**Section:** Decisions / brief-file-lifecycle
**Issue:** Briefs are git-tracked at `_mill/briefs/<role>-<identifier>.md`, but the identifier scheme and overwrite/retention policy are undefined -- re-dispatch on resume and multi-round reviews could collide or pile up.
**Fix:** Define the identifier components (role + batch/scope + round) and the overwrite/retention policy.

### [NOTE] Implementer git env / worktree commit not resolved
**Section:** Technical context / Gotchas
**Issue:** The gotcha leaves an open "confirm" item rather than a decision about how an Agent sub-agent (which inherits orchestrator env, not the stripped subprocess env) commits to the right worktree/branch.
**Fix:** State the expected guarantee (sub-agent inherits orchestrator worktree cwd) or mark it a required integration-test assertion.

### [NOTE] Reviewer model resolution path differs from implementer
**Section:** Decisions / model-and-effort
**Issue:** Implementer resolves via `roles.implementer.model` -> `_reviewers.resolve`; reviewers resolve via role+scope -- the discussion says "the reviewers registry" generically.
**Fix:** Note that prepare must use the same role/scope resolution each existing CLI uses.

## Verdict

GAPS_FOUND
Core design is sound, but via_psmux migration, Agent-tool model/subagent_type formats, and brief-file identity remain unspecified.
