# Ad-hoc fix: pre-existing SHA well-formedness bug blocking batch verify

You are working in the git worktree at:
`/home/knatte/Code/millhouse/wts/mill-verify-gate-scoping-bugs`
(branch `hanf/mill-verify-gate-scoping-bugs`, parent `main`).

## Context

Batch `bug1-holistic-verify-subshell-wrap`'s own work is done and committed
(commits `50f5a141`, `db92f832`). Its `verify:` command is:

```
PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-fix.py
```

This currently fails with 5 failures, ALL unrelated to that batch's diff:

- `test_batch_happy_path`
- `test_holistic_happy_path`
- `test_stage_finalize_reads_agent_output`
- `test_nits_only_all_pushback_zero_commit_is_success_not_stuck`
- `test_nits_only_flag_appends_marker_and_flag`

All 5 fail with `AssertionError: 'stuck' != 'success'`. This has been confirmed to
reproduce identically on a clean checkout of `main`
(`/home/knatte/Code/millhouse/wts/millhouse`) with zero local modifications — this
is a genuine **pre-existing bug**, not something introduced by this task's batches.

A prior implementer's investigation (not independently verified by you — confirm
it yourself) hypothesized: mocks of `git rev-parse HEAD` in these unrelated tests
return short/fake SHA strings (e.g. `"def5678"`), and some code path in
`plugins/mill/scripts/_implementer_common.py` enforces a full 40-hex-char
well-formedness check on that value, causing the mocked calls to fail that check
and the overall implementer/finalize flow to report `stuck` instead of `success`.

## Your task

1. Independently reproduce and root-cause the failure — do not just trust the
   hypothesis above. Read the actual assertion/traceback for each of the 5 tests,
   find the SHA well-formedness check in `_implementer_common.py`, and find where
   each test's mock supplies a non-full-length SHA.
2. Decide the architecturally correct fix:
   - If the well-formedness check in `_implementer_common.py` is legitimate
     production behavior (i.e. real `git rev-parse HEAD` output is always a full
     40-char SHA, so short mock values are just sloppy test fixtures), fix the
     **test mocks** to use realistic full-length SHA strings.
   - If the check in `_implementer_common.py` is itself wrong or overly strict for
     a legitimate real-world case, fix the **production code** instead.
   - Prefer the smallest correct fix. Do not weaken the check just to make tests
     pass if real short SHAs could occur in production.
3. Apply the fix. Commit it on the current branch via the `git-commit` skill
   (small, focused commit; do not amend prior commits).
4. Run the full batch verify command and confirm ALL tests in
   `plugins/mill/unit_tests/test-millpy-fix.py` pass (not just the 5 listed):
   ```
   PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-fix.py
   ```
5. Also run `plugins/mill/unit_tests/test-implementer-common.py` (this file is
   also in this task's plan scope) to make sure your fix didn't break anything
   there:
   ```
   PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
   ```
6. Confirm `git status --porcelain --untracked-files=no` is clean (everything
   committed).

## Report format

Your final message's last line MUST be a single JSON object:

```json
{"status":"success","commit_sha":"<sha of your fix commit>","both_suites_pass":true}
```

or, if you cannot resolve it:

```json
{"status":"stuck","stuck_type":"logic","reason":"<why>"}
```

Before that JSON line, give a plain-text summary: what the actual root cause was
(confirmed, not assumed), what you changed and why, and the test run output
summary (pass counts) for both suites.
