MILL_REVIEW_BEGIN
# Review: Verify/build gates leak shell state and ignore nested Go modules

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] `_go_gate_mock` widening may break existing 66a/66b-style assertions
**Section:** Technical context ("Test infrastructure for bug 2") / Testing
**Issue:** `_go_gate_mock`'s `calls` list is currently bare argv lists (`calls[0] == ["go", "build", ...]`, verified at test-implementer-common.py:4022,4066, used across ~11 existing call sites); discussion says the mock "needs widening to also capture the `cwd` kwarg per call" but doesn't say whether this changes `calls`'s element shape (breaking every existing bare-argv assertion) or adds a separate parallel capture, leaving backward compatibility unresolved.
**Fix:** Add a `### Decision:` specifying the widened shape (e.g. new optional `cwd_calls` list alongside unchanged `calls`, vs. changing `calls` to `(argv, cwd)` tuples and updating all existing assertions).

### [GAP] No test candidate for the "remaining-subpath-under-nested-root" pattern branch
**Section:** Decisions (`bug2-nested-module-cwd-and-pattern`) / Testing
**Issue:** The decision defines two pattern outcomes when a nested module is found — `./...` when the affected dir *is* the module root, else `./<remaining-subpath>/...` — but the Testing section's only nested-module TDD candidate uses `plugins/foo/bar.go` directly inside `plugins/foo/go.mod` (the "is the module root" case); the subpath-derivation branch (e.g. a changed file under `plugins/foo/sub/`) has no named test case.
**Fix:** Add a TDD candidate with the transitioned file one level below the nested module root, asserting pattern `./sub/...` (not `./plugins/foo/sub/...`) and `cwd=project_root/plugins/foo`.

## Verdict

GAPS_FOUND
Two gaps: mock-widening backward compatibility unresolved, and one pattern-derivation branch untested.
MILL_REVIEW_END
