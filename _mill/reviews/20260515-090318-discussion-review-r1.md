I have enough to write the review now.

# Review: Make implementer model configurable via config.yaml

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-15
```

## Findings

### [NOTE] Two `run()` call sites per script, described as one
**Section:** Technical context — Config reading in the three CLI scripts
**Issue:** `millpy-implement.py` and `millpy-merge-in-subagent.py` each have two `_implementer_sonnet.run()` call sites (lines 176/249 and 111/172 respectively); the pattern block says "replace the … call" (singular), implying one per script.
**Fix:** Note that config resolution happens once, but the new `model`/`effort` kwargs must be threaded into both call sites in each script.

### [NOTE] Implement tests have no `_test_registry.write_to()` calls to update
**Section:** Testing — `test-millpy-implement.py`, `test-millpy-implement-holistic.py`, `test-millpy-merge-in-subagent.py`
**Issue:** All three test files mock `_implementer_sonnet.run` directly and never call `_test_registry.write_to()`; the phrase "Update `_test_registry.write_to()` calls" describes nonexistent calls. After the change, `_reviewers.load(wiki_path)` is called for real unless `_reviewers` is also mocked, and `make_minimal_registry` baseline doesn't include `sonnethigh` (needed for the fallback test).
**Fix:** Explicitly state that the plan should add mocks for `_reviewers.load` + `_reviewers.resolve` in these three test files (consistent with how all other external I/O is handled), rather than relying on file-based fixture setup.

## Verdict

APPROVE
Discussion is complete and technically accurate; two NOTEs are implementation-detail bookkeeping, not blocking gaps.