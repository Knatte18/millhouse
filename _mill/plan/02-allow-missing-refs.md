# Batch: allow-missing-refs

```yaml
task: mill-plan/mill-start planning-process gaps, round 2
batch: allow-missing-refs
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-plan-flow.py
depends-on: []
```

## Batch Scope

Adds an opt-in `--allow-missing-refs` bypass for plan review's brief-bulking hard-fail on a `Context:` ref that points at a file living only on an unmerged predecessor task's branch (#1083). Three cards, in dependency order: card 9 adds the new `allow_missing_refs` keyword to `_review_common.resolve_ref_paths` itself plus its unit tests; card 10 threads the same-named parameter through every `context_reads`/`all_context_reads` call site in `_review_plan.py` (both agent-mode's `prepare()` and subprocess-mode's `run()`/`_review_one_batch`); card 11 exposes it as a CLI flag on `millpy-review-plan.py` and threads it into the two call sites that invoke `prepare()`/`run()`. Land in this numeric order — card 10 calls the new parameter card 9 adds, and card 11 calls the new parameters card 10 adds.

## Cards

### Card 9: `resolve_ref_paths` — new opt-in `allow_missing_refs` bypass

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_review_common.resolve_ref_paths(raw_paths, project_root, root, *, creates_union=None, deletes_union=None, wiki_root=None, git_root=None, caller_label="resolve_ref_paths", soft_fail_gitignored=False)`, add a new keyword-only parameter `allow_missing_refs: bool = False` after the existing `soft_fail_gitignored: bool = False` parameter. Document it in the docstring's "Keyword args" section, mirroring `soft_fail_gitignored`'s own doc-comment shape: "When True, a missing non-wiki candidate — not on disk, not in `creates_union`/`deletes_union`, and not confirmed git-ignored — is skipped with a stderr warning instead of raising `ReviewError`. Opt-in; the `wiki/` branch is never affected, mirroring `soft_fail_gitignored`'s own scope. Default False (#1083)."

  In the function body's non-wiki resolution branch, after the existing `if soft_fail_gitignored:` block (the one that runs `git check-ignore` and may `continue` on a confirmed-ignored hit) and before the final `# Hard-fail.` `raise ReviewError(...)` statement, add:

  ```python
        # Opt-in: skip a missing ref that isn't confirmed git-ignored either, when the caller has
        # explicitly accepted that the referenced file may live on an unmerged predecessor task's
        # branch (#1083).
        if allow_missing_refs:
            print(
                f"[resolve_ref_paths] warning: skipping missing Context: ref "
                f"{raw!r} (not on disk, allow_missing_refs)",
                file=sys.stderr,
            )
            continue
  ```

  Do not touch the `wiki/`-prefixed branch (the block starting `if raw.startswith("wiki/"):`) — `allow_missing_refs`, like `soft_fail_gitignored`, never applies there.

  Add two new test blocks to `test-review-common.py`, placed immediately after the existing four `soft_fail_gitignored`-focused blocks (the ones ending with the print "PASS: resolve_ref_paths hard-fails git-ignored missing ref when soft_fail_gitignored=False explicit"), following that same file's established inline-block-with-`_test_helpers.safe_temp_dir()`-and-`errors += 1`-on-failure style (not a separate `def test_*()` function — this file's `resolve_ref_paths` coverage is one long sequential script, not per-function tests):
  1. `allow_missing_refs=True` skips a missing ref that is NOT git-ignored (a plain non-existent path with no `.gitignore` entry), asserting the result list is empty (`result == []`) and printing a PASS line.
  2. `allow_missing_refs=False` (explicit) still raises `ReviewError` for the identical missing, non-ignored path, asserting the exception message contains `"referenced path not found"` (mirror the existing `soft_fail_gitignored=False explicit` block's try/except/`errors += 1`-on-no-exception shape) and printing a PASS line.
- **Commit:** `feat(review-common): add allow_missing_refs opt-in bypass to resolve_ref_paths`

### Card 10: `_review_plan.py` — thread `allow_missing_refs` through every context-read call site

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Four call sites in this file build `context_reads`/`all_context_reads` via `resolve_ref_paths(..., soft_fail_gitignored=True)` (never `Edits:`/`Creates:`/`Deletes:` reads — those stay hard-fail-only). Add a new keyword-only `allow_missing_refs: bool = False` parameter, threaded to each site's own `resolve_ref_paths` call as an additional `allow_missing_refs=allow_missing_refs` argument, at:

  1. `_review_one_batch(...)` — add `allow_missing_refs: bool = False` as a new keyword-only parameter (after the existing `blocking_classes: frozenset[str]` parameter). Thread it into this function's own `context_reads = resolve_ref_paths(context_only_refs, ...)` call (the one immediately following its `other_reads = resolve_ref_paths(other_refs, ...)` call). Document the new parameter in the function's docstring "Args" section, one line, mirroring `blocking_classes`'s own doc-comment shape.
  2. `prepare(cfg, slug, *, scope, mill_dir, project_root, wiki_root, git_root, agent_mode=False, reviewer_override=None, reviews_subdir=None)` — add `allow_missing_refs: bool = False` as a new keyword-only parameter (after `reviews_subdir`). Thread it into BOTH of this function's `context_reads`/`all_context_reads = resolve_ref_paths(...)` calls — the batch-scope branch (`if scope is not None:`) and the holistic-scope branch (the `else` path) — each already passes `soft_fail_gitignored=True`; add `allow_missing_refs=allow_missing_refs` alongside it. Document the new parameter in `prepare`'s docstring "Args" section, mirroring `reviews_subdir`'s own doc-comment shape ("per-invocation-only", no config write-back).
  3. `run(cfg, slug, mill_dir, wiki_root, project_root, *, git_root, max_rounds=None, holistic_only=False, no_holistic=False, reviewer_override=None, reviews_subdir=None)` — add `allow_missing_refs: bool = False` as a new keyword-only parameter (after `reviews_subdir`). Thread it two ways: (a) into this function's own holistic-branch `all_context_reads = resolve_ref_paths(...)` call (the one paired with `all_other_reads = resolve_ref_paths(...)` inside `run()`'s own body, not inside `_review_one_batch`); (b) into the `ex.submit(_review_one_batch, batch_path, overview_path, reviews_dir, batch_max_rounds, task_title, constraints, batch_reviewer_name, batch_spec, project_root, root, creates_union, deletes_union, moves_sources_union, moves_targets_union, wiki_root, git_root, bulk_timeout, blocking_classes=resolve_blocking_classes(cfg, "plan", batch_path.stem))` call inside the `ThreadPoolExecutor` block, by adding `allow_missing_refs=allow_missing_refs` as an additional keyword argument alongside `blocking_classes=...`. Document the new parameter in `run`'s docstring "Args" section, mirroring `reviews_subdir`'s own doc-comment shape.

  Every new parameter defaults to `False`, so every existing caller of `_review_one_batch`, `prepare`, and `run` that does not pass it keeps today's behavior unchanged.
- **Commit:** `feat(review-plan): thread allow_missing_refs through prepare/run/_review_one_batch`

### Card 11: `millpy-review-plan.py` — `--allow-missing-refs` CLI flag

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new `--allow-missing-refs` flag to the argparse setup in `main()`, mirroring the existing `--skip-validate` flag's shape (`action="store_true"`, no `default=` needed since `store_true` already defaults to `False`), placed immediately after the `--skip-validate` argument definition. Help text: `"Skip the brief-bulking hard-fail on a missing Context: ref (e.g. one living only on an unmerged predecessor task's branch); the ref is dropped from the bulk with a stderr warning instead. Never applies to Edits:/Creates:/Deletes: refs."`

  Thread `allow_missing_refs=args.allow_missing_refs` into both existing call sites that invoke the functions card 10 modified:
  1. The `--stage prepare` branch's `prepare_result = prepare(cfg, slug, scope=None, mill_dir=mill_dir, project_root=project_root, wiki_root=wiki_root, git_root=git_root, agent_mode=True, reviewer_override=args.reviewer, reviews_subdir=args.reviews_subdir)` call.
  2. The `--stage full` (else) branch's `result = run(cfg, slug, mill_dir, wiki_root, project_root, git_root=git_root, max_rounds=args.max_rounds, holistic_only=args.holistic_only, no_holistic=args.no_holistic, reviewer_override=args.reviewer, reviews_subdir=args.reviews_subdir)` call.

  Do not add it to the `--stage finalize` branch — that branch never calls `prepare()` or `run()`.

  Add a new line to the module's top-of-file docstring "Flags:" list documenting `--allow-missing-refs`, matching the existing flags' one-paragraph style (e.g. immediately after the `--skip-validate` entry).
- **Commit:** `feat(millpy-review-plan): expose --allow-missing-refs CLI flag`

## Batch Tests

`verify:` runs `test-review-common.py` (direct unit coverage for card 9's new `resolve_ref_paths` parameter, including the two new test blocks) and `test-review-plan-flow.py` (the existing in-process flow harness for `_review_plan.run`, exercising `run()`'s per-batch and holistic code paths card 10 modifies — a regression guard confirming the new default-`False` parameter doesn't change existing behavior for any of that harness's stub-reviewer scenarios). `test-review-plan-finalize-round.py` is not included — it covers `--round` auto-discovery in the finalize stage only, a code path this batch never touches.
