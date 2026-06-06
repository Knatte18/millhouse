# Batch: review-seam

```yaml
task: "Replace subprocess LLM dispatch with the Claude Code Agent tool"
batch: review-seam
number: 4
cards: 6
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-cli.py test-review-discussion-flow.py test-review-code-flow.py test-review-plan-flow.py
depends-on: [1]
```

## Batch Scope

Adds the `--stage {prepare,finalize,full}` seam to the three review CLIs by
splitting each backend `run()` at its `_reviewer_single.run()` boundary into a
per-scope `prepare` (resolve spec + render prompt + write brief) and `finalize`
(parse verdict + write the canonical review file + build the `ReviewResult`
envelope). Agent-mode review dispatch is ALWAYS single-scope per prepare/finalize
cycle (one reviewer); the SKILL targets a scope with the existing
`--batch`/`--holistic-only` flags and loops if more than one scope is enabled.
The multi-scope parallel path (plan per-batch + holistic) stays in `full` and is
subprocess/psmux-only. Decision 24 is preserved: `finalize` (Python) writes the
review file; the reviewer sub-agent only returns text. External interface for
batches 5/6: each review CLI accepts `--stage prepare` (subagent_type=
`mill-reviewer`) and `--stage finalize --agent-output <p>`, printing the same
`ReviewResult` envelope as `full`.

## Cards

### Card 14: Per-scope prepare/finalize primitives in the review backend

- **Context:**
  - `plugins/mill/scripts/_reviewer_single.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add two helpers next to `parse_verdict` / `write_review_file`
  / `ReviewResult`. `finalize_scope(reviews_dir, review_type, round_n, raw_text, *, scope=None) -> dict`
  runs `parse_verdict(raw_text)`, then `write_review_file(reviews_dir, review_type, round_n, raw_text, scope=scope)`,
  and returns the single review entry dict (`{"scope":..., "verdict":..., "file":...}`)
  plus enough for the caller to assemble `ReviewResult` (verdict + blocking/nit
  counts via the existing counting logic). Keep `write_review_file` and
  `parse_verdict` unchanged; `finalize_scope` only composes them. Add a helper
  `brief_path_for(briefs_dir, role, scope, round_n)` that mirrors
  `_agent_dispatch.write_brief`'s naming so prepare and finalize agree on the
  path. Do not change `maybe_switch_spec_for_large_prompt`; it stays callable by
  each backend's prepare. ASCII output only.
- **Commit:** `feat(review-common): add per-scope finalize_scope primitive`

### Card 15: Split `_review_discussion.run()` into prepare/finalize

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_reviewer_single.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Refactor so the existing `run()` (lines ~38-179) delegates to
  two new module functions: `prepare(cfg, slug, mill_dir, project_root, wiki_root) -> dict`
  does the path resolution, reviewer-name lookup
  (`cfg["roles"]["discussion-review"]["holistic"]["reviewer"]`),
  `_reviewers.resolve`, and prompt render (lines ~57-119), returning
  `{"prompt_text":..., "model":<spec["model"]>, "round":round_n, "reviews_dir":..., "scope":"holistic"}`;
  `finalize(cfg, slug, raw_text, *, round_n, reviews_dir, mill_dir, project_root, wiki_root) -> ReviewResult`
  runs `_review_common.finalize_scope(...)` + assembles the `ReviewResult`
  (lines ~144-178). `run()` becomes `prepare` -> `_reviewer_single.run(spec, prompt_text)`
  -> `finalize`, preserving identical behavior and the skip condition. No change
  to verdict/severity semantics.
- **Commit:** `refactor(review-discussion): split run into prepare/finalize`

### Card 16: Split `_review_code.run()` into per-scope prepare/finalize

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_reviewer_single.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Expose `prepare(cfg, slug, *, scope, ...) -> dict` and
  `finalize(cfg, slug, raw_text, *, scope, round_n, reviews_dir, ...) -> dict`
  for a SINGLE scope (`scope` is a batch name or `"holistic"`), reusing the spec
  resolution + render currently inside `run()` (lines ~193-330) and the
  parse+write currently at lines ~348-461 via `_review_common.finalize_scope`.
  Keep the existing `run()` working unchanged for `full` (it may now call the
  single-scope `prepare`/`finalize` internally for its one scope, since code
  review dispatches one reviewer per `run()` invocation -- `--batch X` or
  holistic). Apply `maybe_switch_spec_for_large_prompt` in `prepare` exactly where
  `run()` does today. `prepare` returns `model=spec["model"]`, `prompt_text`,
  `round`, `reviews_dir`, `scope`. Preserve `NEED_CONTEXT`/`--extra-file` handling
  in render.
- **Commit:** `refactor(review-code): split run into per-scope prepare/finalize`

### Card 17: Split `_review_plan.run()` into per-scope prepare/finalize

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_reviewer_single.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Expose single-scope `prepare(cfg, slug, *, scope, ...)` and
  `finalize(cfg, slug, raw_text, *, scope, round_n, reviews_dir, ...)` reusing the
  per-scope render + spec resolution and the parse/write/aggregate logic currently
  inside `run()` (the ThreadPoolExecutor fan-out and holistic call, lines ~269+).
  `run()` (the `full` path) keeps its existing multi-scope parallel behavior
  unchanged -- it may call the new single-scope helpers per scope, but the
  parallel scheduling stays only in `full`. Document in the Batch Scope that agent
  mode drives one scope per cycle (this hub disables plan batch review via
  `roles.plan-review.batch.reviewer: null`, so holistic is the only enabled scope
  in practice). `prepare` returns `model=spec["model"]`, `prompt_text`, `round`,
  `reviews_dir`, `scope`.
- **Commit:** `refactor(review-plan): split run into per-scope prepare/finalize`

### Card 18: `--stage` in the three review CLIs

- **Context:**
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `--stage {prepare,finalize,full}` (default `full`) and
  `--agent-output <path>` to all three. `full`: unchanged (call backend `run()`,
  print `result.to_dict()`). `prepare`: call the backend `prepare(...)` for the
  selected scope (discussion = holistic; code/plan = the scope implied by
  `--batch`/`--holistic-only`, defaulting to holistic), write `prompt_text` to a
  brief via `_agent_dispatch.write_brief(briefs_dir, role, scope, round_n, prompt_text)`
  where `role` is `review-discussion`/`review-code`/`review-plan`, then print the
  prepare JSON with `subagent_type="mill-reviewer"` and
  `model=_agent_dispatch.model_to_tier(prepare_result["model"])`. `finalize`: read
  `--agent-output`, call the backend `finalize(...)` (which writes the canonical
  review file under `_mill/reviews/` -- Decision 24), assemble the `ReviewResult`,
  and print the SAME envelope `full` prints. `briefs_dir =
  _paths.resolve_task_path(project_root, "_mill/briefs/")`. Keep the slug
  resolution fix already on this branch (slug from `git_root` in
  `millpy-review-discussion.py`).
- **Commit:** `feat(review-cli): add --stage prepare/finalize to review CLIs`

### Card 19: Tests for the review seam

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
  - `plugins/mill/unit_tests/test-review-cli.py`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
  - `plugins/mill/unit_tests/test-review-code-flow.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-review-common.py`: assert `finalize_scope` writes the
  review file and returns a review entry whose verdict matches `parse_verdict`. In
  each `*-flow.py`: assert (a) `prepare` renders the same `prompt_text` the `full`
  path would and writes the brief at the expected path WITHOUT calling
  `_reviewer_single.run` (guard it), and (b) `finalize` given a captured reviewer
  output reproduces the same `ReviewResult.to_dict()` envelope and the same review
  file content `full` produces. In `test-review-cli.py`: assert `--stage prepare`
  prints the prepare JSON with `subagent_type=="mill-reviewer"` and the mapped
  tier, and `--stage finalize --agent-output <fixture>` prints the canonical
  envelope. Reuse existing fixtures; keep `full`-path tests passing unchanged.
- **Commit:** `test(review-seam): cover prepare/finalize parity for reviews`

## Batch Tests

`verify:` runs the review backend + CLI + three flow tests. Contract under test:
`full` is byte-for-byte unchanged, and per-scope `prepare`+`finalize` reproduce
the `full` review file and `ReviewResult` envelope without invoking
`_reviewer_single.run` (guarded). Fixtures are in-memory/tempfile; no real LLM.
Scoped to the five review test files this batch touches.
