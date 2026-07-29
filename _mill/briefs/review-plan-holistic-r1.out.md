MILL_REVIEW_BEGIN
# Review: mill-plan/review validation false-positives, hard-fails, and truncated failure reasons — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetxhigh
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [BLOCKING] Card 7: candidates->tuples refactor leaves the hit-found append broken
**Location:** Batch 2 / Card 7 (`_review_common.py::resolve_ref_paths`)
**Issue:** Requirements change `candidates` to `(candidate, source_root)` tuples and update the `hit = next(...)` line to unpack pairs, but never touch the `if hit is not None: resolved.append(hit); continue` branch. `resolved` is `list[Path]` and this is the taken path for every already-on-disk ref (the common, non-error case) — literal implementation appends 2-tuples, corrupting `resolve_ref_paths`'s return contract for every caller.
**Fix:** Add an explicit instruction to change that line to `resolved.append(hit[0])`.

### [BLOCKING] Card 8: all_raw_refs removal leaves moves_targets_on_disk dangling
**Location:** Batch 2 / Card 8 (`_review_code.py::prepare()`)
**Issue:** Verified in source: `prepare()` references `all_raw_refs` in three places beyond its build (line ~283 `resolve_ref_paths` call, line ~301 `moves_targets_on_disk = resolve_existing_paths([t for t in moves_targets_union if t not in all_raw_refs], ...)`, line ~320 `ancestors_on_disk`). Requirements name-check only the `ancestors_on_disk` line; the `moves_targets_on_disk` comprehension still names the now-deleted `all_raw_refs`, producing a `NameError` at runtime.
**Fix:** Also rewrite the `moves_targets_on_disk` filter to `t not in other_refs and t not in context_only_refs`.

### [BLOCKING] Card 3: transcribed self-run call omits wiki_root/skip_checks, miscounts kwargs
**Location:** Batch 1 / Card 3 (SKILL.md self-run-validator instruction)
**Issue:** The real gate (`millpy-review-plan.py`) calls `validate_run(plan_dir, project_root, root=root, git_root=git_root, wiki_root=wiki_root, skip_checks=frozenset(args.skip_checks), max_cards_per_batch=..., max_batch_context_tokens=..., parent_branch=...)` — 7 keyword args including `wiki_root`. Card 3's literal proposed text has only 5 kwargs, omits `wiki_root=` and `skip_checks=` entirely, yet claims "same six keyword arguments" and separately states wiki_path is already bound (implying it belongs). As written, a self-run would hard-fail on `wiki/`-prefixed `Context:` refs that the real gate resolves fine — a false-positive of exactly the class this task exists to fix.
**Fix:** Include `wiki_root=wiki_root` (and `skip_checks=`) in the transcribed call and correct the argument count.

### [BLOCKING] Card 4: new check hardcodes root/git_root/wiki_root to None
**Location:** Batch 1 / Card 4 (`_plan_validate.py::_check_verify_excludes_edited_tagged_test`)
**Issue:** Every sibling check in this module (`_check_non_existent_path`, `_check_move_source_missing`, `_check_batch_oversized`, etc.) threads `run()`'s `root`/`git_root`/`wiki_root` into `resolve_existing_paths`. Card 4 instead specifies a fixed function signature `(batch_files, project_root)` and a literal `resolve_existing_paths([token], project_root, None, wiki_root=None, git_root=None)`, with a matching bare registration call in `run()`. For any nested-layout plan (root set, or git_root != project_root), the edited `_test.go` file will fail to resolve and the check silently no-ops — a false-negative in the check whose whole purpose is closing a silent-skip gap.
**Fix:** Add `root`/`git_root`/`wiki_root` parameters to the new function and thread `effective_root`/`git_root`/`wiki_root` through the `run()` registration call, matching every other check.

### [BLOCKING] Cards 2, 6, 10: new regression tests are never wired into their file's runner
**Location:** Batch 1 / Cards 2, 6 (`test-plan-validate.py`); Batch 2 / Card 10 (`test-review-code-flow.py`)
**Issue:** Verified in source: `test-plan-validate.py::main()` only executes functions present in its explicit `tests = [...]` list; `test-review-code-flow.py::main()` only runs standalone tests via an explicit `errors += test_xxx()` call per function (e.g. the cited `test_project_root_rebind_...` is invoked this way at line ~1622). `run-all.py` runs each file as a subprocess gated solely by `main()`'s return code. None of Cards 2, 6, or 10 instruct adding the new function(s) to that list / adding the invocation call, so as written every new regression test in this plan is dead code that silently never executes — the exact "test coverage looks present but isn't" failure mode this task is meant to eliminate.
**Fix:** Add an explicit sub-step to each card: append the new `test_<name>` function(s) to `test-plan-validate.py`'s `tests` list, and add `errors += test_context_only_gitignored_ref_soft_fails_prepare()` in `test-review-code-flow.py::main()`.

### [NIT] Card 9: "tempfile.TemporaryDirectory" convention claim is wrong for this file
**Location:** Batch 2 / Card 9 (`test-review-common.py`)
**Issue:** `test-review-common.py` exclusively uses `_test_helpers.safe_temp_dir()` (adds wiki-daemon-exit cleanup) across every existing block; grep confirms zero uses of `tempfile.TemporaryDirectory` in this file. Card 9 instructs the opposite, contradicting the overview's own "verified directly against each file's current structure" Shared Decision.
**Fix:** Use `_test_helpers.safe_temp_dir()` for the four new scenario blocks.

### [NIT] Card 10: mischaracterizes `_make_fixture`'s field placement
**Location:** Batch 2 / Card 10 (`test-review-code-flow.py`)
**Issue:** Card 10 describes alpha/beta/gamma's per-batch source file as "Edits:-listed"; `_make_fixture`'s `_make_batch_file` helper actually places it under `Context:` and hardcodes `Edits: none` (no `edits` parameter exists on that helper).
**Fix:** Correct the description to "Context:-listed" so "leave Edits: unchanged" is understood as a no-op against the fixture's hardcoded `none`, not a real value being preserved.

## Verdict

REQUEST_CHANGES
Five BLOCKING correctness gaps (broken refactors, dead-on-arrival regression tests, wrong self-run call shape) plus two NIT source-accuracy slips.
MILL_REVIEW_END
