# Batch: review-common-fixes

```yaml
task: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps
batch: review-common-fixes
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common-guard.py test-review-common.py
depends-on: []
```

## Batch Scope

Two independent fixes to the review backend `_review_common.py`, grouped
because they live in the same module. (1) #487: the worktree snapshot guard
never raises on a reviewer-authored commit because the fast-forward carve-out
classifies it as a tolerated advance — remove the carve-out so any HEAD change
during a review window is an overstep. (2) #489: `_warn_if_prose_diverges`
fires a spurious stderr warning on clean APPROVE reviews — only warn when at
least one severity heading exists, and exclude the `verdict:` line from the
prose scan. The batch also adds unit tests for the #489 behaviour;
the #487 fix is covered by the existing (currently-failing) tests in
`test-review-common-guard.py`. No external interface changes; both edits are
internal to the review backend.

## Cards

### Card 1: Remove the fast-forward carve-out in worktree_snapshot_guard (#487)

- **Context:**
  - `plugins/mill/unit_tests/test-review-common-guard.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `worktree_snapshot_guard` (`_review_common.py`), make any
  HEAD change during the review window an overstep. Change the `should_raise`
  expression to `bool(added) or head_changed or bool(removed)` (computed after
  the existing `expected_paths` filter, which still excludes `reviews_dir`).
  Remove the `fast_forward` local (the `_pygit2_util.is_ancestor(...)` call) and
  the entire fast-forward stderr-warning block (the `if fast_forward and not
  added ...: print(...)`). Leave the `_pygit2_util.is_ancestor` helper itself
  untouched — only its callsite here is removed. Preserve the existing
  exception-chaining contract exactly: when `should_raise` and the block raised,
  `raise ReviewerOverstepError(before_sha, after_sha, diff) from inner_exc`;
  when not raising, re-raise `inner_exc` unchanged at the end. Update the
  docstring to delete the fast-forward-tolerance paragraph. After this change
  the four `TestWorktreeSnapshotGuard` cases in the Context test file pass
  (clean/clean no-raise; clean/mutated raises; raise/clean propagates
  RuntimeError; raise/mutated raises with `__cause__` == the RuntimeError).
- **Commit:** `fix(review): treat any HEAD change during review as overstep (#487)`

### Card 2: Suppress the spurious divergence warning on clean reviews (#489)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_warn_if_prose_diverges` (`_review_common.py`), (1) return
  immediately without emitting any warning when `heading_count == 0`; and (2)
  before running the prose regex, drop every line of `raw_output` whose stripped
  form starts with `verdict:` (so a `verdict: GAPS_FOUND` line can never feed the
  prose count) — scan the filtered text. Do NOT change `parse_blocking_count`'s
  returned heading count or its signature; this edit only governs whether the
  stderr warning fires.
- **Commit:** `fix(review): silence parse_blocking_count divergence warning on clean reviews (#489)`

### Card 3: Unit tests for the #489 warning behaviour

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add unittest cases (capturing stderr via
  `contextlib.redirect_stderr` or equivalent) for `parse_blocking_count` /
  `_warn_if_prose_diverges`: (a) a clean review body with zero `### [GAP]`
  headings whose prose contains a number-plus-severity phrase (e.g. `1 gap`) and
  a `verdict: GAPS_FOUND` line emits NO warning, and `parse_blocking_count(...,
  severity="GAP")` still returns `0`; (b) a review body with two `### [GAP]`
  headings whose prose says a divergent count (e.g. `three GAPs`) STILL emits the
  warning, and the returned count is `2`. Follow the existing test conventions in
  the file (module-path bootstrap, `unittest.TestCase`).
- **Commit:** `test(review): cover parse_blocking_count warning suppression (#489)`

## Batch Tests

`verify:` runs `run-all.py --only test-review-common-guard.py
test-review-common.py`. `test-review-common-guard.py` is the acceptance gate for
#487 (its `TestWorktreeSnapshotGuard` cases fail today and must pass after card
1). `test-review-common.py` covers `_review_common.py` generally and gains the
card-3 cases for #489. Both files are scoped to the single module this batch
edits; no full-suite run needed.
