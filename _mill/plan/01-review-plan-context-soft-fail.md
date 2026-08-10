# Batch: review-plan-context-soft-fail

```yaml
task: '_review_common/_review_plan: verdict/count consistency and path-suppression gaps'
batch: review-plan-context-soft-fail
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-plan-flow.py
depends-on: []
```

## Batch Scope

`_review_plan.py` gets the same `Context:` vs `Edits:`/`Creates:`/`Deletes:` ref split that `_review_code.py`'s `prepare()` already has (added for `#733`): a `Context:`-only ref that is missing on disk AND confirmed git-ignored soft-fails instead of raising `ReviewError`; a missing `Edits:`/`Creates:`/`Deletes:` ref still hard-fails unconditionally, since those name files the batch is expected to produce or touch. This closes the asymmetry `#808` reported — `_review_plan.py` currently has zero soft-fail capability for any ref type. The literal `#808` repro (an `Edits:`-only gitignored+deleted path) is deliberately NOT fixed by this batch — see discussion.md's `plan-review-context-soft-fail-parity` Decision. There are 4 independent call sites in `_review_plan.py`, each needing the identical split-and-resolve-twice treatment; Cards 1-4 apply it once per site, Card 5 adds regression + new-behavior test coverage.

## Cards

### Card 1: Split refs in `_review_one_batch()`

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_one_batch()` (def at line 132), replace the single-call ref resolution at lines 177-185:
  ```
        raw_refs = parse_batch_refs(batch_path)
        raw_refs_set = set(raw_refs)
        # Merge move targets into creates suppression set so downstream batches referencing a move target don't raise ReviewError.
        combined_creates = creates_union | moves_targets
        reads = resolve_ref_paths(
            raw_refs, project_root, root,
            creates_union=combined_creates, deletes_union=deletes_union,
            wiki_root=wiki_root, git_root=git_root, caller_label="_review_plan",
        )
  ```
  with a Context:-only split mirroring `_review_code.py`'s `prepare()` pattern at lines 266-290 (`context_only_refs`/`other_refs` built via two `parse_batch_refs(bp, fields=(...))` calls, then two `resolve_ref_paths` calls, only the `Context:`-only one passing `soft_fail_gitignored=True`): call `parse_batch_refs(batch_path, fields=("Context",))` for the soft-fail-eligible set and `parse_batch_refs(batch_path, fields=("Edits", "Creates", "Deletes"))` for the hard-fail set, resolve each separately (the `Edits:`/`Creates:`/`Deletes:` group keeping today's call shape and arguments exactly, the `Context:` group adding `soft_fail_gitignored=True`), then concatenate the two resolved lists into `reads` (same variable name, same final shape/order-independent list-of-Path semantics existing callers already consume). Before editing, read the rest of `_review_one_batch()` (through its closing `return`) to confirm no other statement in the function reads `raw_refs` or `raw_refs_set` in a way this split would break; if such a use exists, keep `raw_refs_set` populated as the union of both field-groups' refs (`set(context_only_refs) | set(other_refs)`) so its existing semantics (the full unsplit ref set) are preserved. `combined_creates` (built from `creates_union | moves_targets` — note this call site's local variable is named `moves_targets`, not `moves_targets_union` like the other three sites) is passed to both resolve calls unchanged.
- **Commit:** `fix(_review_plan): split Context: refs from Edits:/Creates:/Deletes: in _review_one_batch (#808)`

### Card 2: Split refs in `prepare()`'s per-batch scope branch

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `prepare()` (def at line 336), per-batch scope branch, replace the single-call ref resolution at lines 408-416:
  ```
        raw_refs = parse_batch_refs(batch_path)
        raw_refs_set = set(raw_refs)
        # Merge move targets into creates suppression set so downstream batches referencing a move target don't raise ReviewError.
        combined_creates = creates_union | moves_targets_union
        reads = resolve_ref_paths(
            raw_refs, project_root, root,
            creates_union=combined_creates, deletes_union=deletes_union,
            wiki_root=wiki_root, git_root=git_root, caller_label="_review_plan",
        )
  ```
  with the identical split-and-resolve-twice pattern described in Card 1's Requirements (same `parse_batch_refs(..., fields=(...))` split, same two `resolve_ref_paths` calls with only the `Context:`-only one passing `soft_fail_gitignored=True`, same `reads` concatenation, same variable-preservation caveat for any other in-function use of `raw_refs`/`raw_refs_set`). This call site's local variable is `moves_targets_union` (not `moves_targets` — that name is specific to Card 1's site).
- **Commit:** `fix(_review_plan): split Context: refs from Edits:/Creates:/Deletes: in prepare() per-batch scope (#808)`

### Card 3: Split refs in `prepare()`'s holistic scope branch

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `prepare()` (def at line 336), holistic scope branch, replace the ref-union-then-resolve block at lines 509-520:
  ```
        # Union all Context:/Edits:/Creates: across all batch files
        all_raw_refs: dict[str, None] = {}
        for batch_path in batch_files:
            for ref in parse_batch_refs(batch_path):
                all_raw_refs[ref] = None
        # Merge move targets into creates suppression set so downstream batches referencing a move target don't raise ReviewError.
        combined_creates = creates_union | moves_targets_union
        all_reads = resolve_ref_paths(
            list(all_raw_refs.keys()), project_root, root,
            creates_union=combined_creates, deletes_union=deletes_union,
            wiki_root=wiki_root, git_root=git_root, caller_label="_review_plan",
        )
  ```
  Build two unions instead of one — `all_context_refs: dict[str, None]` from `parse_batch_refs(batch_path, fields=("Context",))` across `batch_files`, and `all_other_refs: dict[str, None]` from `parse_batch_refs(batch_path, fields=("Edits", "Creates", "Deletes"))` across the same loop — then resolve each union separately (the `Edits:`/`Creates:`/`Deletes:` union keeping today's call shape, the `Context:` union adding `soft_fail_gitignored=True`), and concatenate into `all_reads` (same variable name, same final list semantics). This mirrors `_review_code.py`'s `prepare()` split (lines 266-290) applied to a per-batch-union loop instead of a single batch file — same principle, plural source.
- **Commit:** `fix(_review_plan): split Context: refs from Edits:/Creates:/Deletes: in prepare() holistic scope (#808)`

### Card 4: Split refs in `run()`'s holistic scope branch

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `run()` (def at line 660), holistic scope branch, replace the ref-union-then-resolve block at lines 906-917:
  ```
            # Union all Context:/Edits:/Creates: across all batch files
            all_raw_refs: dict[str, None] = {}
            for batch_path in batch_files:
                for ref in parse_batch_refs(batch_path):
                    all_raw_refs[ref] = None
            # Merge move targets into creates suppression set so downstream batches referencing a move target don't raise ReviewError.
            combined_creates = creates_union | moves_targets_union
            all_reads = resolve_ref_paths(
                list(all_raw_refs.keys()), project_root, root,
                creates_union=combined_creates, deletes_union=deletes_union,
                wiki_root=wiki_root, git_root=git_root, caller_label="_review_plan",
            )
  ```
  with the identical split-union-then-resolve-twice pattern described in Card 3's Requirements (this is `prepare()`'s holistic branch's twin site, kept in sync for prepare/finalize symmetry per the discussion's `Technical context` note — same two-union construction, same two `resolve_ref_paths` calls, same `soft_fail_gitignored=True` scoped to the Context: union only, same `all_reads` concatenation).
- **Commit:** `fix(_review_plan): split Context: refs from Edits:/Creates:/Deletes: in run() holistic scope (#808)`

### Card 5: Test coverage for the Context:/Edits: split

- **Context:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Extend `test-review-plan-flow.py` with new inline test blocks (this file has no discrete `def test_*` functions — it is one `def main() -> int:` with sequential comment-delimited blocks that print `PASS:`/`FAIL:`, per the existing convention already used throughout the file; follow that exact style, do not introduce `def test_*` functions). Mirror `test-review-code-flow.py`'s `test_context_only_gitignored_ref_soft_fails_prepare()` (line 1925) fixture shape — a `Context:`-only ref missing on disk AND confirmed git-ignored — adapted to `_review_plan.py`'s `prepare()`. Add at minimum: (1) a per-batch-scope case — a plan batch file whose `Context:` lists a path that is missing on disk and covered by `.gitignore`, calling `prepare()` (per-batch scope branch, Card 2's site) and asserting it does NOT raise `ReviewError`; (2) a holistic-scope case — same fixture shape, calling `prepare()`'s holistic branch (Card 3's site) with the same assertion; (3) a regression case — a `Context:`-only ref missing on disk and NOT covered by `.gitignore` still raises `ReviewError` (both a per-batch and holistic variant, or one variant with an explicit note in `## Batch Tests` if only one is added, per the discussion's testing guidance to cover "at least a per-batch call site and the holistic call site, since both are being changed"); (4) a design-boundary regression case — an `Edits:`-only ref missing on disk AND covered by `.gitignore` still hard-fails with `ReviewError` (confirms `#808`'s literal repro remains unfixed by design, per discussion.md's `plan-review-context-soft-fail-parity` Decision). Run the full file (not just the new blocks) after adding these to confirm the existing "Test 9" (line ~751, `len(r.reviews) == 1` resume-mode assertion) and "Test 17" (line ~1095, same assertion) blocks still pass unchanged — these guard the `#790`/`#184` resume behavior this plan must not disturb (see `00-overview.md`'s `790-not-touched` Shared Decision).
- **Commit:** `test(_review_plan): cover Context: soft-fail split at per-batch and holistic scope (#808)`

## Batch Tests

`verify:` runs `test-review-plan-flow.py` in full (not `--only`-scoped to new blocks) because the file has no per-test isolation (single `main()` with sequential blocks) and because Card 5 explicitly requires the pre-existing "Test 9"/"Test 17" resume-mode assertions to keep passing as a regression guard for the `#790` scope decision. `test-review-common.py` and `test-review-code-flow.py` are not re-run by this batch's `verify:` — neither `resolve_ref_paths` nor `_review_code.py` is edited by any card here, only referenced as read-only Context for the pattern they already establish.
