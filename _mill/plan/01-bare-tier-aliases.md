# Batch: bare-tier-aliases

```yaml
task: "Fix stale checkpoint safety, Go binary ephemeral allowlist, and bare agent-tier name trap"
batch: bare-tier-aliases
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py
depends-on: []
```

## Batch Scope

Fixes issue #565: the agent registry defines bare `haiku` but only effort-suffixed `sonnet*`/`opus*`, so `model: sonnet` fails deep in the pipeline with `Unknown reviewer: 'sonnet'`. This batch (a) adds bare convenience aliases `sonnet`, `sonnet_bulk`, `opus`, `opus_bulk` at `effort: medium` to `mill-agents.yaml` for parity with bare `haiku`, (b) enriches `_reviewers.resolve()`'s unknown-name error to list the available registry names, and (c) adds unit tests. No external interface is produced for other batches. Batch-local decision: bare aliases resolve to the **medium** effort tier (the neutral default); explicit `…high`/`…max` remain available unchanged.

## Cards

### Card 1: Add bare sonnet/opus aliases to the agent registry

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/templates/mill-agents.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add four new top-level entries to `mill-agents.yaml`, each `provider: claude`, `type: single`, `effort: medium`, mirroring the existing effort-tier entries' shape. `sonnet`: `model: claude-sonnet-4-6`, `tooluse: true`. `sonnet_bulk`: `model: claude-sonnet-4-6`, `tooluse: false`. `opus`: `model: claude-opus-4-7`, `tooluse: true`. `opus_bulk`: `model: claude-opus-4-7`, `tooluse: false`. Place `opus`/`opus_bulk` adjacent to the existing `opus*` block and `sonnet`/`sonnet_bulk` adjacent to the existing `sonnet*` block, preserving the file's existing alphabetical-by-family ordering. Add a brief comment (ASCII only) at each new bare entry stating it resolves to the medium effort tier and that `…high`/`…max` remain available. Do NOT remove or alter `haiku`, `haiku_bulk`, or any existing entry. The new names must satisfy `_reviewers._NAME_REGEX` (`^[a-z0-9_-]+$`) — they do.
- **Commit:** `feat(agents): add bare sonnet/opus tier aliases at medium effort`

### Card 2: List available names in the unknown-reviewer error

- **Context:**
  - `plugins/mill/templates/mill-agents.yaml`
- **Edits:**
  - `plugins/mill/scripts/_reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_reviewers.resolve(registry, name)`, change the `ReviewerError` raised when `name not in registry` (currently `f"Unknown reviewer: {name!r}"`) to additionally list the valid names: append `". Available: " + ", ".join(sorted(registry))`. Keep the existing `name!r` prefix so the message still reads `Unknown reviewer: 'sonnet'. Available: g25flash, ...`. ASCII only. Do not change the `test_stub` special case, `resolve_role`, `validate_role_refs`, or the cluster-flattening recursion — they propagate the richer message unchanged. The existing `test_load_raises_*` and `validate_role_refs` tests that assert on substring `"Unknown reviewer"` must remain satisfied (the prefix is unchanged).
- **Commit:** `feat(reviewers): list available names in unknown-reviewer error`

### Card 3: Unit tests for bare aliases and the enriched error

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/templates/mill-agents.yaml`
- **Edits:**
  - `plugins/mill/unit_tests/test-reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add test functions to `test-reviewers.py` following the file's existing print-PASS/append-FAIL style. (1) Loading the real plugin template via `_reviewers.load(...)` (or a fixture mirroring the four new entries) and `resolve()`-ing `"sonnet"`, `"opus"`, `"sonnet_bulk"`, `"opus_bulk"` returns specs with `provider == "claude"`, `effort == "medium"`, correct `model` ids, and `tooluse` True for the bare names / False for the `_bulk` names. (2) `validate_role_refs` passes (no raise) for a cfg with `roles.implementer.model: sonnet` and `roles.fixer.model: opus` — the exact #565 repro config. (3) `resolve(registry, "definitely-not-a-name")` raises `ReviewerError` whose message contains both `"Unknown reviewer"` and `"Available:"`. Register any new test functions in the file's run harness the same way existing tests are registered.
- **Commit:** `test(reviewers): cover bare tier aliases and enriched unknown-name error`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py` runs the single test file this batch touches. It covers the registry resolution path (cards 1 & 2) and the new tests (card 3). Scope is intentionally limited to `test-reviewers.py`; `test-agents-defs.py` validates agent `.md` frontmatter (not the registry contents) and is unaffected by the new entries, so it is not in scope.
