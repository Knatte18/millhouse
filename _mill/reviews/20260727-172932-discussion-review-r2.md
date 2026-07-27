MILL_REVIEW_BEGIN
# Review: mill-vscode/mill-spawn leak CLAUDE_CODE_CHILD_SESSION into spawned VS Code windows

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-07-27
```

## Findings

### [GAP] Blanket CLAUDE_CODE_* strip may drop legitimate persistent config
**Section:** Decisions > scrub-scope
**Issue:** Rationale asserts "no known legitimate case where a CLAUDE_CODE_* var... should leak," but the `claude` CLI documents persistent configuration vars under the same prefix (e.g. `CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX`) that users may set at shell level and expect any freshly spawned session — including these ones — to inherit.
**Fix:** Confirm against Claude Code's documented env-var surface whether any `CLAUDE_CODE_*` vars are persistent config rather than session markers; if so, narrow scrub-scope or explicitly document the accepted trade-off.

### [GAP] Shared helper name disagrees across sections
**Section:** Scope > In vs Decisions > helper-location
**Issue:** Scope/In names the new helper `_scrubbed_env()`; every other mention (Decisions > helper-location, Technical context, Testing, Q&A log) uses `scrub_env()` — a single stray, inconsistent name.
**Fix:** Correct Scope/In to `scrub_env()`.

### [GAP] Decided scrub_env() signature has no seam for Testing's "fake env dict"
**Section:** Testing vs Decisions > helper-location / env-copy-semantics
**Issue:** The pinned signature `scrub_env(prefix: str = "CLAUDE_CODE_") -> dict[str, str]` takes no env argument and reads `os.environ` directly per env-copy-semantics, but Testing's TDD plan says to "test with a fake env dict (do not mutate real os.environ in the test)" — the signature as decided has no parameter to inject that fake dict through.
**Fix:** Add an `env` parameter (defaulting to `os.environ`) to the decided signature, or change Testing to specify monkeypatch/`patch.dict` on `os.environ` instead.

### [NOTE] Test-mock kwargs-discarding claim undercounts test-millpy-terminal.py
**Section:** Technical context (existing test mocks)
**Issue:** Claims the mocks discard kwargs "or in one test-millpy-terminal.py case only cwd"; actually 5 of that file's mock lambdas keep only `cwd` (lines ~68, 122, 201, 245, 297) and 3 already capture the full kwargs dict (lines ~159, 339, 386), so those three need no signature change.
**Fix:** Correct the count so plan-writing doesn't mis-scope the mock-signature-update work in test-millpy-terminal.py.

## Verdict

GAPS_FOUND
Three GAPs: scrub-scope's legitimacy claim, a stray helper name, and a signature/testing-plan mismatch on scrub_env().
MILL_REVIEW_END
