# Batch: unit-tests-plan

```yaml
task: 'Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran'
batch: unit-tests-plan
number: 6
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-common.py
depends-on: [1, 3, 4]
```

## Batch Scope

This batch adds the unit tests covering the plan-review `--reviewer` override's holistic scope (batch `plan-review-cli`, which itself depends on `reviewer-override-helper`) and the `reviewer_self_id` round-trip through `_review_common.py` (batch `reviewer-self-id-templates`), hence its dependency on batches 1, 3, and 4. It is split out from `unit-tests-discussion` purely to keep each batch's context estimate under `pipeline.max_batch_context_tokens` — `test-review-plan-flow.py` and `test-review-common.py` are large files, and combining all six test cards into one batch pushed the estimate over the 120000-token cap. All new tests use the in-memory/tempfile fixture style already established in the touched files (`_test_helpers.safe_temp_dir()`, `_test_registry.write_to()`, `_reviewer_test_stub`); no real git remote, no real LLM, no network calls.

Card 17 (the `run()`-level large-prompt-skip test) distinguishes which reviewer spec actually dispatched via `_reviewer_test_stub.captured_prompts()`, using the same `effort`-field distinguishing technique as `unit-tests-discussion`'s Card 15 — this relies on batch `reviewer-override-helper`'s Card 2 fix (`_reviewer_single.py` forwarding `effort=spec.get("effort")` to the `test_stub` provider branch), which is why this batch depends on batch 1 in addition to batches 3 and 4.

## Cards

### Card 16: `_review_plan.py::prepare()` holistic `reviewer_override` unit tests

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-large-prompt-switch.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change the existing `from _review_plan import run as plan_run` import line to also import `prepare as plan_prepare`. Add five new checks to `main()`, each using `_make_plan_fixture(tmp_path, [("01-setup", "01-setup.md", [], [])])` (a minimal single-batch fixture, matching this file's existing minimal-fixture calls) and `os.chdir(project_root)` / `finally: os.chdir(orig_dir)`, incrementing the file's existing `errors` accumulator, printing `PASS`/`FAIL` in this file's established style. Every new `cfg` dict sets `cfg["roles"]["plan-review"]["holistic"]["reviewer"]` to a deliberately-wrong name:
  1. Extend the registry (`_test_registry.write_to(wiki_root, **{"override-reviewer": {"type": "single", "provider": "claude", "model": "claude-opus-4-1", "effort": "max", "tooluse": False}})`); call `plan_prepare(cfg, SLUG, scope=None, mill_dir=mill_dir, project_root=project_root, wiki_root=wiki_root, git_root=project_root, reviewer_override="override-reviewer")` (`git_root=project_root` because `_make_plan_fixture` builds a flat, non-nested layout where the git toplevel and the mill hub are the same directory); assert `result["model"] == "claude-opus-4-1"` and `result["effort"] == "max"`.
  2. Call `plan_prepare(cfg, SLUG, scope=None, mill_dir=mill_dir, project_root=project_root, wiki_root=wiki_root, git_root=project_root, reviewer_override="does-not-exist")`; assert `ReviewError` (imported from `_review_common`, already imported in this file) mentioning "Unknown reviewer".
  3. Extend the registry with a cluster entry, mirroring `plugins/mill/unit_tests/test-large-prompt-switch.py`'s `_make_registry_with_cluster` helper's shape (one `worker_single` single entry plus one `type: cluster` entry referencing it, with `workers: {use: "worker_single", count: 3}` and `handler: {use: "worker_single"}`); call `plan_prepare(..., reviewer_override="<cluster-entry-name>")`; assert `ReviewError` mentioning "cluster".
  4. Set `cfg["roles"]["plan-review"]["holistic"]["large_prompt"] = {"threshold_ktok": 0, "reviewer": "large-prompt-reviewer"}`; extend the registry with `override-reviewer` (as in check 1) and a distinct `large-prompt-reviewer` (`type: single, provider: claude, model: "claude-haiku-4-5-20251001", tooluse: False`); call `plan_prepare(..., reviewer_override="override-reviewer")`; assert `result["model"] == "claude-opus-4-1"`.
  5. Call `plan_prepare(cfg, SLUG, scope="01-setup", mill_dir=mill_dir, project_root=project_root, wiki_root=wiki_root, git_root=project_root, reviewer_override="override-reviewer")` (per-batch scope, with `cfg["roles"]["plan-review"]["batch"]["reviewer"]` left at the fixture's normal `"test_stub"` value); assert no exception is raised and `result["model"] is None` (the `test_stub` synthetic spec has no `model` key — proving the batch-scope reviewer resolved from config, not from `reviewer_override`, which is silently ignored outside holistic scope per the overview's holistic-only Decision) and `result["scope"] == "01-setup"`.
- **Commit:** `mill: add prepare()-level reviewer_override unit tests for _review_plan.py holistic scope`

### Card 17: `_review_plan.py::run()` holistic `reviewer_override` unit tests

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
  - `plugins/mill/unit_tests/test-reviewers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add four new checks to `main()` (same fixture/accumulator/PASS-FAIL conventions as Card 16), calling `plan_run` (already imported as `plan_run` in this file) with `holistic_only=True` on every call (skips the per-batch `ThreadPoolExecutor` path entirely, so only one stub response needs seeding per check) and a `reviewer_override` keyword argument, same deliberately-wrong `cfg["roles"]["plan-review"]["holistic"]["reviewer"]` pattern:
  1. Extend the registry with `override-reviewer` (`type: single, provider: test_stub, model: "unused-test-stub-model", tooluse: False`); `stub.seed([(APPROVE_TEXT, "sid-run-plan-override")])`; call `plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, holistic_only=True, reviewer_override="override-reviewer")`; assert `r.verdict == "APPROVE"`.
  2. Call `plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, holistic_only=True, reviewer_override="does-not-exist")` with no `stub.seed(...)` call; assert `ReviewError` mentioning "Unknown reviewer".
  3. Extend the registry with `gemini-reviewer` (`type: single, provider: gemini, model: "gemini-2.5-flash", tooluse: False`); monkeypatch `_llm_gemini.run_bulk` for the duration of this check only, mirroring `plugins/mill/unit_tests/test-reviewers.py`'s `test_single_gemini_bulk_mode` save/restore pattern (`import _llm_gemini as llm_gemini; original = llm_gemini.run_bulk; llm_gemini.run_bulk = lambda prompt_text, **kw: (APPROVE_TEXT, "sid-gemini"); try: <call>; finally: llm_gemini.run_bulk = original`); call `plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, holistic_only=True, reviewer_override="gemini-reviewer")`; assert `r.verdict == "APPROVE"`.
  4. Set `cfg["roles"]["plan-review"]["holistic"]["large_prompt"] = {"threshold_ktok": 0, "reviewer": "large-prompt-reviewer"}`; extend the registry with `override-reviewer` (`effort: "max"`) and `large-prompt-reviewer` (`effort: "low"`), both `provider: test_stub, model: "unused-test-stub-model", tooluse: False`; `stub.seed([(APPROVE_TEXT, "sid-run-plan-large-prompt")])`; call `plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, holistic_only=True, reviewer_override="override-reviewer")`; assert `r.verdict == "APPROVE"` AND `stub.captured_prompts()[-1][1]["effort"] == "max"` (this assertion depends on batch `reviewer-override-helper`'s Card 2 fix, which forwards `effort` to the `test_stub` provider branch).
- **Commit:** `mill: add run()-level reviewer_override unit tests for _review_plan.py holistic scope`

### Card 18: `reviewer_self_id` round-trip unit tests

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `main()`, immediately after the existing `# apply_actual_model_override: identity when actual_model is None` block (the block ending with `print("PASS: apply_actual_model_override identity when actual_model is None")`), add two new inline-assertion checks in this file's established style (raw string literal, `assert`, `print("PASS: ...")`):
  1. `apply_actual_model_override` leaves a `reviewer_self_id:` line untouched when rewriting `reviewer_model:`: `raw = "```yaml\nverdict: APPROVE\nreviewer_model: sonnetmax\nreviewer_self_id: claude-sonnet-4-6 (self-reported)\n```\n"`; `out = apply_actual_model_override(raw, "sonnet")`; assert `out == "```yaml\nverdict: APPROVE\nreviewer_model: sonnet\nreviewer_self_id: claude-sonnet-4-6 (self-reported)\n```\n"` (only the `reviewer_model:` line changes; `reviewer_self_id:` is byte-identical).
  2. `write_review_file` preserves a `reviewer_self_id:` line verbatim: reuse the `_test_helpers.safe_temp_dir()` + `reviews` tempdir pattern already established a few lines above in this same `main()` (the `write_review_file: creates file` block); write `write_review_file(reviews, "discussion", 2, "```yaml\nverdict: APPROVE\nreviewer_model: sonnetmax\nreviewer_self_id: claude-opus-4-1\n```\n")`; read the returned path back via `.read_text(encoding="utf-8")`; assert `"reviewer_self_id: claude-opus-4-1"` is present verbatim in the read-back content.
- **Commit:** `mill: add reviewer_self_id round-trip tests to test-review-common.py`

## Batch Tests

`verify:` runs `test-review-plan-flow.py` and `test-review-common.py` via `run-all.py --only` — exactly the two files this batch edits, covering every new test added by Cards 16-18 plus the full pre-existing suite in each file (regression coverage for batch `plan-review-cli` and the `reviewer_self_id` field added by `reviewer-self-id-templates`).
