# Plan: _plan_validate.py: path-reference heuristic false positives (round 3) + run() docstring drift

```yaml
task: '_plan_validate.py: path-reference heuristic false positives (round 3) + run() docstring drift'
slug: mill-plan-validate-heuristic-gaps-3
approved: false
started: 20260810-174901
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: heuristic-gaps
    file: 01-heuristic-gaps.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
```

## Shared Decisions

### Decision: marker-substring architecture stays flat

- **Decision:** All three fixes that touch exemption logic (#807 citation markers, #789 prohibition
  markers) extend the existing flat-tuple substring-match architecture (`_PROHIBITION_MARKERS` /
  new `_CITATION_MARKERS`). No verb-parsing, no allowlist-of-consuming-verbs rewrite, no new
  plan-format annotation field.
- **Rationale:** matches `_mill/discussion.md`'s `citation-exemption-via-markers` and
  `prohibition-marker-change-modify` Decisions — this is a heuristic-tuning task, not an
  architecture change. Accepts the same false-negative risk tolerance already priced into the
  existing marker tuples.
- **Applies to:** all cards in batch `heuristic-gaps`.

### Decision: moves_sources is a plan-wide exemption, not per-card

- **Decision:** the new `moves_sources` exemption in `_check_context_completeness` mirrors
  `creates_union`/`deletes_union`'s existing plan-wide (not per-card) scope — a token that is a
  `Moves:` source anywhere earlier in the plan is exempt in *any* later card's `Requirements:`.
- **Rationale:** matches `_mill/discussion.md`'s `moves-sources-plan-wide-exemption` Decision — the
  whole point is a later card referencing an earlier card's Move, which a per-card check cannot
  catch.
- **Applies to:** card 2 (batch `heuristic-gaps`).

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
