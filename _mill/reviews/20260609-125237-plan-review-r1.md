The overview structure matches the reference exactly: `verify: null` at plan level, per-batch verify in the Batch Index. The DAG is a single batch with `depends-on: []`, no cycle, file `01-fix-and-test.md` exists. Consistent.

Now one important verify-shape check: the batch verify uses `PYTHONPATH= uv run --project plugins/mill python ...`. Per CLAUDE.md, unit tests use `uv run --project plugins/mill`, and the verify must start with `PYTHONPATH=`. This matches the reference plan. Good.

Let me check one remaining concern: the `verify` runs the whole test file via `python plugins/mill/unit_tests/test-review-cli.py` rather than `run-all.py`. The reference uses `run-all.py --only`. Let me confirm whether running the file directly works — it has `if __name__ == "__main__": sys.exit(main())`. That works standalone. The batch scope justifies this choice. This is a stylistic deviation but functionally valid.

Let me verify there are no issues with the test's mock of `_review_discussion.prepare` returning a dict without `model` being run through — already confirmed it has `model`. Let me also confirm `_review_discussion` is importable as a module attribute target. The CLI does `from _review_discussion import prepare, finalize, run`. Mocking `_review_discussion.prepare` patches the module attribute before the `from` import binds it inside `main()`. Good.

I have enough to render the review. Let me do a final check on whether the test correctly handles that `find_active_slug` is mocked but `args.slug` is None (so `find_active_slug` is called) — yes, `main(["--stage", "prepare"])` has no `--slug`, so `args.slug` is None and `find_active_slug` mock is used. Correct.

One subtle gap: the plan's Card 2 mocks `_paths.resolve_hub_path` → `hub_root` and `_paths.resolve_wiki_path` → `wiki_root`, but does NOT mock `_config`/`load_config`'s internal behavior beyond mocking `_review_common.load_config`. Since `load_config` is fully mocked to return `cfg_dict`, the real `_config.load_config` is bypassed. Good. And `resolve_wiki_path(git_root)` is mocked. Good.

All checks pass. Rendering the review.

MILL_REVIEW_BEGIN
# Review: Fix millpy-review-discussion to write briefs to the task worktree — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-09
```

## Findings

### [NIT] Verify runs file directly, not via run-all.py
**Location:** Batch 1 / Batch Index verify
**Issue:** `verify` invokes `python plugins/mill/unit_tests/test-review-cli.py` directly rather than the repo-standard `run-all.py --only test-review-cli.py` used by sibling plans; the file's `__main__` guard makes direct invocation work, but it bypasses run-all's harness conventions.
**Fix:** Optionally switch to `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-cli.py` for consistency; current form is functionally valid.

### [NIT] hub_root-substring assertion is slightly brittle
**Location:** Batch 1 / Card 2 requirement (the `str(hub_root) in brief_path_str` regression guard)
**Issue:** `hub_root = tmp/wts/millhouse` and `task_root = tmp/wts/my-slug` share the `tmp/wts/` prefix; the guard relies on the distinct trailing segment, which is correct here, but a future fixture renaming could make the substrings overlap.
**Fix:** Acceptable as-is; the two leaf names differ so the check is sound. No change required.

## Verdict

APPROVE
Fix direction, mock targets, signatures, DAG, and decision alignment all verified correct against source.
MILL_REVIEW_END
