# Batch: move-parsing-foundation

```yaml
task: "Add first-class Moves/Renames field to plan cards for rename-heavy batches"
batch: "move-parsing-foundation"
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common.py
depends-on: []
```

## Batch Scope

This batch delivers the single shared `Moves:` parser in `_review_common.py`
that every other batch consumes — `parse_moves` (extract `(old, new)` pairs from
a batch file) and `compute_moves_union` (aggregate sources/targets across a plan
directory). It mirrors the existing `parse_batch_refs` / `compute_creates_union`
/ `compute_deletes_union` helpers in the same module. The external interface the
validator (batch 2) and review backends (batch 4) consume is exactly these two
functions plus the `_RE_MOVES_HEADER` regex. Per `## Shared Decisions`
(single-moves-parser), nothing else re-implements move parsing. All additions
are purely additive — no existing function changes — so existing tests across
the suite are unaffected.

## Cards

### Card 1: Moves regex + parse_moves in _review_common

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a module-level regex `_RE_MOVES_HEADER = re.compile(r"^-\s*\*\*Moves:\*\*(?P<inline>.*)$")` near the existing `_RE_REFS_HEADER` (line ~475). Do NOT add `Moves` to `_RE_REFS_HEADER` — its sub-bullet grammar is a single backtick path, but a Move sub-bullet has two backtick paths plus an arrow, and `reads-not-backtick-path` in `_plan_validate.py` rejects sub-bullets with more than one backtick. Add `parse_moves(batch_path: Path) -> list[tuple[str, str]]`: parse each `- **Moves:**` header; if the inline value is `none` (case-insensitive) treat as empty; otherwise read multi-line sub-bullets (reuse the `_RE_REFS_SUB` pattern at line ~479), and for each sub-bullet matching exactly two backtick-wrapped tokens separated by ` -> ` (literal space-hyphen-greater-space, ASCII) append `(src, dst)`. Tolerate malformed sub-bullets by skipping them — `parse_moves` MUST NOT raise (the `move-format` validator check in batch 2 reports malformed bullets). Return a deduplicated list preserving first-seen order.
- **Commit:** `feat(review-common): add _RE_MOVES_HEADER and parse_moves`

### Card 2: compute_moves_union in _review_common

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `compute_moves_union(plan_dir: Path) -> tuple[set[str], set[str]]` returning `(sources, targets)`. Iterate every `??-*.md` under `plan_dir` except `00-overview.md` (mirror `compute_creates_union` at line ~539), call `parse_moves` on each, and accumulate sources (first element) and targets (second element) into two sets. Return `(set(), set())` when `plan_dir` does not exist. Update the module docstring's public-API list (lines ~35-37) to add one line each for `parse_moves()` and `compute_moves_union()`.
- **Commit:** `feat(review-common): add compute_moves_union`

### Card 3: Unit tests for parse_moves and compute_moves_union

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add tests covering `parse_moves`: a single `` `a` -> `b` `` pair; multiple pairs; inline `none` returns `[]`; a `Moves:` field mixed among other card fields; a malformed sub-bullet (missing arrow, or only one backtick path) is skipped without raising. Add tests covering `compute_moves_union`: aggregation of sources and targets across two batch files; empty/non-existent `plan_dir` returns `(set(), set())`; `none` filtered. Add one regression test asserting `parse_batch_refs` does NOT return any token from a `- **Moves:**` bullet (Moves stays on the dedicated parser). Follow the in-memory/tempfile fixture style already used in this file; no real git.
- **Commit:** `test(review-common): cover parse_moves and compute_moves_union`

## Batch Tests

`verify:` runs `test-review-common.py` only — this batch adds two functions and
one regex to `_review_common.py` and their tests live in that file. The changes
are additive (no existing signature changes), so the scoped run is sufficient;
no cross-cutting helper behavior changes, so the full suite is not needed.
