# Review: subprocess-to-agents

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-06-06
```

## Findings

### [GAP] via_psmux migration policy unresolved
**Section:** Testing — `_config` dispatch enum
**Issue:** The test item says "the old `via_psmux` key is handled per the chosen migration (rejected or mapped)" — the parenthetical exposes an unresolved fork: reject-with-error vs. silent-map to `dispatch: psmux`. These produce different `_config.py` code paths and different user-facing behaviour when existing hub configs still carry `via_psmux: true`.
**Fix:** Add a `dispatch-config-migration` decision (or extend `dispatch-config-flag`) stating which policy applies; "map silently" and "reject with a clear error message naming the replacement key" are the two options.

### [GAP] Implementer sub-agent cwd mechanism not decided
**Section:** Technical Context — Gotchas
**Issue:** The gotcha says "the plan should confirm the implementer sub-agent commits to the correct worktree/branch" but gives no mechanism. In subprocess mode `_llm_claude.run_implementer` receives `cwd=project_root`; in agent mode the sub-agent inherits the orchestrator's cwd. If the orchestrator is running in the hub worktree and the task is in a sibling worktree, unqualified `git commit` / Bash operations will target the wrong repo unless the brief explicitly instructs otherwise.
**Fix:** Decide and state the mechanism: either (a) the brief template is updated to prefix every git/Bash call with `git -C <PROJECT_ROOT>` or include a `cd <PROJECT_ROOT>` preamble, or (b) investigate whether the Agent tool accepts a `cwd`/`workdir` override. Without this, the plan writer must invent it.

### [NOTE] Brief file `<identifier>` naming left as placeholder
**Section:** Decisions — `brief-file-lifecycle`
**Issue:** The example path `_mill/briefs/<role>-<identifier>.md` uses `<identifier>` without specifying what it resolves to (batch name, UUID, round number, etc.). Different choices have different uniqueness/collision properties.
**Fix:** Name the concrete value (e.g. batch name for the implementer, reviewer name + round for review roles) so the plan can specify the path formula precisely.

## Verdict

GAPS_FOUND
Two undecided implementation choices (`via_psmux` migration policy and implementer cwd mechanism) must be resolved before the plan can be written.