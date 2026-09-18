# Plan: mill-start Explore: Agent(subagent_type: fork) dispatch fails to perform assigned investigation

```yaml
task: 'mill-start Explore: Agent(subagent_type: fork) dispatch fails to perform assigned investigation'
slug: mill-start-explore-fork-dispatch-failure
approved: false
started: '20260918-174934'
parent: main
root: ""
verify: null
discussion_sha: e9e64a98aa760e4af8dd3020bb42a31ee2ee01d3
```

## Batch Index

```yaml
batches:
  - number: 1
    name: fork-echo-fallback
    file: 01-fork-echo-fallback.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: doc-only fix, no code changes

- **Decision:** This task fixes `plugins/mill/skills/mill-start/SKILL.md`'s "Fork echo caution" paragraph (Phase: Explore) only — it adds a documented fallback for when the paragraph's existing single corrective-retry mitigation itself fails to produce grounded findings. No script, template, or config file changes.
- **Rationale:** Issue #993's observed failure (a fork dispatch returning unrelated/echoed content) is a property of fork dispatch fidelity that this repo has no code-level lever over. Only prompting-level guidance — telling the orchestrator when to stop trusting a fork and switch to a cold agent — is actionable. See `_mill/discussion.md`'s "Fallback trigger" and "Fallback destination" Decisions for the full rationale.
- **Applies to:** all batches (there is only one).

## All Files Touched

- `plugins/mill/skills/mill-start/SKILL.md`
