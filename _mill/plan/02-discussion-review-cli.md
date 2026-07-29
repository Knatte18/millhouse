# Batch: discussion-review-cli

```yaml
task: 'Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran'
batch: discussion-review-cli
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-discussion-flow.py test-review-prepare-envelope.py test-review-cli-error-envelope.py
depends-on: [1]
```

## Batch Scope

This batch wires the `--reviewer` override through the discussion-review backend (`_review_discussion.py`'s `prepare()` and `run()`) and exposes it as a CLI flag on `millpy-review-discussion.py`. It depends on batch `reviewer-override-helper` for `_reviewers.resolve_reviewer_override`. The `--stage finalize` branch of the CLI is deliberately untouched — `--reviewer` has no effect on finalize, which only parses already-produced reviewer output. No batch-local decisions beyond the overview's `## Shared Decisions`.

## Cards

### Card 2: `_review_discussion.py::prepare()` accepts `reviewer_override`

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a `reviewer_override: str | None = None` keyword-only parameter to `prepare()` (currently ending `max_rounds: int | None = None, agent_mode: bool = False`). Replace the reviewer-resolution block (currently: read `reviewer_name = cfg["roles"]["discussion-review"]["holistic"]["reviewer"]`; raise `ReviewError` if `None`; `registry = _reviewers.load(hub_dir)`; `spec = _reviewers.resolve(registry, reviewer_name)`) with:
  - `hub_dir = project_root` and `registry = _reviewers.load(hub_dir)` unconditionally, as today.
  - If `reviewer_override is not None`: resolve it via `_reviewers.resolve_reviewer_override(registry, reviewer_override, reject_non_claude=True)`, wrapped in `try: ... except _reviewers.ReviewerError as exc: raise ReviewError(str(exc)) from exc`; set `reviewer_name = reviewer_override`. This branch must NOT check `cfg["roles"]["discussion-review"]["holistic"]["reviewer"] is None` — an explicit `reviewer_override` bypasses that disablement per the overview's null-bypass Decision (the separate `rounds == 0` check earlier in `prepare()`, at the existing `effective_max == 0` branch, is untouched and still fires before this block runs).
  - Else: unchanged existing behavior — `reviewer_name = cfg["roles"]["discussion-review"]["holistic"]["reviewer"]`; raise `ReviewError("discussion-review holistic reviewer is null; nothing to do")` if `None`; `spec = _reviewers.resolve(registry, reviewer_name)`.
  Wrap the existing `maybe_switch_spec_for_large_prompt(prompt_text, spec, reviewer_name, cfg, "discussion-review", "holistic", registry)` call (currently unconditional, immediately after the `render_prompt(...)` call) in `if reviewer_override is None:` per the overview's large-prompt Decision — when an override is set, `spec`/`reviewer_name` from the block above pass through to the return dict untouched. No change is needed to the `render_prompt(...)` call itself — its `reviewer_model=reviewer_name` keyword argument already reads whichever `reviewer_name` value the block above set.
- **Commit:** `mill: add --reviewer override support to _review_discussion.py prepare()`

### Card 3: `_review_discussion.py::run()` accepts `reviewer_override`

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a `reviewer_override: str | None = None` keyword-only parameter to `run()` (currently ending `max_rounds: int | None = None`). Thread `reviewer_override=reviewer_override` into the `prepare(cfg, slug, mill_dir, project_root, wiki_root, max_rounds=max_rounds)` call inside `run()`. Replace the reviewer re-resolution block (currently: `reviewer_name = cfg["roles"]["discussion-review"]["holistic"]["reviewer"]`; `registry = _reviewers.load(project_root)`; `spec = _reviewers.resolve(registry, reviewer_name)`; unconditional `spec, _ = maybe_switch_spec_for_large_prompt(prompt_text, spec, reviewer_name, cfg, "discussion-review", "holistic", registry)`) with:
  - `registry = _reviewers.load(project_root)` unconditionally, as today.
  - If `reviewer_override is not None`: resolve via `_reviewers.resolve_reviewer_override(registry, reviewer_override, reject_non_claude=False)` — narrower than `prepare()`'s validation, since `run()`'s direct-dispatch path (`_reviewer_single.run()`) never calls `model_to_tier` and must keep accepting non-Claude aliases, matching today's config-based capability — wrapped in `try: ... except _reviewers.ReviewerError as exc: raise ReviewError(str(exc)) from exc`; set `reviewer_name = reviewer_override`; do NOT call `maybe_switch_spec_for_large_prompt` in this branch.
  - Else: unchanged existing behavior — `reviewer_name = cfg["roles"]["discussion-review"]["holistic"]["reviewer"]`; `spec = _reviewers.resolve(registry, reviewer_name)`; `spec, _ = maybe_switch_spec_for_large_prompt(prompt_text, spec, reviewer_name, cfg, "discussion-review", "holistic", registry)`.
- **Commit:** `mill: add --reviewer override support to _review_discussion.py run()`

### Card 4: `--reviewer` CLI flag on `millpy-review-discussion.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new `--reviewer` argument to `main()`'s `argparse.ArgumentParser` (place it immediately before the existing `--actual-model` argument, after `--round`): `parser.add_argument("--reviewer", default=None, help="Override roles.discussion-review.holistic.reviewer for this invocation only (e.g. sonnetmax). Nothing is written back to config.")`. Update the module docstring's `Flags:` list (currently lines 6-14) to document `--reviewer <alias>` in the same one-line style as the existing `--max-rounds` entry. Thread `args.reviewer` into the two dispatch calls that reach the backend:
  - `--stage prepare` branch: add `reviewer_override=args.reviewer` to the existing `prepare(cfg, slug, mill_dir, project_root, wiki_root, max_rounds=args.max_rounds, agent_mode=True)` call.
  - `else:` (`--stage full`) branch: add `reviewer_override=args.reviewer` to the existing `run(cfg, slug, mill_dir, project_root, wiki_root, max_rounds=args.max_rounds)` call.
  - `--stage finalize` branch: leave completely unchanged — `--reviewer` has no effect on finalize.
- **Commit:** `mill: add --reviewer CLI flag to millpy-review-discussion.py`

## Batch Tests

`verify:` runs `test-review-discussion-flow.py` (exercises `_review_discussion.py`'s `prepare()`/`run()` directly — the functions Cards 2-3 change), plus `test-review-prepare-envelope.py` and `test-review-cli-error-envelope.py` (both load `millpy-review-discussion.py` via `importlib` and exercise its `--stage prepare`/error-envelope contract — the CLI Card 4 changes), scoped via `run-all.py --only` rather than the full suite since this batch does not touch plan- or code-review files. The new `reviewer_override`-specific test cases are added in the later `unit-tests` batch; this batch's own `verify:` is a regression check that these three existing files still pass unmodified after the signature/flag changes.
