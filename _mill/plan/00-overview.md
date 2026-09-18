# Plan: _plan_validate.py: subprocess trace noise, batch-oversized TDD cap, unrelated-test-file and fence-unaware parser bugs

```yaml
task: '_plan_validate.py: subprocess trace noise, batch-oversized TDD cap, unrelated-test-file and fence-unaware parser bugs'
slug: plan-validate-misc-check-and-perf-bugs
approved: true
started: '20260918-175420'
parent: main
root: ""
verify: null
discussion_sha: 98982c4bbaea55568b9444eb08ca76fba145f681
```

## Batch Index

```yaml
batches:
  - number: 1
    name: plan-validate-fixes
    file: 01-plan-validate-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-subprocess-util.py
  - number: 2
    name: plan-validate-tests
    file: 02-plan-validate-tests.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
```

## Shared Decisions

### Decision: source-edits and test-edits must stay in separate batches

- **Decision:** batch 1 implements all four fixes in `_plan_validate.py`/`_subprocess_util.py`; batch 2 adds every new/changed test case, entirely in `plugins/mill/unit_tests/test-plan-validate.py` (plus one small test-subprocess-util.py case that lives in batch 1 instead — see below). No batch mixes editing `_plan_validate.py` with editing `test-plan-validate.py`.
- **Rationale:** `test-plan-validate.py` is 471265 bytes (~117816-token estimate) and `_plan_validate.py` is 174461 bytes (~43615-token estimate). `_check_batch_oversized`'s context-size sub-check (the very check this task's own batch 1 fixes to evaluate per-card instead of per-batch) is still evaluated the OLD, per-batch-aggregate way by the *currently installed* plugin cache validator that checks THIS plan — this task's own fix has not landed in that cache yet. Summing both files in one batch (~161431 tokens) exceeds `pipeline.max_batch_context_tokens` (120000) and would fail `batch-oversized` before this plan could even be approved. This is the exact structural trap issue #1000 describes, encountered self-hostingly while planning its own fix.
- **Applies to:** all batches.

### Decision: no backtick citation of `_plan_validate.py` symbols from batch 2's Requirements:

- **Decision:** batch 2's cards describe the source behavior under test in plain prose (function/check names as descriptive text, not backtick-wrapped symbol citations) or, where a precise signature is genuinely needed, inline it directly in `Requirements:` with the `no file read needed` marker per `context-completeness`'s documented escape hatch.
- **Rationale:** a backtick-wrapped symbol citation resolving into `_plan_validate.py` would require that file in the citing card's `Context:`, and `_check_batch_oversized` dedupes file-token bytes at the *batch* level (a set union across all cards) — one citation anywhere in batch 2 would pull the full ~43615-token file into the batch total, pushing it to ~161431 tokens and blowing the cap exactly as the Decision above describes. Every card in batch 2 instead points at existing sibling test functions in `test-plan-validate.py` itself (already implicitly read via that card's own `Edits:`) as structural templates, by name and line number.
- **Applies to:** `plan-validate-tests` (batch 2).

### Decision: card-scoped token-extraction helpers mirror existing in-file precedent

- **Decision:** the new `_card_context_tokens`, `_card_deletes_tokens`, and `_card_moves_tokens` helpers (batch 1, card 4) follow the exact shape of the already-existing `_card_edits_tokens` (line 2548) and `_card_creates_tokens` (line 2119) in `_plan_validate.py` — same `card_text: str -> list[str]` (or `list[tuple[str, str]]` for moves) signature, same `_RE_REFS_HEADER`/`_RE_REFS_SUB` (or `_RE_MOVES_HEADER`/`_RE_MOVE_PAIR`) inline/sub-bullet walk.
- **Rationale:** these regexes and the walk pattern are all module-level/already-defined within `_plan_validate.py` itself (in the same file every batch-1 card edits), so no external file or new pattern is needed — reuse, don't reinvent.
- **Applies to:** `plan-validate-fixes` (batch 1), card 4.

### Decision: fence-delimiter fix applies identically to three call sites

- **Decision:** `_parse_cards`, `_requirements_fence_aware_body`, and the context-completeness Requirements: fence-toggle each change `line.startswith("```")` to a leading-whitespace-tolerant match (`line.lstrip().startswith("```")`), in the same card (batch 1, card 2), as one atomic fix.
- **Rationale:** all three currently share the identical brittle pattern; fixing only `_parse_cards` (the function issue #992 names) would leave `_requirements_fence_aware_body` and the context-completeness scanner equally exploitable by the same indented-delimiter/column-0-content mismatch. See `_mill/discussion.md`'s `fence-delimiter-indentation-tolerance (#992)` Decision for the full root-cause writeup.
- **Applies to:** `plan-validate-fixes` (batch 1), card 2.

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_subprocess_util.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-subprocess-util.py`
