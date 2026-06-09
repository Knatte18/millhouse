# Batch: Review CLI finalize: drop prepare() re-invocation

```yaml
task: Fix agent-pipeline reliability gaps in finalize/success contract
batch: "'Review CLI finalize: drop prepare() re-invocation'"
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-review-plan-flow.py test-review-discussion-flow.py
depends-on: []
```

## Batch Scope

This batch fixes Gap C across all three review CLIs: `millpy-review-code.py`, `millpy-review-plan.py`, and `millpy-review-discussion.py`. Each CLI's finalize stage currently re-invokes `prepare()` to obtain `round_n` and `reviews_dir`. The fix adds a `--round` CLI arg and derives `reviews_dir` from config, eliminating the prepare re-invocation. The backend `finalize()` function signatures are unchanged — only the CLI frontend changes. Discussion-review differs from code/plan review in its finalize signature: no `scope` or `git_root` params. Read the backend signature carefully before editing.

This batch is independent of Batch 1 and can run in parallel. Batch 3 (SKILL.md) and Batch 4 (tests) both consume this batch's changes.

## Cards

### Card 3: Fix millpy-review-code.py finalize stage (Gap C)

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add `--round` argument to the argparser (alongside the existing `--stage` and `--agent-output` args): `parser.add_argument("--round", type=int, default=None, help="Review round number from prepare envelope; required for finalize stage.")`.
  - Add `resolve_path` to the existing `from _review_common import ReviewError, find_active_slug, load_config` import statement (add it to the list). This import is inside the lazy-import block at the top of `main()`.
  - In the `args.stage == "finalize"` branch:
    - Remove the `prepare_result = prepare(cfg, slug, ...)` call entirely.
    - Add a guard before the removed call: `if args.round is None: print_error_envelope("code", "--round is required for finalize stage"); return 1`.
    - Derive `reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)`.
    - Call `finalize(cfg, slug, raw_text, scope=args.batch, round_n=args.round, reviews_dir=reviews_dir, mill_dir=mill_dir, project_root=project_root, wiki_root=wiki_root, git_root=git_root)`. Use `reviews_dir` and `args.round` directly.
    - The `print(json.dumps(result.to_dict()))` and `return 0` lines remain.
  - The prepare stage (`args.stage == "prepare"`) and full stage (`else`) are NOT changed.
  - `_review_code.finalize` signature for reference (do not change the backend): `finalize(cfg, slug, raw_text, *, scope, round_n, reviews_dir, mill_dir, project_root, wiki_root, git_root) -> ReviewResult`.
- **Commit:** `fix(pipeline): review-code finalize uses --round arg, drops prepare() re-invocation (Gap C)`

### Card 4: Fix millpy-review-plan.py finalize stage (Gap C)

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add `--round` argument to the argparser (alongside `--stage` and `--agent-output`): `parser.add_argument("--round", type=int, default=None, help="Review round number from prepare envelope; required for finalize stage.")`.
  - `resolve_path` is already imported from `_review_common` at line 92 of `millpy-review-plan.py` (`from _review_common import ReviewError, find_active_slug, load_config, resolve_path`). No import change needed.
  - In the `args.stage == "finalize"` branch:
    - Remove the `prepare_result = prepare(cfg, slug, ...)` call entirely.
    - Add a guard: `if args.round is None: print_error_envelope("plan", "--round is required for finalize stage"); return 1`.
    - Derive `reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)`.
    - Call `finalize(cfg, slug, raw_text, scope=None, round_n=args.round, reviews_dir=reviews_dir, mill_dir=mill_dir, project_root=project_root, wiki_root=wiki_root, git_root=git_root)`.
    - Rebuild the result dict using `args.round` (not `prepare_result["round"]`): `result_dict = {"type": "plan", "round": args.round, "verdict": review_entry["verdict"], "blocking_count": review_entry["blocking_count"], "reviews": [review_entry]}`.
    - `print(json.dumps(result_dict))` and `return 0` remain.
  - The prepare stage and full stage are NOT changed.
  - `_review_plan.finalize` signature: `finalize(cfg, slug, raw_text, *, scope, round_n, reviews_dir, mill_dir, project_root, wiki_root, git_root) -> dict`. Note `scope=None` for holistic.
- **Commit:** `fix(pipeline): review-plan finalize uses --round arg, drops prepare() re-invocation (Gap C)`

### Card 5: Fix millpy-review-discussion.py finalize stage (Gap C)

- **Context:**
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add `--round` argument to the argparser: `parser.add_argument("--round", type=int, default=None, help="Review round number from prepare envelope; required for finalize stage.")`.
  - Add `resolve_path` to the existing import inside `main()`. The current lazy import is `from _review_common import ReviewError, find_active_slug, load_config`. Change it to `from _review_common import ReviewError, find_active_slug, load_config, resolve_path`.
  - In the `args.stage == "finalize"` branch:
    - Remove the `prepare_result = prepare(cfg, slug, mill_dir, project_root, wiki_root, max_rounds=args.max_rounds)` call entirely.
    - Add a guard: `if args.round is None: print_error_envelope("discussion", "--round is required for finalize stage"); return 1`.
    - Derive `reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)`.
    - Call `finalize(cfg, slug, raw_text, round_n=args.round, reviews_dir=reviews_dir, mill_dir=mill_dir, project_root=project_root, wiki_root=wiki_root)`. **Critical difference from code/plan review:** `_review_discussion.finalize` has NO `scope` parameter and NO `git_root` parameter. The call has exactly these kwargs: `round_n`, `reviews_dir`, `mill_dir`, `project_root`, `wiki_root`.
    - `print(json.dumps(result.to_dict()))` and `return 0` remain.
  - The prepare stage and full stage are NOT changed.
  - `_review_discussion.finalize` signature (read before editing): `finalize(cfg, slug, raw_text, *, round_n, reviews_dir, mill_dir, project_root, wiki_root) -> ReviewResult`. No `scope`, no `git_root`.
- **Commit:** `fix(pipeline): review-discussion finalize uses --round arg, drops prepare() re-invocation (Gap C)`

## Batch Tests

`verify:` runs the three existing review flow tests to ensure the `run()` (full-stage) path is not broken by the changes. The finalize-specific coverage (testing that `--round` is wired correctly and that `prepare()` is NOT called in finalize) lives in Batch 4's `test-review-finalize.py`. The flow tests are focused (no real LLM calls; use mocked reviewer backends) and execute quickly.
