# Plan: Agent-mode dispatch: envelope fields and session/runtime state are unreliable

```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
slug: mill-go-agent-dispatch-reliability-gaps
approved: false
started: "20260716-135443"
parent: hanf/linux-port-more
root: ""
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

## Batch Index

```yaml
batches:
  - number: 1
    name: implement-prepare-reliability
    file: 01-implement-prepare-reliability.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agent-dispatch.py test-millpy-implement.py
  - number: 2
    name: effort-tier-envelope
    file: 02-effort-tier-envelope.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-review-prepare-envelope.py test-millpy-implement.py
  - number: 3
    name: reviewer-model-audit-trail
    file: 03-reviewer-model-audit-trail.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-finalize.py test-review-cli.py test-review-prepare-envelope.py
  - number: 4
    name: permission-allowlist
    file: 04-permission-allowlist.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-claude-settings.py
```

## Shared Decisions

### Decision: batch ordering follows the shared-call-site chain, not the discussion's grouping order alone

- **Decision:** Batch 2 (`depends-on: [1]`) and Batch 3 (`depends-on: [2]`) form a strict chain even though discussion.md's three fix-surface groups (implement-prepare / effort-tier+audit-trail / permission-allowlist) suggested only two independent groups. Batch 4 (`depends-on: []`) is fully independent of 1–3.
- **Rationale:** Batch 1's Card 2 and Batch 2's Card 5 both edit the exact same `emit_prepare(...)` call site in `millpy-implement.py`'s `--stage prepare` branch (Batch 1 adds `start_sha=`, Batch 2 adds `effort=` to the same call) — the `parallel-modifies-overlap` validator requires a dependency edge for any two batches editing the same file, and Batch 2 building on Batch 1's already-corrected call site is the natural order. Batch 3's audit-trail fix (`--actual-model` threading) is a direct extension of Batch 2's `mill-go/SKILL.md` step-3 model-recording addition (Batch 3's step-6 threading instruction refers back to the variable Batch 2's step-3 edit introduces) and both touch the same three review-CLI files (`millpy-review-code.py`, `millpy-review-plan.py`, `millpy-review-discussion.py`), so Batch 3 depends on Batch 2 for the same file-overlap reason. Batch 4 touches only a new `_claude_settings.py` module and `mill-setup/SKILL.md`, neither touched elsewhere — no dependency needed.
- **Applies to:** all batches (Batch Index `depends-on:` above).

### Decision: verify command shape and scope

- **Decision:** every batch's `verify:` starts with the literal `PYTHONPATH= ` prefix (Python project) and scopes to the specific test file(s) each batch's `Edits:`/`Creates:` touch, via `run-all.py --only <basenames>`. The overview's module-wide `verify:` runs the full unscoped `run-all.py` suite.
- **Rationale:** per-batch scoping keeps each implementer/fixer verify round fast (seconds, not the multi-minute full-suite cost `CLAUDE.md` warns about). The module-wide check is deliberately unscoped despite that cost warning because Batches 2 and 3 both edit widely-shared helpers (`_implementer_common.py`, `_review_common.py`) that other, untouched test files also import — a full-suite regression net at each batch boundary is the safety margin those shared-helper edits warrant.
- **Applies to:** all batches.

### Decision: no `mill-config.yaml` changes

- **Decision:** this plan does not touch `mill-config.yaml` (hub file or plugin template) or `pipeline.done_gate`.
- **Rationale:** discussion.md's Scope In/Out lists only the specific `.py`/`SKILL.md` files needed for the six fixes; adding a repo-wide `done_gate` is an unrelated config decision the discussion never raised, and the module-wide `verify:` above already provides an equivalent regression net for this task without a config mutation (avoiding the `wiki-config-mutation` validator check entirely).
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/scripts/_agent_dispatch.py`
- `plugins/mill/scripts/_claude_settings.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/unit_tests/test-agent-dispatch.py`
- `plugins/mill/unit_tests/test-claude-settings.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-review-cli.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-finalize.py`
- `plugins/mill/unit_tests/test-review-prepare-envelope.py`
