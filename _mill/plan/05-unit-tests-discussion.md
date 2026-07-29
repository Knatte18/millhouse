# Batch: unit-tests-discussion

```yaml
task: 'Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran'
batch: unit-tests-discussion
number: 5
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py test-review-discussion-flow.py
depends-on: [1, 2]
```

## Batch Scope

This batch adds the unit tests covering `_reviewers.resolve_reviewer_override` (batch `reviewer-override-helper`) and the discussion-review `--reviewer` override behavior (batch `discussion-review-cli`), hence its dependency on both. It is split out from the plan-side test batch (`unit-tests-plan`) purely to keep each batch's context estimate under `pipeline.max_batch_context_tokens` — `test-review-plan-flow.py` and `test-review-common.py` are large files, and combining all six test cards into one batch pushed the estimate over the 120000-token cap. All new tests use the in-memory/tempfile fixture style already established in the touched files (`_test_helpers.safe_temp_dir()`, `_test_registry.write_to()`, `_reviewer_test_stub`); no real git remote, no real LLM, no network calls.

Card 14 (the `run()`-level large-prompt-skip test) distinguishes which reviewer spec actually dispatched via the `_reviewer_test_stub` module's existing `captured_prompts()` API: `_reviewer_test_stub.run()` records `(prompt_text, kwargs)` per call where `kwargs["effort"]` is the dispatched spec's `effort` field (confirmed in `plugins/mill/scripts/_reviewer_test_stub.py`). The card registers two `provider: test_stub` registry entries with distinct `effort` values so a post-call assertion on `stub.captured_prompts()[-1][1]["effort"]` proves which spec was actually used, without needing to patch a real LLM provider module.

## Cards

### Card 12: `_reviewers.resolve_reviewer_override` unit tests

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add six new bare `test_*` functions to `test-reviewers.py`, following the file's existing convention (plain function, `assert` statements, ending with `print("PASS: ...")`, no return value used for pass/fail):
  - `test_resolve_reviewer_override_single_claude_happy_path`: build a registry dict with one `type: single, provider: claude, model: "claude-sonnet-4-6", effort: "max"` entry (mirror `test_resolve_single_happy_path`'s inline registry shape); call `_reviewers.resolve_reviewer_override(registry, "<that name>", reject_non_claude=True)`; assert the returned spec's `type`/`provider`/`model` match, no exception raised.
  - `test_resolve_reviewer_override_cluster_raises`: build a registry with a `type: cluster` entry (mirror `test_resolve_cluster_happy_path`'s inline registry shape: a `myworker` single entry plus a `mycluster` cluster entry referencing it); call `resolve_reviewer_override(registry, "mycluster", reject_non_claude=True)` and again with `reject_non_claude=False`; assert both raise `_reviewers.ReviewerError` mentioning "cluster" (cluster rejection applies regardless of `reject_non_claude`).
  - `test_resolve_reviewer_override_test_stub_raises`: call `resolve_reviewer_override({}, "test_stub", reject_non_claude=True)` and again with `reject_non_claude=False` (an empty registry dict is sufficient — `resolve()`'s `test_stub` special case never consults the registry); assert both raise `_reviewers.ReviewerError` (missing-model rejection applies regardless of `reject_non_claude`).
  - `test_resolve_reviewer_override_non_claude_rejected_when_reject_true`: build a registry with one `type: single, provider: gemini, model: "gemini-2.5-flash", effort: "high"` entry (mirror the `provider: gemini` shape already used in `test-reviewers.py`'s `test_single_gemini_bulk_mode`); call `resolve_reviewer_override(registry, "<that name>", reject_non_claude=True)`; assert `_reviewers.ReviewerError` is raised.
  - `test_resolve_reviewer_override_non_claude_accepted_when_reject_false`: same registry as the previous test; call `resolve_reviewer_override(registry, "<that name>", reject_non_claude=False)`; assert it succeeds (returns the spec unchanged, no exception).
  - `test_resolve_reviewer_override_unknown_name_raises`: call `resolve_reviewer_override(make_minimal_registry(), "does-not-exist", reject_non_claude=True)` (reuse the file's existing `make_minimal_registry` import); assert `_reviewers.ReviewerError` mentioning "Unknown reviewer" (propagated unchanged from `resolve()`).
  Register all six new function names in `main()`'s `tests` list, appended immediately after the existing `test_resolve_unknown_name_lists_available` entry and before the `# --- _reviewer_single tests merged from test-reviewer-single.py ---` comment.
- **Commit:** `mill: add unit tests for _reviewers.resolve_reviewer_override`

### Card 13: `_review_discussion.py::prepare()` `reviewer_override` unit tests

- **Context:**
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change the existing `from _review_discussion import run as discussion_run` import line to also import `prepare as discussion_prepare`, and add `from _review_common import ReviewError` alongside this file's existing imports. Add four new checks to `main()`, each in its own `with _test_helpers.safe_temp_dir() as tmpdir:` block using `_make_fixture(tmpdir)` and `os.chdir(project_root)` / `finally: os.chdir(orig_dir)`, incrementing the file's existing `errors` accumulator on failure and printing `PASS`/`FAIL` in this file's established style. Every new `cfg` dict sets `cfg["roles"]["discussion-review"]["holistic"]["reviewer"]` to a deliberately-wrong name (e.g. `"config-reviewer-should-not-be-used"`) so a passing test proves `reviewer_override` — not config — drove resolution:
  1. Extend the fixture's registry (`_test_registry.write_to(wiki_root, **{"override-reviewer": {"type": "single", "provider": "claude", "model": "claude-opus-4-1", "effort": "max", "tooluse": False}})`); call `discussion_prepare(cfg, SLUG, mill_dir, project_root, wiki_root, reviewer_override="override-reviewer")`; assert `result["model"] == "claude-opus-4-1"` and `result["effort"] == "max"`.
  2. Call `discussion_prepare(cfg, SLUG, mill_dir, project_root, wiki_root, reviewer_override="does-not-exist")`; assert it raises `ReviewError` (not `_reviewers.ReviewerError`) and `"Unknown reviewer"` is in `str(exc)`.
  3. Extend the registry with a cluster entry (mirror `test-large-prompt-switch.py`'s `_make_registry_with_cluster` shape: one `worker_single` single entry plus one `type: cluster` entry referencing it); call `discussion_prepare(..., reviewer_override="<cluster-entry-name>")`; assert `ReviewError` mentioning "cluster".
  4. Set `cfg["roles"]["discussion-review"]["holistic"]["large_prompt"] = {"threshold_ktok": 0, "reviewer": "large-prompt-reviewer"}`; extend the registry with both `override-reviewer` (as in check 1) and a distinct `large-prompt-reviewer` (`type: single, provider: claude, model: "claude-haiku-4-5-20251001", tooluse: False`); call `discussion_prepare(..., reviewer_override="override-reviewer")` (any non-empty `discussion.md` content is sufficient — `threshold_ktok: 0` makes `_check_large_prompt`'s `estimated_ktok >= threshold_ktok` comparison true unconditionally, confirmed in `_review_common._check_large_prompt`); assert `result["model"] == "claude-opus-4-1"` (the override's model), proving `large-prompt-reviewer` was never consulted.
- **Commit:** `mill: add prepare()-level reviewer_override unit tests for _review_discussion.py`

### Card 14: `_review_discussion.py::run()` `reviewer_override` unit tests

- **Context:**
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add four new checks to `main()` (same fixture/accumulator/PASS-FAIL conventions as Card 13, same deliberately-wrong `cfg["roles"]["discussion-review"]["holistic"]["reviewer"]` pattern), calling `discussion_run` (already imported in this file) with a `reviewer_override` keyword argument:
  1. Extend the registry with `override-reviewer` (`type: single, provider: test_stub, model: "unused-test-stub-model", tooluse: False`); `stub.seed([(APPROVE_TEXT, "sid-run-override")])`; call `discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root, reviewer_override="override-reviewer")`; assert `r.verdict == "APPROVE"` and `Path(r.reviews[0]["file"]).exists()`.
  2. Call `discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root, reviewer_override="does-not-exist")` with no `stub.seed(...)` call (resolution fails before any dispatch); assert it raises `ReviewError` (imported by Card 13) mentioning "Unknown reviewer".
  3. Extend the registry with `gemini-reviewer` (`type: single, provider: gemini, model: "gemini-2.5-flash", tooluse: False`); monkeypatch `_llm_gemini.run_bulk` for the duration of this check only, mirroring `test-reviewers.py::test_single_gemini_bulk_mode`'s save/restore pattern (`import _llm_gemini as llm_gemini; original = llm_gemini.run_bulk; llm_gemini.run_bulk = lambda prompt_text, **kw: (APPROVE_TEXT, "sid-gemini"); try: <call>; finally: llm_gemini.run_bulk = original`); call `discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root, reviewer_override="gemini-reviewer")`; assert `r.verdict == "APPROVE"` — proving `run()`'s narrower `reject_non_claude=False` validation accepts an alias `prepare()` would reject.
  4. Set `cfg["roles"]["discussion-review"]["holistic"]["large_prompt"] = {"threshold_ktok": 0, "reviewer": "large-prompt-reviewer"}`; extend the registry with two `provider: test_stub, model: "unused-test-stub-model", tooluse: False` entries distinguished only by `effort` — `override-reviewer` (`effort: "max"`) and `large-prompt-reviewer` (`effort: "low"`); `stub.seed([(APPROVE_TEXT, "sid-run-large-prompt")])`; call `discussion_run(cfg, SLUG, mill_dir, project_root, wiki_root, reviewer_override="override-reviewer")`; assert `r.verdict == "APPROVE"` AND `stub.captured_prompts()[-1][1]["effort"] == "max"` (proving `maybe_switch_spec_for_large_prompt` was skipped — the dispatched spec was `override-reviewer`'s `"max"` effort, not `large-prompt-reviewer`'s `"low"`).
- **Commit:** `mill: add run()-level reviewer_override unit tests for _review_discussion.py`

## Batch Tests

`verify:` runs `test-reviewers.py` and `test-review-discussion-flow.py` via `run-all.py --only` — exactly the two files this batch edits, covering every new test added by Cards 12-14 plus the full pre-existing suite in each file (regression coverage for batches `reviewer-override-helper` and `discussion-review-cli`).
