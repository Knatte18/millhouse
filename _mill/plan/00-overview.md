# Plan: Dedicated fixer agent for post-holistic-review fix cycles

```yaml
task: "Dedicated fixer agent for post-holistic-review fix cycles"
slug: "holistic-fix-agent"
approved: true
started: "20260519-121334"
parent: "main"
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: fixer-config
    file: 01-fixer-config.md
    depends-on: []
    verify: "uv run --project plugins/mill python plugins/mill/unit_tests/test-reviewers.py"
  - number: 2
    name: fixer-script
    file: 02-fixer-script.md
    depends-on: [1]
    verify: "uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-fix.py"
  - number: 3
    name: cutover
    file: 03-cutover.md
    depends-on: [2]
    verify: "uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py"
```

## Shared Decisions

### Decision: roles.fixer.model is the single source of truth for fixer model selection

- **Decision:** All fixer sessions resolve their model via `cfg["roles"]["fixer"]["model"]` -> `_reviewers.resolve(registry, model_name)`. Default value `haiku` lives in `plugins/mill/templates/mill-config.yaml`; per-hub overrides live in the hub's `mill-config.yaml` or `.millhouse/config.local.yaml`.
- **Rationale:** Mirrors the existing `roles.implementer.model` pattern. Fixer and implementer are different cost/quality tradeoffs and must be configurable independently. Hard-coding Haiku was explicitly rejected in the discussion.
- **Applies to:** all batches

### Decision: Cold-start dispatch only -- never `resume=True`

- **Decision:** Every `_implementer_claude.run(...)` call from `millpy-fix.py` passes `resume=False`. The fixer never reuses a warm session, regardless of scope.
- **Rationale:** Eliminates psmux keepalive across the review window. Cold-start Haiku is cheap; the plan file plus the review file is sufficient context. Removing warm-session resume is the whole motivation for this task.
- **Applies to:** all batches

### Decision: `SELF_FIX_ROUNDS` token sources from `roles.implementer.self_fix_rounds`

- **Decision:** The fixer brief's `<SELF_FIX_ROUNDS>` token is rendered from `cfg["roles"]["implementer"]["self_fix_rounds"]`. No new `roles.fixer.self_fix_rounds` key is introduced.
- **Rationale:** The self-fix loop is a property of the fix-and-verify cycle, not of which role is fixing. Reusing the implementer key is intentional cross-role sharing; an extra key would only proliferate config without adding flexibility. The current `millpy-implement-holistic.py` already reads this key for the same purpose.
- **Applies to:** all batches

### Decision: `stuck_type: logic` for plan conflicts

- **Decision:** When a review finding contradicts the plan such that no fix is possible without plan revision, the fixer emits `{"status":"stuck","stuck_type":"logic","reason":"plan conflict: <finding title>"}`. The fixer never invents a new stuck_type.
- **Rationale:** Reuses existing mill-go logic-stuck routing (user prompt with options edit-plan / skip / block). No mill-go code change required, no new routing branch.
- **Applies to:** batch 2 (template content), batch 3 (mill-go remains unchanged on this branch)

### Decision: Two separate template files, not one shared template

- **Decision:** `fixer-batch-brief.md` and `fixer-holistic-brief.md` are independent files in `plugins/mill/templates/`. No shared base template, no conditional sections.
- **Rationale:** The two contexts differ meaningfully -- batch fixer gets one batch plan file and one verify command; holistic fixer gets every batch plan file and runs every batch's verify command. A shared template with branching sections would be harder for the planner and reviewer to read and harder to maintain.
- **Applies to:** batch 2

### Decision: Per-batch psmux cleanup moves to immediately after implementation completes

- **Decision:** In `mill-go/SKILL.md`, the per-batch cleanup block is invoked when the implementer's `success` report is parsed (right before the cleanliness gate, before the review CLI fires). Existing terminal invocations at APPROVE / blocked / stuck remain present but become idempotent no-ops (the session id is already cleaned up).
- **Rationale:** With cold-start fix dispatch the warm implementer session is no longer needed once implementation completes. Cleaning up immediately removes the need to keep the session alive through review. The cleanup block is already idempotent (failure-swallowing), so the existing terminal invocations remain harmless.
- **Applies to:** batch 3

### Decision: Adding `roles.fixer.model` is additive -- no key removal

- **Decision:** The plugin template adds a new `roles.fixer:` subsection alongside `roles.implementer:`. No existing key is removed, renamed, or repurposed.
- **Rationale:** Backwards compat for in-flight worktrees. Existing hubs that have not yet pulled this change will deep-merge the new template default at next config load.
- **Applies to:** batch 1

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_reviewers.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement-holistic.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/templates/fixer-batch-brief.md`
- `plugins/mill/templates/fixer-holistic-brief.md`
- `plugins/mill/templates/implementer-fix.md`
- `plugins/mill/templates/implementer-holistic-brief.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-reviewers.py`
