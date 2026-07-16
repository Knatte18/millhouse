# Plan: Agent-mode dispatch: envelope fields and session/runtime state are unreliable

```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
slug: mill-go-agent-dispatch-reliability-gaps
approved: true
started: "20260716-135443"
parent: hanf/linux-port-more
root: ""
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agent-dispatch.py test-millpy-implement.py test-implementer-common.py test-millpy-fix.py test-review-prepare-envelope.py test-review-common.py test-review-finalize.py test-review-cli.py test-claude-settings.py
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
    name: effort-tier-implementer
    file: 02-effort-tier-implementer.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py test-millpy-fix.py
  - number: 3
    name: effort-tier-review-cli
    file: 03-effort-tier-review-cli.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-prepare-envelope.py
  - number: 4
    name: reviewer-model-audit-trail-backend
    file: 04-reviewer-model-audit-trail-backend.md
    depends-on: [3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py
  - number: 5
    name: reviewer-model-audit-trail-cli
    file: 05-reviewer-model-audit-trail-cli.md
    depends-on: [4]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-finalize.py test-review-cli.py
  - number: 6
    name: permission-allowlist
    file: 06-permission-allowlist.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-claude-settings.py
```

## Shared Decisions

### Decision: batch ordering follows the shared-call-site chain, not the discussion's grouping order alone

- **Decision:** Batches 2 through 5 form a strict `depends-on` chain (`2←1`, `3←2`, `4←3`, `5←4`) even though discussion.md's three fix-surface groups (implement-prepare / effort-tier+audit-trail / permission-allowlist) suggested only two dependent groups plus one independent one. Batch 6 (`depends-on: []`) is fully independent of 1–5.
- **Rationale:** Batch 1's Card 2 and Batch 2's Card 5 both edit the exact same `emit_prepare(...)` call site in `millpy-implement.py`'s `--stage prepare` branch (Batch 1 adds `start_sha=`, Batch 2 adds `effort=` to the same call) — the `parallel-modifies-overlap` validator requires a dependency edge for any two batches editing the same file, and Batch 2 building on Batch 1's already-corrected call site is the natural order. Discussion.md's second group (effort-tier envelope work plus the `reviewer_model` audit-trail fix) was originally planned as two batches, but each individually exceeded `pipeline.max_batch_context_tokens` (120000) once every card's touched-file byte sum was computed — `_plan_validate`'s `batch-oversized` check rejected both, since several touched files are large (`mill-go/SKILL.md` at ~95KB, and `test-implementer-common.py`/`test-review-common.py` each ~140KB). Each was re-split on its most natural internal seam — implementer/fixer-side vs. review-CLI-side for the effort-tier group (Batches 2/3), and shared-helper-backend vs. CLI-flag-wiring for the audit-trail group (Batches 4/5) — producing four batches chained in sequence, matching the order the underlying fixes actually build on each other (Batch 3's `mill-go/SKILL.md` step-3 edit introduces the recorded-model variable Batch 5's step-6 edit consumes). Batch 6 touches only a new `_claude_settings.py` module and `mill-setup/SKILL.md`, neither touched elsewhere — no dependency needed.
- **Applies to:** all batches (Batch Index `depends-on:` above).

### Decision: verify command shape and scope

- **Decision:** every batch's `verify:` starts with the literal `PYTHONPATH= ` prefix (Python project) and scopes to the specific test file(s) each batch's `Edits:`/`Creates:` touch, via `run-all.py --only <basenames>`. The overview's module-wide `verify:` also uses `--only`, scoped to the union of all eight test files this task touches across every batch (`test-agent-dispatch.py`, `test-millpy-implement.py`, `test-implementer-common.py`, `test-review-prepare-envelope.py`, `test-review-common.py`, `test-review-finalize.py`, `test-review-cli.py`, `test-claude-settings.py`) — an unfiltered `run-all.py` is rejected outright by the plan validator's `verify-full-suite` check.
- **Rationale:** per-batch scoping keeps each implementer/fixer verify round fast. The module-wide check re-runs the full set of nine files this task touches (`test-agent-dispatch.py`, `test-millpy-implement.py`, `test-implementer-common.py`, `test-millpy-fix.py`, `test-review-prepare-envelope.py`, `test-review-common.py`, `test-review-finalize.py`, `test-review-cli.py`, `test-claude-settings.py` — rather than just the current batch's own files) at every batch boundary — this still catches a later batch's changes silently breaking an earlier batch's already-passing tests (e.g. Batch 2's `millpy-implement.py` edit regressing a Batch 1 test case), which per-batch scoping alone would miss since each batch only re-verifies its own files.
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
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-review-cli.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-finalize.py`
- `plugins/mill/unit_tests/test-review-prepare-envelope.py`
