# Plan: Ask the parent session when stuck (parent_thread)

```yaml
task: Ask the parent session when stuck (parent_thread)
slug: parent-thread-escalation
approved: true
skip_checks: ["wiki-config-mutation"]
discussion_sha: 95c09528760f6a801e78a2587d95c14eac82a7f6
started: 20260926-070743
parent_branch: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: parent-escalation-helper
    file: 01-parent-escalation-helper.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py test-ask-parent.py test-millpy-ask-parent.py
  - number: 2
    name: fixer-parent-guidance
    file: 02-fixer-parent-guidance.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-fix.py
  - number: 3
    name: ask-parent-skill
    file: 03-ask-parent-skill.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skills-index.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-guards.py
  - number: 4
    name: mill-go-base-wiring
    file: 04-mill-go-base-wiring.md
    depends-on: [2, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-base-agent-only.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-variants.py
  - number: 5
    name: plan-start-quick-wiring
    file: 05-plan-start-quick-wiring.md
    depends-on: [3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-brief-commit.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-variants.py
```

## Shared Decisions

### Decision: ask-parent-return-contract

- **Decision:** the `ask-parent` skill takes three inputs (`site`, `reason`, `actions`) and returns three values to its caller: `action` (`retry` | `approve` | `halt`), `guidance` (free text, possibly empty), and `halt_suffix` (a string the caller appends to its own `blocked_reason` / `BLOCKED:` message when `action` is `halt`; empty when nothing should be appended).
  `halt_suffix` is ` (parent_thread <name> unreachable)` on a `SendMessage` error, ` -- parent: <first guidance line, max 200 chars>` when the parent answered `halt` with guidance (or the reply fell back to `halt`), and empty otherwise.
  Both suffix strings are computed by `_ask_parent` (printed by `millpy-ask-parent.py`), never hand-assembled by a skill.
  The skill never edits `status.md`, never commits, and never prompts; the caller owns every status write and commit.
- **Rationale:** one mechanical contract lets every converted site branch the same way; computing suffixes in Python keeps them ASCII and unit-tested.
- **Applies to:** all batches

### Decision: one-escalation-tracking

- **Decision:** each converted site tracks its one allowed escalation with a session-local variable named in that site's own text (`parent_escalated_batches` set for `go-batch`; `parent_escalated_holistic`, `parent_escalated_nits`, `parent_escalated_done_gate`, `parent_escalated_plan_cap`, `parent_escalated_start_cap`, `parent_escalated_quick_gate` booleans, all initially false/empty).
  The site sets its variable before loading `ask-parent`, so a crash-free re-entry of the same site in the same run skips the escalation and halts as today.
  Nothing is persisted: a fresh session (after a crash or a manual re-run) may escalate again, which is acceptable since it is a new run.
- **Rationale:** `one-escalation-per-site` in the discussion bounds parent traffic per run; persisting the flag would need a new status field for no gain.
- **Applies to:** ask-parent-skill, mill-go-base-wiring, plan-start-quick-wiring

### Decision: escalate-before-recording

- **Decision:** at every converted site the `ask-parent` load happens before the site's `set_blocked` / `set_batch_field(..., "blocked")` / block commit / `_notify.notify` / builder-lock release, and no `_status.append_phase` call happens during the wait.
  A `retry` commit never appends a phase (discussion Decision `no-new-phase-strings`); `approve` reuses the site's existing terminal actions, which append only the phases they already append.
- **Rationale:** a session that dies mid-wait leaves `status.md` at its pre-halt phase, so a re-run resumes normally.
- **Applies to:** mill-go-base-wiring, plan-start-quick-wiring

### Decision: skill-text-verify-uses-direct-invocations

- **Decision:** batches 3, 4 and 5 edit only skill/doc text; their `verify:` runs the existing skill-text lint tests (`test-skill-helper-drift.py` resolves every `_<module>.<fn>(` reference in SKILL.md files and mill-go-base companions; `test-skills-index.py`, `test-guards.py`, `test-mill-go-base-agent-only.py`, `test-mill-go-variants.py`, `test-brief-commit.py` pin skill-text invariants in the files these batches edit) as `&&`-chained direct invocations, one `PYTHONPATH= `-prefixed invocation per file, rather than one `run-all.py --only` list.
- **Rationale:** these test files are unchanged by the task, so a `--only` list would trip the `verify-unrelated-test-file` check, yet they are exactly the tests that scan the edited skill files.
  All of them pass on the current worktree tip.
- **Applies to:** ask-parent-skill, mill-go-base-wiring, plan-start-quick-wiring

### Decision: config-key-bootstrap

- **Decision:** card 4 adds `pipeline.parent_escalation_timeout_minutes: 60` to the hub `mill-config.yaml` and to `plugins/mill/templates/mill-config.yaml`.
  This is a key addition whose consumer (`_ask_parent.timeout_minutes`) ships in the same batch, so the `wiki-config-mutation` skip-check rests on condition (a): card 4 carries the bootstrap explanation.
- **Rationale:** no code outside this task reads the key; `_ask_parent.timeout_minutes` defaults to `60` when the key is absent, so the change is safe for every task running mid-flight on the old or new config.
- **Applies to:** parent-escalation-helper

### Decision: done-gate-recommendation

- **Decision:** recommendation for the operator: set `pipeline.done_gate` to `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` (the full unit suite, run once per task).
  The currently effective value is `null`.
  No lint command is recommended: `uvx ruff check .` exits non-zero on the current worktree tip (pre-existing repo-wide lint debt unrelated to this task).
  Not applied: mill-go gates on the effective config value, not this Decision.
- **Rationale:** batch verifies are scoped; the skill-text batches in particular touch files many unit tests scan.
- **Applies to:** all batches

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path across every batch, sorted alphabetically (Move **source** paths are excluded — they disappear, like `Deletes:` tokens).
Cards are the source of truth;
this section is the input `_plan_validate.py`'s `all-files-touched-mismatch` check cross-references against the derived union of every card's `Edits:`/`Creates:`/Move-target paths, to catch drift between the hand/agent-maintained list here and that derived union._

- `SKILLS.md`
- `mill-config.yaml`
- `plugins/mill/docs/harness-tool-contracts.md`
- `plugins/mill/scripts/_ask_parent.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/millpy-ask-parent.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/skills/ask-parent/SKILL.md`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go-base/handoff.md`
- `plugins/mill/skills/mill-go-base/holistic-review.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-quick/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/fixer-holistic-brief.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-ask-parent.py`
- `plugins/mill/unit_tests/test-millpy-ask-parent.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-status.py`
