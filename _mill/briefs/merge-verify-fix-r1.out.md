Verify passed and the fix is committed.

**Summary of root causes and fixes:**

1. `plugins/mill/unit_tests/test-fixer-env-isolation.py` — the merge changed `_llm_claude._invoke()` to return a `ReviewerCallResult` object instead of a `(text, session_id)` tuple (the codebase's own `run_implementer` was updated to unwrap `result.text, result.session_id`, per a comment at `plugins/mill/scripts/_llm_claude.py:547`). The test still destructured `_invoke()`'s return value directly, causing `cannot unpack non-iterable ReviewerCallResult object`. Fixed by dropping the tuple-unpack (the test only needs the captured `env`, not the return value).

2. `plugins/mill/unit_tests/test-guards.py` — its `no_direct_rmtree` guard does a literal regex scan for `shutil\.rmtree` across all scripts. Two new docstrings added in the merge (`plugins/mill/scripts/_long_path.py:6`, `plugins/mill/scripts/_worktree.py:232`) mentioned "shutil.rmtree" in prose, not as an actual call, tripping the guard. Fixed by rewording the docstrings ("shutil's rmtree" / "shutil's recursive-delete ... calls") so the prose no longer contains the literal pattern, without touching the guard's strictness.

3. `plugins/mill/unit_tests/test-language-skills-directive.py::test_render_fixer_brief` — `fixer-batch-brief.md` now requires a `<PRIOR_BLOCKING>` token (added alongside the merge's `NITS_ONLY_CARVEOUT` work in `millpy-fix.py`, defaulting to `"(none)"` when there is no prior digest). The test's render-token fixture didn't include it, so `_render.render` raised `Unresolved template tokens: ['PRIOR_BLOCKING']`. Fixed by adding `"PRIOR_BLOCKING": "(none)"` to the fixture's tokens dict.

Verify command now passes: `PASS -- all 111 unit tests in 12.2s`.

Files changed (all absolute paths under `/home/knatte/Code/millhouse/wts/mill-go2-fork-dispatch-reliability`):
- `plugins/mill/scripts/_long_path.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/unit_tests/test-fixer-env-isolation.py`
- `plugins/mill/unit_tests/test-language-skills-directive.py`

{"status":"success","commit_sha":"e29c1ecd7f1604fd2d8f1093927cab883c2a45ee"}
