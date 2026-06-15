# Batch: ref-path-resolution

```yaml
task: Fix millpy-review-plan validator gaps and resolve_ref_paths path-doubling
batch: ref-path-resolution
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py
depends-on: []
```

## Batch Scope

Fixes the #471 path-doubling root cause in the two shared source-ref resolvers in `_review_common.py`. Makes `git_root/root/raw` the primary candidate (when `root` is set) so a worktree whose cwd is the `root:` subfolder no longer doubles the sub-path. This is the foundation every downstream batch builds on: the validator (batch 2) and the review CLI (batch 3) inherit the corrected behaviour through these helpers. External interface consumed by later batches: the unchanged *signatures* of `resolve_ref_paths` and `resolve_existing_paths` (both already accept `git_root`), with corrected internal resolution order. Batch-local decision: `resolve_ref_paths` only needs a reorder; `resolve_existing_paths` needs a NEW candidate added — they are asymmetric today.

## Cards

### Card 1: resolve_ref_paths — make git_root/root/raw primary

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `resolve_ref_paths` (`_review_common.py:582`), change the non-wiki resolution order so that, when `root` is truthy and `git_root is not None`, the candidate `git_root / root / raw` is tried BEFORE `project_root / root / raw`. Concretely: the primary `candidate` for a non-wiki ref with `root` set must become `git_root / root / raw` when `git_root` is available; the existing `project_root / root / raw` becomes a fallback tried only if the primary does not exist on disk; then the existing `git_root / raw` fallback; then creates_union/deletes_union suppression; then the hard-fail `ReviewError`. Preserve the `if git_root is not None` guard so `git_root=None` falls back to `project_root / root / raw` exactly as today. Do not change wiki/ routing, the `raw is None`/`"none"` filter, the creates/deletes suppression semantics, or the hard-fail message format. The `ReviewError` message's `resolved candidate:` should report the primary candidate that was attempted.
- **Commit:** `fix(review): resolve_ref_paths tries git_root/root/raw before project_root`

### Card 2: resolve_existing_paths — add git_root/root/raw candidate

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `resolve_existing_paths` (`_review_common.py:673`), ADD a new primary candidate `git_root / root / raw` for non-wiki refs when `root` is truthy and `git_root is not None`. Today its git-root fallback (lines ~721-726) tries only `git_root / raw`; there is no `git_root/root/raw` candidate. The corrected order for a non-wiki ref with `root` set: try `git_root / root / raw` first, then `project_root / root / raw`, then `git_root / raw`, else silent-drop (this function never raises). Keep the wiki/ routing and the silent-drop-on-missing behaviour unchanged. Mirror the structure used in `resolve_ref_paths` (card 1) so the two functions stay parallel, except `resolve_existing_paths` drops silently instead of raising.
- **Commit:** `fix(review): resolve_existing_paths resolves root refs against git_root`

### Card 3: unit tests for both resolvers

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add cases covering the corrected resolution for BOTH `resolve_ref_paths` and `resolve_existing_paths`. Use tempfile fixtures (no real git). Cover: (a) cwd==git_root layout — `root` set, a file present at `git_root/root/raw` resolves correctly (regression for normal mill-plan); (b) cwd==git_root/root layout (#471) — `project_root` equals `git_root/root`, a file present at `git_root/root/raw`. For `resolve_existing_paths` this is the genuine doubling regression (it has NO `git_root/root/raw` candidate today, so without card 2 it silently drops the file): assert it returns the single-prefixed `git_root/root/raw` and NOT the doubled `git_root/root/root/raw`. For `resolve_ref_paths` (which already had a `git_root/root/raw` fallback at `:656`, so it never doubled) the assertion verifies the REORDER — that `git_root/root/raw` is now the resolved primary and no `ReviewError` is raised. Make this scope distinction explicit in the two assertions; (c) `git_root=None` — falls back to `project_root/root/raw` without crashing; (d) wiki-prefixed paths still route through `wiki_root` unchanged. Follow the existing test style in `test-review-common.py`.
- **Commit:** `test(review): cover git_root-primary ref resolution and #471 doubling`

## Batch Tests

`verify:` runs `test-review-common.py` only, scoped to the two edited functions. The new cases in card 3 are the regression net for #471 (doubling) and the git_root=None fallback. No cross-cutting helper is touched, so per-batch scoping is correct; the full suite is not needed.
