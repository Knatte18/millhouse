# Batch: review-plan-reviews-subdir-plumbing

```yaml
task: 'mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)'
batch: review-plan-reviews-subdir-plumbing
number: 6
cards: 3
verify: 'PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-plan-finalize-round.py test-review-prepare-envelope.py'
depends-on: []
```

## Batch Scope

`#786`: implements the CLI-plumbing half of the `--revise` feature batch 5 documents at the `mill-plan/SKILL.md` prose level.
Confirmed by direct reading of `plugins/mill/scripts/millpy-review-plan.py`: there are exactly three sites that resolve or consume `reviews_dir` for plan review — `_review_plan.prepare()` (its own internal `reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)` at line ~369), `_review_plan.run()` (the identical resolution at line ~696), and `millpy-review-plan.py`'s own `--stage finalize` handler (which resolves `reviews_dir` directly at line ~223, without going through `prepare()`/`run()`).
This batch adds an optional `reviews_subdir: str | None = None` parameter to `prepare()` and `run()`, and a new `--reviews-subdir` CLI flag threaded to both of those calls plus the finalize handler's own direct resolution — mirroring the existing `--reviewer` flag's "override for this invocation only, nothing written back to config" contract exactly (both flags default to `None`/inactive and change behavior for the current invocation only).
This batch has no dependency on batch 5 — batch 5's `SKILL.md` prose describes calling this CLI with `--reviews-subdir <name>` but is documentation, not code that imports these functions; the two batches touch disjoint files and either can run first.
No batch-local decisions differ from `## Shared Decisions` in the overview.

## Cards

### Card 15: Add `reviews_subdir` parameter to `_review_plan.prepare()` and `_review_plan.run()`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `prepare(cfg, slug, *, scope, mill_dir, project_root, wiki_root, git_root, agent_mode=False, reviewer_override=None)`, add a new keyword-only parameter `reviews_subdir: str | None = None`, placed after `reviewer_override` in the signature.
  Immediately after the existing line `reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)`, add: `if reviews_subdir: reviews_dir = reviews_dir / reviews_subdir`.
  Add a corresponding `Args:` entry to the docstring: "reviews_subdir: When not None, appended as a subdirectory under the config-resolved `reviews_dir` for this call only (e.g. `revise-2`) — used by mill-plan's `--revise` re-entry mode to give a revision pass its own round-numbering namespace, distinct from the original approved pass's review files. Mirrors `reviewer_override`'s per-invocation-only contract; nothing is written back to config."
  Apply the identical change to `run(cfg, slug, mill_dir, wiki_root, project_root, *, git_root, max_rounds=None, holistic_only=False, no_holistic=False, reviewer_override=None)`: add `reviews_subdir: str | None = None` after `reviewer_override` in the signature, and immediately after its own existing `reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)` line, add the identical `if reviews_subdir: reviews_dir = reviews_dir / reviews_subdir` line, plus the identical docstring `Args:` entry.
  Do not alter either function's other parameters, docstring sections, or body logic beyond these two additions per function.
- **Commit:** `feat(review-plan): add reviews_subdir override to prepare() and run()`

### Card 16: Add `--reviews-subdir` CLI flag and thread it through all three call sites in `millpy-review-plan.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new `parser.add_argument("--reviews-subdir", default=None, help="Append this subdirectory under the resolved reviews_dir for this invocation only (e.g. revise-2), used by mill-plan's --revise re-entry mode. Nothing is written back to config.")` call, placed immediately after the existing `--reviewer` `add_argument` call (mirrors its option style and per-invocation-only contract in the help text).
  At the `--stage prepare` handler's call to `prepare(cfg, slug, scope=None, mill_dir=mill_dir, project_root=project_root, wiki_root=wiki_root, git_root=git_root, agent_mode=True, reviewer_override=args.reviewer)`, add `reviews_subdir=args.reviews_subdir` as a new keyword argument.
  At the `--stage finalize` handler's line `reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)`, add immediately after it: `if args.reviews_subdir: reviews_dir = reviews_dir / args.reviews_subdir` — applied before that `reviews_dir` value is used by the subsequent `discover_round(reviews_dir, "plan", "holistic")` call and the `finalize(...)` call, so both honor the override.
  At the `else:  # full` branch's call to `run(cfg, slug, mill_dir, wiki_root, project_root, git_root=git_root, max_rounds=args.max_rounds, holistic_only=args.holistic_only, no_holistic=args.no_holistic, reviewer_override=args.reviewer)`, add `reviews_subdir=args.reviews_subdir` as a new keyword argument.
  Do not alter the module's docstring flag list, the validator-gate blocks (`--skip-validate`/`--skip-check` handling) in either the `prepare` or `full` branches, or any other argparse option.
- **Commit:** `feat(review-plan-cli): thread --reviews-subdir through prepare/finalize/full stages`

### Card 17: Unit test coverage for `reviews_subdir` plumbing

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Following this file's existing test fixture and naming conventions (in-memory/tempfile fixtures, no real git/LLM, per the `plugins/mill/unit_tests/` module docstring convention), add test coverage for the `reviews_subdir` override added by Cards 15-16:
  (1) calling `prepare(...)` with `reviews_subdir="revise-2"` resolves its internal `reviews_dir` to `<configured-reviews-dir>/revise-2` rather than the bare configured directory — assert on the returned `prepare_result["reviews_dir"]` value (per `prepare()`'s documented return-dict keys: "prompt_text, model, effort, round, reviews_dir, scope");
  (2) calling `prepare(...)` with `reviews_subdir=None` (the default) resolves `reviews_dir` unchanged, exactly as before this batch — a regression guard confirming the override is opt-in only;
  (3) the identical two cases (subdir-set vs. subdir-`None`) for `run(...)`, asserting the round discovered inside the namespaced subdirectory is independent of round files already present in the bare (non-namespaced) `reviews_dir` — i.e. a `revise-2` subdirectory with no review files yet discovers round 1 even when the parent `reviews_dir` already has round 3+ files from the original approved pass.
  Use whichever existing helper this file already uses to construct a `cfg`/`slug`/temp-directory fixture for `prepare()`/`run()` calls — do not introduce a new fixture-construction pattern if an equivalent one already exists in this file.
- **Commit:** `test(review-plan): cover reviews_subdir namespacing for prepare/run`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-plan-finalize-round.py test-review-prepare-envelope.py` — runs the three existing test files that already cover `_review_plan.py`'s `prepare()`/`run()`/finalize-round logic (including Card 17's new `reviews_subdir` cases added to `test-review-plan-flow.py`), scoped to exactly the files this batch's `Edits:` can affect; the full `run-all.py` suite is not needed since this batch touches no cross-cutting helper imported by unrelated test files.
