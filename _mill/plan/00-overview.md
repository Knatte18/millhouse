# Plan: _plan_validate context-completeness: further false-positive/false-negative gaps, round 3

```yaml
task: '_plan_validate context-completeness: further false-positive/false-negative gaps, round 3'
slug: plan-validate-context-completeness-round3-gaps
approved: true
started: 20260923-111625
parent: main
root: ""
verify: null
discussion_sha: cb5629cfe380fe2ae6263fddfb199be62a70358e
```

## Batch Index

```yaml
batches:
  - number: 1
    name: context-completeness-resolution-and-tokenization-rework
    file: 01-context-completeness-resolution-and-tokenization-rework.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
```

## Shared Decisions

### Decision: resolution-scope-rework

- **Decision:** `_resolve_symbol_files` (`plugins/mill/scripts/_plan_validate.py`) stops walking the
  whole repo tree for a bare/dotted symbol candidate. It now resolves only within the plan-wide
  union of files already cited somewhere in the plan (every card's `Context:`/`Edits:`/`Creates:`/
  `Deletes:`/`Moves:` tokens, across every batch) — built once per `run()` call via a new
  `_compute_plan_wide_cited_files` helper. No repo-wide fallback: when the narrowed search finds
  nothing, the token is unresolvable and never flagged.
- **Rationale:** #1131/#1129's false positives (`CellLength`, `InnerRadius`, `OuterRadius`,
  `InvalidOperationException`, …) are well-formed identifiers that coincidentally collide with an
  unrelated file's symbol of the same name purely because the repo is large. Three prior rounds of
  shape/exemption patching cannot close this class — narrowing *where* the search looks is the only
  fix that addresses the root cause. See card 4.
- **Accepted cost:** a symbol cited as a dependency for the very first time anywhere in the plan (no
  card yet names its declaring file) is no longer caught by the symbol branch. This is the same
  blind spot the symbol branch's own path-only predecessor had before it existed — not a regression.
- **Applies to:** context-completeness-resolution-and-tokenization-rework (cards 4, 5).

### Decision: line-join-refactor

- **Decision:** `_check_context_completeness`'s Requirements-text tokenization stops restarting
  `_BACKTICK_RE.finditer` fresh on each physical line. Token EXTRACTION now runs once per maximal
  RUN of contiguous non-quoted physical lines (a quoted/fenced line always starts a new run), never
  once over the whole fence/blockquote-filtered Requirements body joined as a single string — joining
  the whole body would let a dangling backtick bridge across an entire elided quoted region and
  spuriously pair with a real backtick far away, reintroducing the same corruption class this fix
  targets. This fixes a traced backtick-line-wrap corruption bug (an inline-code span crossing a
  markdown line break, within one run, silently swallows every genuine token after it on the closing
  line). Which text an EXEMPTION helper is checked against still splits per-helper, always scoped to
  the current run: the two clause-bounded helpers (`_is_non_dependency_negation_exempt`,
  `_is_contrast_citation_exempt`) run against the run's own joined text with `_clause_bounds`
  additionally capped at that run's own physical-line boundaries; the four unconditional line-wide
  helpers (`_is_prohibition_exempt`, `_is_literal_enumeration_exempt`, `_is_cross_card_ownership_exempt`,
  `_is_illustrative_output_exempt`) keep running against only the physical line(s), within that same
  run, the tested token's own backtick span crosses (normally exactly one line, joined only for the
  rare cross-line-spanning token). This does NOT close `_is_prohibition_exempt`'s own documented
  nested-bullet/multi-line-prohibition limitation — that remains open and out of scope.
- **Rationale:** `_compute_declared_symbols_union` already tokenizes in one pass with no per-line
  loop and never had this bug — it is untouched. `_check_context_completeness` restarts the regex
  per physical line, so an odd-backtick-count inline-code span that opens on one line and closes on
  the next corrupts extraction on the closing line. See card 6.
- **Applies to:** context-completeness-resolution-and-tokenization-rework (card 6).

### Decision: literal-enumeration-majority

- **Decision:** `_is_literal_enumeration_exempt` changes its trigger from "at least one non-shaped
  sibling token" to "non-shaped tokens are a STRICT majority (non-shaped count > shaped count) of
  the line's backtick tokens" (self-inclusive tally — the tested occurrence counts toward both the
  total and its own shape classification). An exact tie is NOT a majority and does not exempt.
- **Rationale:** fixes #1116 (`SteadyStateHydraulicSolver` wrongly swept in by one unrelated
  non-shaped literal on the same line) and #1122 (`millpy-merge-in-subagent.py` wrongly swept in by
  the CLI-mode literal `verify-fix`) — both lines have a minority of non-shaped tokens, so the
  stricter rule stops suppressing the genuine dependency. See card 3.
- **Applies to:** context-completeness-resolution-and-tokenization-rework (card 3).

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
