# Batch: plan-review-cli

```yaml
task: 'Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran'
batch: plan-review-cli
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-prepare-envelope.py test-review-cli-error-envelope.py
depends-on: [1]
```

## Batch Scope

This batch wires the `--reviewer` override through the plan-review backend's holistic scope only (`_review_plan.py`'s `prepare()` holistic branch and `run()` holistic branch) and exposes it as a CLI flag on `millpy-review-plan.py`. It depends on batch `reviewer-override-helper` for `_reviewers.resolve_reviewer_override`. Per the overview's holistic-only Decision, the per-batch resolution paths in both `prepare()` and `run()` are never touched by this batch. The `--stage finalize` branch is deliberately untouched, same as batch `discussion-review-cli`.

## Cards

### Card 6: `_review_plan.py::prepare()` holistic branch accepts `reviewer_override`

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a `reviewer_override: str | None = None` keyword-only parameter to `prepare()` (currently ending `git_root: Path, agent_mode: bool = False`). In the holistic branch (the `else:` block reached when `scope is None`), replace the reviewer-resolution block (currently: `holistic_name = cfg["roles"]["plan-review"]["holistic"]["reviewer"]`; raise `ReviewError("plan-review holistic reviewer is null")` if `None`; `holistic_spec = _reviewers.resolve(registry, holistic_name)`) with:
  - If `reviewer_override is not None`: resolve via `_reviewers.resolve_reviewer_override(registry, reviewer_override, reject_non_claude=True)`, wrapped in `try: ... except _reviewers.ReviewerError as exc: raise ReviewError(str(exc)) from exc`; set `holistic_name = reviewer_override`; `holistic_spec = <the resolved spec>`. This bypasses the `reviewer is null` disablement per the overview's null-bypass Decision.
  - Else: unchanged existing behavior — `holistic_name = cfg["roles"]["plan-review"]["holistic"]["reviewer"]`; raise `ReviewError("plan-review holistic reviewer is null")` if `None`; `holistic_spec = _reviewers.resolve(registry, holistic_name)`.
  Wrap the existing `holistic_spec, holistic_name = maybe_switch_spec_for_large_prompt(prompt_text, holistic_spec, holistic_name, cfg, "plan-review", "holistic", registry)` call (currently unconditional, near the end of the holistic branch after `render_prompt(...)`) in `if reviewer_override is None:`.
  The per-batch branch (`if scope is not None:`, which resolves `batch_reviewer_name`/`batch_spec`) is completely untouched by this card — `reviewer_override` is accepted by the function signature regardless of `scope` but has no effect when `scope is not None`, per the overview's holistic-only Decision. There is no live caller today that passes both a batch `scope` and `reviewer_override` together, so this is a documented no-op, not a new error path.
- **Commit:** `mill: add --reviewer override support to _review_plan.py prepare() holistic scope`

### Card 7: `_review_plan.py::run()` holistic branch accepts `reviewer_override`

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a `reviewer_override: str | None = None` keyword-only parameter to `run()` (currently ending `holistic_only: bool = False, no_holistic: bool = False`). In the reviewer-loading step (step 3, where `holistic_name = cfg["roles"]["plan-review"]["holistic"]["reviewer"]` is currently read, followed by `if holistic_name is None or cfg["roles"]["plan-review"]["holistic"]["rounds"] == 0: holistic_spec = None else: holistic_spec = _reviewers.resolve(registry, holistic_name)`), change only the holistic half:
  - If `reviewer_override is not None`: resolve via `_reviewers.resolve_reviewer_override(registry, reviewer_override, reject_non_claude=False)` (the narrower `run()`-scope validation, matching Card 4's rationale for the discussion-review equivalent), wrapped in `try: ... except _reviewers.ReviewerError as exc: raise ReviewError(str(exc)) from exc`; set `holistic_name = reviewer_override`; `holistic_spec = <the resolved spec>`. This bypasses the `holistic_name is None` disablement but does NOT bypass the separate `cfg["roles"]["plan-review"]["holistic"]["rounds"] == 0` check in this same `if`/`else` — that check must still independently set `holistic_spec = None` when rounds is 0, exactly as the overview's null-bypass Decision requires (the step-5 holistic-review section already short-circuits to an APPROVE stub before any prompt is built when `holistic_max_rounds == 0`, so this ordering is preserved).
  - Else: unchanged existing behavior.
  - The immediately-preceding `batch_reviewer_name`/`batch_spec` resolution (the per-batch half of step 3) is completely untouched.
  In the holistic-review section (step 5, after the `prompt_text = render_prompt("review-plan-holistic", ...)` call for the holistic scope), wrap the existing `holistic_spec, holistic_name = maybe_switch_spec_for_large_prompt(prompt_text, holistic_spec, holistic_name, cfg, "plan-review", "holistic", registry)` call in `if reviewer_override is None:`.
- **Commit:** `mill: add --reviewer override support to _review_plan.py run() holistic scope`

### Card 8: `--reviewer` CLI flag on `millpy-review-plan.py`

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new `--reviewer` argument to `main()`'s `argparse.ArgumentParser` (place it immediately before the existing `--actual-model` argument, after `--round`, matching this CLI's existing flag ordering): `parser.add_argument("--reviewer", default=None, help="Override roles.plan-review.holistic.reviewer for this invocation only (e.g. sonnetmax). Holistic scope only -- batch-scope reviewer is unaffected. Nothing is written back to config.")`. Update the module docstring's `Flags:` list (currently lines 6-14) to document it in the same one-line style as the existing `--max-rounds` entry, explicitly noting the holistic-only scope. Thread `args.reviewer` into the two dispatch calls that reach the backend:
  - `--stage prepare` branch: add `reviewer_override=args.reviewer` to the existing `prepare(cfg, slug, scope=None, mill_dir=mill_dir, project_root=project_root, wiki_root=wiki_root, git_root=git_root, agent_mode=True)` call.
  - `else:` (`--stage full`) branch: add `reviewer_override=args.reviewer` to the existing `run(cfg, slug, mill_dir, wiki_root, project_root, git_root=git_root, max_rounds=args.max_rounds, holistic_only=args.holistic_only, no_holistic=args.no_holistic)` call.
  - `--stage finalize` branch: leave completely unchanged.
- **Commit:** `mill: add --reviewer CLI flag to millpy-review-plan.py`

## Batch Tests

`verify:` runs `test-review-plan-flow.py` (exercises `_review_plan.py`'s `prepare()`/`run()` directly — the functions Cards 6-7 change), plus `test-review-prepare-envelope.py` and `test-review-cli-error-envelope.py` (both load `millpy-review-plan.py` via `importlib` and exercise its `--stage prepare`/error-envelope contract — the CLI Card 8 changes), scoped via `run-all.py --only`. The new `reviewer_override`-specific test cases are added in the later `unit-tests` batch; this batch's own `verify:` is a regression check that these three existing files still pass unmodified after the signature/flag changes.
