MILL_REVIEW_BEGIN
# Review: Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: plan/
date: 2026-07-28
```

## Findings

### [BLOCKING] Card 7 omits `_implementer_common.py` from Context
**Location:** Batch 2 (merge-in-marker-verification) / Card 7
**Issue:** Requirements directs adding `_extract_status_json` to the `from _implementer_common import ...` line and calling `_implementer_common._extract_status_json(output)`, but Card 7's `Context:` is `none` and `Edits:` is only `millpy-merge-in-subagent.py` — the file defining that function is listed nowhere.
**Fix:** Add `plugins/mill/scripts/_implementer_common.py` to Card 7's `Context:` (Card 8 already does this correctly for the same function).

### [BLOCKING] Cards 9–11 omit `millpy-merge-in-subagent.py` from Context
**Location:** Batch 2 / Cards 9, 10, 11
**Issue:** All three test cards have `Context: none` yet require reading module-level state from `millpy-merge-in-subagent.py`: Card 9 calls `millpy_merge_in_subagent._verify_conflict_markers(...)` directly, Card 10 patches `millpy_merge_in_subagent._verify_conflict_markers` and asserts on gate wiring, Card 11 drives `main()`'s new finalize-stage guards. None of this is verifiable without opening that file.
**Fix:** Add `plugins/mill/scripts/millpy-merge-in-subagent.py` to `Context:` for Cards 9, 10, 11 — contrast Batch 1 Cards 3–5, which correctly list the module under test.

### [BLOCKING] Card 10 misdescribes two tests' current mocks; both will break
**Location:** Batch 2 / Card 10
**Issue:** Card 10 claims `test_1_conflicts_success`, `test_15_stage_finalize_conflicts`, `test_16_...`, `test_17_...`, and `test_19_finalize_conflicts_accepts_parity_flags` all currently mock `_subprocess_util.run` with a constant `return_value=`. That's true for `test_1`/`16`/`17`, but `test_15_stage_finalize_conflicts` has no such mock at all, and `test_19` instead mocks `finalize_from_output` itself, with a comment explicitly noting this avoids "real git operations on a non-repo temp directory" (`self.tmp_path` is never `git init`'d in `setUp`). Once Cards 7–8 wire the gate into the finalize path, both tests will make a real, unmocked `git diff ...` call against that non-repo tempdir, producing `"fatal: not a git repository"` — which Card 6's own design converts to `stuck`, breaking `test_15`'s `status == "success"` assertion and, for `test_19`, preventing `finalize_from_output` from ever being called (breaking `mock_finalize.assert_called_once()`).
**Fix:** Extend Card 10 to add real `_subprocess_util.run` `side_effect` mocking (matching the other three tests) to `test_15_stage_finalize_conflicts` and `test_19_finalize_conflicts_accepts_parity_flags`, rather than assuming a `return_value=` mock already exists there to "convert."

### [BLOCKING] Card 16's `_setup_trio` return-tuple is misdescribed
**Location:** Batch 4 (dirty-parent-worktree-preflight) / Card 16
**Issue:** Card 16 says the fresh trio unpacks as `(hub, worktree, child_worktree, child_branch)`. The actual helper (`test-merge.py:89`, docstring and `return` at line 264) returns `(hub, wiki_path, worktree, slug)` — there is one worktree (not two), and the branch is `f"test/{slug}"`, not the bare slug. Following the card literally would bind `wiki_path` to a variable named `worktree` and use the bare slug as a branch name in `git merge --squash child_branch`, which does not exist.
**Fix:** Correct Card 16 to unpack `(hub, wiki_path, worktree, slug)` and derive `child_branch = f"test/{slug}"` before using it.

### [NIT] Cards 7–8 don't spell out the no-JSON extraction case
**Location:** Batch 2 / Cards 7, 8
**Issue:** Both cards gate on `_extract_status_json(output)`'s `"status"` being `"success"` vs. not, but `_extract_status_json` can also return `None` (no valid JSON found); neither card states this is treated as "not success."
**Fix:** State explicitly that a `None` extraction skips the gate and falls through, same as a non-`"success"` status.

## Verdict

REQUEST_CHANGES
Four BLOCKING gaps: two Context-completeness omissions, a test-mocking bug breaking two tests, and a misdescribed helper return tuple.
MILL_REVIEW_END
