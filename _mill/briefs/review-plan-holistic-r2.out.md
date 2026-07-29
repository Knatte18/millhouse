MILL_REVIEW_BEGIN
# Review: mill-merge misjudges worktree topology and mishandles Step 5 squash-restore checkout — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: plan/
date: 2026-07-29
```

## Findings

None. Cross-checked every line-number/quote citation in both batches (Cards 1-7) against the actual contents of `_inplace.py`, `_paths.py`, `millpy-cleanup.py`, `test-inplace.py`, `test-paths.py`, `test-review-common.py`, `test-cleanup.py`, `mill-merge/SKILL.md`, `mill-merge-in/SKILL.md`, and `test-merge.py` — all citations (line numbers, quoted strings, existing patch sites, existing swallow-idiom, `_resolve_inplace_mode` control flow, `SlugRecord` shape, `_fake_run2` pattern, test-cleanup.py's `except AssertionError`-only `main()`, the M2/M2+sub/`skip_slug_validation` fixture sites in test-paths.py and test-review-common.py, and test-merge.py's `_run`/`_assert`/`SCRATCH` helpers and the flat-hub scenario's insertion point) resolved correctly. Both Shared Decisions are faithfully and completely implemented by their respective cards. Batch Index DAG is a clean two-node, no-dependency graph with both `file:` targets present. Global step (card) numbering is 1-7, sequential, no gaps. All cards carry non-empty Creates/Edits/Context/Moves/Requirements/Commit; `Moves: none` throughout, so no rename-mechanic requirement applies. Requirements throughout name specific functions/lines rather than vague prose. Card 5's reasoning about why `millpy-cleanup.py:437`'s fallback was previously unreachable is independently verifiable and correct. Card 7's integration-scenario git sequence (squash → reset → bare-checkout repro → reset again (no-op) → guarded checkout via `shell=True` → commit → `show --stat` assertion) is internally consistent with the actual git failure mode and mirrors the real Step 5 command ordering.

## Verdict

APPROVE
Both batches are accurately grounded in the current source and fully implement both Shared Decisions with no gaps found.
MILL_REVIEW_END
