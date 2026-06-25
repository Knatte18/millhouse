# Discussion: Fix pre-existing unit-test failures, CRLF cleanliness false-positive, and review false-BLOCKING on Go

```yaml
task: Fix pre-existing unit-test failures, CRLF cleanliness false-positive, and review false-BLOCKING on Go
slug: mill-unit-test-and-signal-accuracy
status: discussing
parent: main
```

## Problem

The mill-v2 unit-test suite has 4 of 91 test files failing on this branch, and two production "signal" gates produce false positives on Windows/Go projects. Together these erode trust in the green-bar and in mill-go's stuck/BLOCKING signals: a developer cannot tell a real regression from pre-existing noise, and Go projects get spurious BLOCKING verdicts on benign Windows file-cleanup races.

**Why now:** the suite must be green before further orchestration work lands, otherwise every downstream task inherits an ambiguous baseline. The two false-positives actively misclassify clean work as dirty (CRLF) or failing (Go verify), which can wedge autonomous mill-go runs.

The work decomposes into six concrete fixes: four failing test files plus the two named behavioral false-positives. Each was root-caused during exploration; root causes and exact file/line anchors are recorded below so the plan can be written without re-investigation.

## Scope

**In:**

- **brief_path (prod bug):** make the three review CLIs write the agent brief under the **task worktree** (`resolve_git_root()`), not the **hub root** (`resolve_hub_path()`). Fix all three: `millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py`. Extend tests so plan & code are covered, not just discussion.
- **worktree_snapshot_guard (prod behind spec):** tolerate a **fast-forward HEAD advance** that introduces no *new* working-tree dirt — emit a `fast-forward` warning instead of raising `ReviewerOverstepError`. Use the existing unused helper `_pygit2_util.is_ancestor`. Keep non-fast-forward / new-dirt cases raising.
- **CRLF cleanliness false-positive (prod):** targeted fix — write the cleanliness snapshot with `newline=""`; add `--ignore-cr-at-eol` to the `git diff` / `git diff -w` checks in `_is_formatter_drift_only`; CR-normalize the porcelain set-comparison in `_cleanliness.compute_new_dirt`. Add a regression test.
- **Go review false-BLOCKING (prod):** tighten the `_is_benign_windows_cleanup` failure-marker list from the over-broad bare `"fail"` to Go-aware specific patterns (`--- FAIL`, `panic:`, `build failed`, and the bare-`FAIL` go-test summary line) so benign Windows cleanup-race exits on Go projects are not misclassified as real failures. Add a regression test for go-test output.
- **test-review-finalize (stale test):** update the two stale assertions to match the deliberate auto-discovery contract for plan/discussion finalize (commit `8a5fefac`).
- **test-agent-mode-dispatch (test fixture):** fix the unrealistic constant-SHA mock so finalize's `git rev-parse HEAD` differs from the prepare-recorded `start_sha`.

**Out:**

- No change to the review **verdict parser** (`parse_verdict` / `parse_blocking_count` / `aggregate_verdict` in `_review_common.py`) — confirmed language-agnostic and sound.
- No change to the `verify-not-isolated` `PYTHONPATH=` gate in `_plan_validate.py` — confirmed correctly Python-gated; Go/C# already use the native runner.
- No cherry-picking from, or coordination commits into, parallel branches (`hanf/mill-implementer-and-dispatch-quality`, checkpoints, etc.). Those touched the same Go markers but are not on main and not on this branch; any overlap is resolved at merge, not pre-empted here.
- No broad EOL-normalization helper / refactor — the CRLF fix stays targeted to the three call sites.
- No changes to the no-content-commit gate, completeness gate, or dirty-tree gate themselves — all confirmed correct; only the test fixture that mis-drives one of them is fixed.

## Decisions

### finalize-round-contract

- Decision: keep the **asymmetric** finalize contract — `review-code` finalize requires `--round`; `review-plan` and `review-discussion` finalize **auto-discover** the round via `discover_round` when `--round` is absent. Update the two stale tests (`test_review_plan_finalize_round_required`, `test_review_discussion_finalize_round_required`) to assert that finalize **succeeds** without `--round` (round auto-discovered), mocking `_review_common.discover_round`.
- Rationale: commit `8a5fefac` ("review-plan --round threading") deliberately replaced the `if args.round is None: return 1` guard in plan & discussion with `discover_round`, and changed the `--round` help text to "auto-discovered when absent in finalize stage". The tests are the stale artifact, not the code.
- Rejected: (a) re-adding the `--round`-required guard to plan & discussion for uniformity — would revert an intentional change; (b) deleting the two tests — loses coverage of the auto-discovery path.

### go-false-blocking-fix-here

- Decision: fix the Go false-BLOCKING in **this** task by tightening the `_is_benign_windows_cleanup` failure-marker list, and add a regression test. Resolve any overlap with parallel branches at merge time.
- Rationale: the bare `"fail"` marker over-matches benign Go test output; none of the parallel branches that explored this are merged to main or present on this branch, so deferring would leave the bug live with no owner on the integration path. Fixing here keeps the task self-contained.
- Rejected: (a) deferring to a parallel branch — no merged owner exists; (b) cherry-picking sibling commits (`859e59ae` etc.) — drags unrelated changes and history across branches; a clean local fix plus test is simpler to review and merge.

### crlf-fix-targeted

- Decision: targeted CRLF fix at the three exact call sites — snapshot write `newline=""`, `--ignore-cr-at-eol` on the drift diffs, CR-normalized porcelain compare — plus a regression test. No shared EOL helper.
- Rationale: the failure surface is narrow and well understood; a targeted fix is lower-risk and easier to verify than introducing a new abstraction. YAGNI on the shared helper until a third call site needs it.
- Rejected: (a) snapshot-only minimal fix — leaves the `git diff -w` CR-blindness in `_is_formatter_drift_only` unaddressed; (b) shared EOL-normalization helper — over-engineering for two call sites.

### brief-path-fix-all-three

- Decision: fix the hub-vs-task brief-path bug in all three review CLIs and extend tests to cover plan & code, not just discussion.
- Rationale: the bug is identical in `millpy-review-plan.py` and `millpy-review-code.py` (they already compute `git_root` but write the brief against `project_root = resolve_hub_path()`); fixing only the tested one leaves two latent bugs. Briefs are per-task artifacts committed to the task branch (commit `f56d6f97`), so they must live in the task worktree.
- Rejected: (a) fix all three but test only discussion — leaves plan/code regressions uncaught; (b) fix only discussion — leaves two known bugs in place.

## Technical context

All paths are under `plugins/mill/scripts/` and `plugins/mill/unit_tests/` unless noted. Anchors captured during exploration (line numbers approximate — verify before editing):

**brief_path (prod):**
- `millpy-review-discussion.py` ~line 72-75 sets `project_root = hub_dir = resolve_hub_path()`; ~line 96 computes `briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")`. Change the briefs base to `resolve_git_root()` (already imported). `resolve_git_root` is the task worktree; `resolve_hub_path` is the shared hub.
- Same bug: `millpy-review-plan.py` ~line 151 and `millpy-review-code.py` ~line 150, both with `project_root = resolve_hub_path()` while `git_root` is already computed (plan ~103, code ~102) but unused for the brief.
- Helpers: `_paths.resolve_task_path` (~533-546) joins `worktree_root / cfg_relative`; `_agent_dispatch.write_brief` (~96-120) writes verbatim.
- Failing test: `test-review-cli.py` `test_discussion_prepare_brief_path_uses_git_root` (~337-426) patches `resolve_git_root -> task_root`, `resolve_hub_path -> hub_root`, asserts brief is under `task_root` and not `hub_root`.

**worktree_snapshot_guard (prod):**
- `_review_common.py` `worktree_snapshot_guard` (~124-170). Current raise condition (~159-167): `should_raise = bool(added) or head_changed or bool(removed)` where `head_changed = before_sha != after_sha`. Docstring (~142-145) and `_porcelain_diff` fallback string `"(no porcelain line diff; HEAD changed)"` (~226) encode the old all-or-nothing rule.
- Unused helper to call: `_pygit2_util.is_ancestor(path, ancestor_sha, descendant_sha)` (~211-235, exported ~318).
- Intended rule (from `test-review-guard.py`): a fast-forward HEAD advance (new HEAD is a descendant of old) that adds **no new** working-tree dirt is allowed and prints a `fast-forward` warning. Cases: B (~78-112, ff commit, clean), F (~167-202, ff with `expected_paths`), I (~234-270, prior untracked dirt committed away). Must still raise: C/D (porcelain change, HEAD same), J (~272-330, reset to non-descendant), K (~332-363, ff + new untracked `extra.txt`). Suggested: `ff = head_changed and is_ancestor(root, before_sha, after_sha)`; `should_raise = bool(added) or (head_changed and not ff) or (bool(removed) and not ff)`.

**CRLF cleanliness (prod):**
- `_cleanliness.py` `capture_snapshot` (~14-24) writes via `write_text(..., encoding="utf-8")` with no `newline=""` -> text-mode CRLF translation on Windows. `compute_new_dirt` (~27-51) reads back and set-diffs porcelain; the read path is CR-safe (`read_text` + `splitlines`) but the live `git status` / `git diff` signals are not.
- `_implementer_common.py` `_is_formatter_drift_only` (~224-287): uses `git diff` and `git diff -w`. `-w` (`--ignore-all-space`) does NOT neutralize CR-at-eol; add `--ignore-cr-at-eol` so a pure CRLF-vs-LF delta is classified as drift, not real content.
- Call sites: `capture_snapshot` from `millpy-implement.py` (~273) and `millpy-fix.py` (~212); `compute_new_dirt` from `_implementer_common.py` (~642); `_is_formatter_drift_only` invoked ~662.
- Existing tests: `test-cleanliness.py` (test #8 ~144-158 already exercises a CRLF snapshot round-trip and passes). New regression test should cover the live-status CR-only delta path, not just the snapshot read.

**Go review false-BLOCKING (prod):**
- `_implementer_common.py` `_is_benign_windows_cleanup` (~165-196), `failure_markers` (~189-193) currently `["fail", "panic:", "build failed"]`. The bare `"fail"` substring matches benign Go output, so `has_failure_marker` is True even on benign cleanup-race exits -> gate returns False -> `_run_verify_gate` (~328-390) returns `stuck_type:"verify"` (~376-380) -> mill-go BLOCKING.
- Supporting: `_has_windows_cleanup_race_signature` (~142-162) signatures `unlinkat`, `access is denied`, `winerror 5`, `winerror 32`. `_posix_shell_run_args` (~199-221) routes verify through bash; harmless to Go.
- Tighten markers to Go-aware patterns, matched **line-anchored, not as bare substrings**. Exact match semantics the plan/impl/test must share (matching stays case-insensitive on the lowercased output, as today):
  - `--- fail` — the go-test per-test failure prefix (`--- FAIL: TestName (0.00s)`). Substring match is safe because the `--- ` prefix never appears in benign log text.
  - a line whose first token is `fail` followed by a tab or space — the package-summary line `FAIL\tpkg/path\t0.12s` (here `\t` denotes a real TAB character, U+0009, not the two literal characters backslash-t). Match as the regex `(?m)^fail[\t ]` against the lowercased output, NOT the substring `"fail"`.
  - `panic:`
  - `build failed` (covers go-test's `FAIL\tpkg [build failed]` and `# pkg` build-error blocks).
  - Removed: the bare `"fail"` substring. Benign Go output such as `ok  \tpkg/failover\t0.1s` contains the substring `fail` but matches none of the above (no `--- ` prefix, the line starts with `ok` not `fail`), so it is correctly treated as benign.
- Existing tests: `test-implementer-common.py` cases 24 / 24b (win32 + cleanup signature + `--- FAIL` / bare FAIL -> stuck/verify) and 25/26 currently pass; the tightened list must keep these green and add a benign-go-output-with-"fail"-substring case that resolves to success.

**test-review-finalize (stale test):**
- `millpy-review-code.py` finalize enforces `--round` (~174-176, `print_error_envelope` + return 1). `millpy-review-plan.py` (~175-178) and `millpy-review-discussion.py` (~120-123) auto-discover via `discover_round(reviews_dir, type, "holistic")`.
- Tests to update: `test-review-finalize.py` `test_review_plan_finalize_round_required` (~150-206) and `test_review_discussion_finalize_round_required` (~362-418), plus their dispatch blocks in `main()` (~444-452, ~474-482). Invert to assert success without `--round` (mock `discover_round`). Keep `test_review_code_finalize_round_required` asserting `rc == 1`.

**test-agent-mode-dispatch (test fixture):**
- `test-agent-mode-dispatch.py` `test_implementer_parity_finalize_stage` (~253-282). The fixture's `mock_subprocess_run` (~183-188) returns a constant `stdout="abc1234\n"` for every `_subprocess_util.run`. Prepare records `start_sha = "abc1234"` (`millpy-implement.py` ~262-281); finalize reads it (~240) and the no-content-commit gate (`_implementer_common.py` `_forward_output` ~580-597) runs `git rev-parse HEAD` -> also `"abc1234"` -> `HEAD == start_sha` -> `stuck/logic`.
- Fix: make finalize's `git rev-parse HEAD` return a distinct SHA (e.g. a `side_effect` that yields `abc1234` at prepare time and a different SHA during finalize), so the gate sees a real content commit and the envelope stays `success`. Production no-content-commit gate (added `bd35e83c`) is correct and untouched.

## Constraints

- **Windows-first correctness.** All four areas are Windows-sensitive (CRLF translation, file-cleanup races, path separators). Fixes must hold on Windows cp1252; `print()`/`_log()` output stays ASCII (`--`, `->`).
- **Verify-command shape.** This is a Python project (`plugins/mill/pyproject.toml`), so plan `verify:` commands MUST start with `PYTHONPATH=` (literal, empty, single space) per CLAUDE.md, enforced by `_plan_validate.py` `verify-not-isolated`.
- **Unit tests use `uv run --project plugins/mill`** and run via `plugins/mill/unit_tests/run-all.py`; fixtures are in-memory/tempfile, no real git/LLM where avoidable. New tests follow `test-<name>.py` naming and the existing return-bool / `main()`-aggregator style in the touched files.
- **No `/tmp` / `$env:TEMP`.** Scratch goes to `.scratch/`.
- **Reuse over new abstractions** — `_pygit2_util.is_ancestor` already exists; use it rather than reimplementing ancestry.

## Testing

Per area (TDD candidates marked):

- **brief_path** — *TDD*: existing `test-review-cli.py` discussion test already encodes the contract (red now). Add parallel assertions for `millpy-review-plan.py` and `millpy-review-code.py` brief paths (under task root, not hub root). Drive prod fix to green.
- **worktree_snapshot_guard** — *TDD*: `test-review-guard.py` cases B/F/I are red now; J/K/C/D constrain the boundary. Implement the fast-forward tolerance until B/F/I pass with the `fast-forward` warning on stderr and J/K/C/D still raise. No new test file needed; the suite already specifies the contract.
- **CRLF cleanliness** — add a regression test (extend `test-cleanliness.py` and/or `test-implementer-common.py`) that simulates a CR-only delta in the live `git status` / `git diff` path and asserts `compute_new_dirt` returns `[]` and `_is_formatter_drift_only` returns `True`. Must fail before the fix, pass after.
- **Go false-BLOCKING** — add a `test-implementer-common.py` case: win32 + cleanup-race signature + benign go-test output whose only `fail` substring is inside an `ok` line (e.g. `ok  \tpkg/failover\t0.1s`, with a real TAB) and which has no `--- fail` prefix and no line beginning with `fail` followed by tab/space -> resolves to **success** (benign). Keep cases 24/24b/25/26 green: a real per-test `--- FAIL:` line and a real package-summary `FAIL\tpkg` line (line-anchored `(?m)^fail[\t ]`) must still -> stuck/verify.
- **test-review-finalize** — invert the two stale tests to assert finalize succeeds without `--round` (mock `discover_round`); keep the code-finalize `--round`-required test red-on-missing.
- **test-agent-mode-dispatch** — fix the fixture so finalize HEAD differs from prepare `start_sha`; assert the envelope is `success` with `commit_sha` and `session_id` preserved.
- **Whole-suite gate:** final acceptance is `uv run --project plugins/mill plugins/mill/unit_tests/run-all.py` green (0 of 91 failing).

## Q&A log

- **Q:** test-review-finalize `--round` contract — update stale tests vs make prod uniform vs delete? **A:** [auto-pick] Update the two stale tests to assert auto-discovery succeeds. **Why:** commit `8a5fefac` deliberately switched plan/discussion finalize to `discover_round` and changed the help text; the tests are the stale artifact, not the code.
- **Q:** Go false-BLOCKING — fix here now vs defer to a parallel branch vs cherry-pick sibling commits? **A:** [auto-pick] Fix it here now (tighten markers + regression test), resolve overlap at merge. **Why:** no parallel branch that touched this is merged to main or present here, so deferring leaves the bug live with no owner on the integration path.
- **Q:** CRLF cleanliness fix scope — targeted vs snapshot-only minimal vs broad shared helper? **A:** [auto-pick] Targeted fix at the three call sites (snapshot `newline=""`, `--ignore-cr-at-eol`, CR-normalized porcelain compare) + regression test. **Why:** narrow, well-understood failure surface; YAGNI on a shared helper for two sites.
- **Q:** brief_path fix breadth — all three CLIs + extend tests vs all three + discussion test only vs discussion only? **A:** [auto-pick] Fix all three CLIs and extend tests to cover plan & code. **Why:** the bug is identical in plan/code and currently untested; fixing only the tested one leaves two latent regressions.
- **Q:** test-agent-mode-dispatch finalize parity — prod bug or test fixture? **A:** Test fixture. **Why:** the constant-SHA mock makes finalize `HEAD == start_sha`, tripping the legit no-content-commit gate; production gate (`bd35e83c`) is correct.
```
