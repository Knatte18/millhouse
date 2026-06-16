# Discussion: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps

```yaml
task: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps
slug: mill-test-and-implementer-reliability
status: discussing
parent: main
```

## Problem

Five independent reliability and quality gaps in mill's own tooling, surfaced
by `/mill-self-report` during recent tasks and filed as GitHub issues #486,
#487, #489, #488, and #492. Two are red unit tests that fail on every
`run-all.py` run (a pre-existing ASCII-guard violation and a snapshot-guard
that never raises). One is a noisy false-positive stderr warning on clean
APPROVE reviews. The remaining two are correctness gaps in the implementer
pipeline: mill-go approves a batch on the implementer's self-reported
`success` JSON without ever re-running `verify:`, and a weak-tier implementer
was caught silently weakening test assertions to make `verify:` go green
instead of fixing the underlying bug.

**Why now:** the two failing tests mean `run-all.py` is never green, so the
suite can't be used as a clean baseline gate; the verify-gate holes let
false-success and gutted-coverage batches advance silently, which is the most
dangerous class of mill bug because nothing downstream catches it.

## Scope

**In:**

- #486 — Replace the literal U+2192 (`→`) arrows in
  `plugins/mill/unit_tests/test-claude-sub.py` (lines 775, 787) with ASCII `->`.
- #487 — Fix `_review_common.worktree_snapshot_guard` so any HEAD advance OR
  new working-tree dirt during a review window raises `ReviewerOverstepError`.
  Remove the fast-forward carve-out and its stderr warning.
- #489 — Stop `_review_common._warn_if_prose_diverges` from emitting a
  divergence warning on clean reviews: only warn when the heading count is
  > 0, and exclude the `verdict:` line from the prose scan.
- #488 — Add a verify gate to the implementer finalize path
  (`_implementer_common._forward_output`): on a self-reported `success`,
  re-run the batch `verify:` command and demote a failing verify to
  `stuck_type: verify`. Always, not only when per-batch review is disabled.
- #492 — Add an explicit anti-weakening guardrail to BOTH
  `templates/implementer-brief.md` and `agents/mill-implementer.md`: never
  relax, exclude, downgrade, or delete test assertions / allowlist entries to
  pass `verify:`; fix the harness or code, or report `stuck_type: logic`.

**Out:**

- Per-batch model-tier selection for test-authoring batches (#492 suggestion
  (b)). That needs per-batch tier plumbing in mill-plan/config — a larger
  feature, deliberately deferred. The guardrail is the lever this task pulls.
- Any change to the public `_pygit2_util.is_ancestor` helper or its test
  (`test-pygit2-util.py`). It stays; only its single callsite in
  `_review_common.py` is removed.
- A config toggle to disable the finalize verify-gate. The gate is always on.
- Reworking how `verify:` strings are executed on Windows (the `shell=True`
  cmd.exe vs POSIX `PYTHONPATH=` prefix question). The new gate mirrors the
  existing, proven pattern in `millpy-merge-in-subagent.py` verbatim; any
  pre-existing shell-portability concern is out of scope and affects both
  callsites equally.
- The merge-in verify-fix path, plan/code review backends, and mill-go SKILL
  flow beyond what the five fixes touch.

## Decisions

### 487-remove-ff-carveout

- Decision: In `worktree_snapshot_guard`, treat any HEAD change during the
  review window as an overstep. `should_raise` becomes
  `bool(added) or head_changed or bool(removed)` (after the existing
  `expected_paths` filter, which still excludes `reviews_dir`). Delete the
  `fast_forward` computation, the `_pygit2_util.is_ancestor` call, and the
  "HEAD advanced … (fast-forward; allowed)" stderr warning block. Update the
  docstring to drop the fast-forward tolerance description.
- Rationale: Reviewers run strictly read-only — the bulk/tool-use tool rules
  forbid Write/Edit/git/bash writes, and reviews run synchronously in the
  worktree, so no legitimate HEAD advance can occur during the window. The FF
  carve-out (added in commit `3af385d9` "mill-go / mill-plan loop hardening"
  with no documented justification) is exactly what masks a reviewer-authored
  commit: `git commit --allow-empty` produces a child commit that
  `is_ancestor` classifies as a tolerated fast-forward, so the guard never
  raises. The two `TestWorktreeSnapshotGuard` failures
  (`test_clean_exit_state_mutated`, `test_inner_raises_state_mutated`) encode
  the desired behaviour and become the acceptance gate.
- Rejected: (a) Narrowing the carve-out to detect reviewer-authored commits by
  author/window — more code for a scenario that should never occur. (b)
  Changing the tests to assert FF is allowed — contradicts the issue's stated
  expectation and the "fix the harness, never weaken tests" principle that
  #492 is itself about.

### 487-preserve-inner-chaining

- Decision: Keep the existing exception-chaining contract intact. When the
  wrapped block raised AND state was mutated, `ReviewerOverstepError` is raised
  `from inner_exc` (chains via `__cause__`); when state is unchanged the inner
  exception re-raises unchanged. The only change is widening `should_raise`;
  the raise/chain/re-raise structure below it is untouched.
- Rationale: `test_inner_raises_state_mutated` asserts `__cause__` is the
  `RuntimeError`, and `test_inner_raises_clean_state` asserts the bare
  `RuntimeError` propagates. Both must keep passing.
- Rejected: Rewriting the control flow — unnecessary; the bug is purely in the
  `should_raise` predicate.

### 489-warn-only-when-headings-exist

- Decision: In `_warn_if_prose_diverges`, (1) return early without warning when
  `heading_count == 0`, and (2) before scanning prose for the
  `<number> <severity>` pattern, drop any line whose stripped form starts with
  `verdict:` so the verdict line (e.g. `verdict: GAPS_FOUND`) can never be
  miscounted. The returned `parse_blocking_count` value is unchanged — this
  only governs whether the stderr warning fires.
- Rationale: The warning's genuine purpose (#225) is to catch a reviewer who
  described N findings in prose but emitted fewer `### [<severity>]` headings —
  a *missing heading*. That only makes sense when at least one heading exists.
  On a clean APPROVE with zero headings, an incidental prose mention of a
  number near a severity word is benign noise. Gating on `heading_count > 0`
  kills the false positive while preserving the missing-heading signal;
  excluding the verdict line is belt-and-suspenders for the heading-bearing
  case.
- Rejected: (a) Suppress whenever verdict is APPROVE — would need to thread the
  parsed verdict into the heuristic and loses the warning on a
  clean-looking-but-buggy review. (b) Delete the heuristic entirely — throws
  away a real (if rare) signal.

### 488-always-reverify-on-success

- Decision: In `_implementer_common._forward_output`, after a `success` status
  is determined (both the parsed-JSON `success` path AND the inferred-success
  fallback paths), re-run the batch `verify:` command. If verify is non-null
  and exits non-zero, emit `{"status":"stuck","stuck_type":"verify",...}`
  instead of `success`, including the verify output in `reason`. If
  `verify: null` (nothing to run), keep current behaviour. The verify command
  is read from the batch file's fenced-yaml frontmatter via
  `_plan_dag._read_batch_frontmatter(batch_file).get("verify")` — use `.get`,
  NOT `["verify"]`: the helper returns `{}` on missing/malformed frontmatter
  and a valid batch may omit the `verify:` key, so indexing would raise
  `KeyError`; `.get` yields `None`, which the gate treats as "nothing to run"
  (the verify:null no-op branch). Thread the verify command string into
  `_forward_output` / `finalize_from_output` as a new parameter (e.g.
  `verify_cmd: str | None`). `millpy-implement.py` resolves it in both the
  `finalize` branch (where `batch_file` is already in scope at line ~175) and
  the `full` stage before calling `_forward_output`.
- Gate locus (resolves which process runs verify): the gate executes inside
  the `finalize` (and `full`) process, against `project_root` at its CURRENT
  HEAD — i.e. after the implementer's commits, never a stale snapshot. Under
  `agent` dispatch (this repo's mode) the implementer runs out-of-process and a
  separate `--stage finalize` invocation does the gating; that finalize call
  must carry `verify_cmd`, so the agent-dispatch path is gated identically to
  the in-process `full` stage. There is no path where a `success` is emitted
  without the verify gate having run (when `verify_cmd` is non-null).
- Ordering vs formatter-drift auto-commit: in the inferred-success fallback,
  `_forward_output` may auto-commit formatter drift (`_implementer_common.py`
  ~line 269) before emitting success at line 290. The verify gate runs AFTER
  any such drift commit, against the resulting clean HEAD, so all four success
  emit points (parsed-success line 250; inferred-success lines 290, 299, 310)
  are gated uniformly on the same final state.
- Rationale: The finalize stage trusts the implementer's self-reported JSON and
  never re-runs verify. When per-batch review is disabled there is no later
  stage that re-runs verify either — and even when review IS enabled, the
  review backends read code but never execute `verify:`, so a false-success
  can still slip through. Re-running verify on every `success` claim is cheap
  insurance (one extra verify run per batch, on work the implementer already
  ran green) and closes the gap regardless of review config. This also
  partially backstops #492: a weakened-but-still-failing verify is caught,
  though weakened-and-passing tests remain a guardrail (prompt) concern.
- Rejected: (a) Only re-run when per-batch review is disabled (the issue's
  minimum) — leaves the review-enabled false-success path open and adds a
  config branch. (b) Add a config toggle — extra surface for a safety feature
  that should always be on.

### 488-verify-execution-mechanism

- Decision: Execute the verify command exactly as
  `millpy-merge-in-subagent.py` does (lines 175–194):
  `subprocess.run(verify_cmd, shell=True, capture_output=True, text=True, cwd=project_root)`;
  return code 0 = pass; non-zero → `stuck_type: verify` with
  `reason` set to the FAILURE output. Cap `reason` to the last ~2000 chars of
  `(stdout + stderr).strip()` (keep the tail — pytest/unittest summaries and
  the failing assertion live at the end), so the single-line stuck JSON that
  mill-go consumes stays bounded. This is the one intentional divergence from
  the merge-in precedent (which passes the full output); note it in the
  implementation.
- Rationale: There is an existing, working precedent for running a user
  `verify:` string from Python in this exact context; mirror it for
  consistency and to avoid inventing a second execution path.
- Rejected: Splitting the command / avoiding `shell=True` — the verify strings
  are shell command lines (pipes, env-prefix), so they need a shell; diverging
  from the merge-in pattern would be gratuitous.

### 492-anti-weakening-guardrail

- Decision: Add a short, explicit guardrail section to both
  `templates/implementer-brief.md` (the per-batch prompt) and
  `agents/mill-implementer.md` (the sub-agent definition). Wording forbids
  relaxing, excluding, downgrading, or deleting test assertions, conformance
  checks, or allowlist entries (e.g. `ExcludedPropertyNames`) in order to make
  `verify:` pass. If `verify:` fails because a test or harness is itself buggy,
  the implementer fixes the test/harness or the code under test; if it cannot,
  it reports `stuck_type: logic` — never weakens coverage to go green.
- Rationale: No mechanical gate can distinguish "legitimately edited a test"
  from "gutted a test to pass," so the lever is the implementer's instructions.
  Putting it in both places means it survives whether mill-go renders the brief
  or the agent definition is the operative prompt. Cheap, in-scope, targets the
  observed failure mode directly.
- Rejected: (a) Also raising model tier for test-authoring batches — deferred
  (see Scope/Out). (b) Brief-only — leaves the agent definition silent, a gap
  if the brief path changes.

## Technical context

- **#486** — `test-claude-sub.py:775` and `:787` contain `→` in comments. The
  ASCII guard is `test-guards.py::_check_no_unicode_arrow` (fails with
  `FAIL: U+2192 arrow found in test-claude-sub.py`). Fix is a literal
  search-and-replace of `→` with `->`; no logic change.
- **#487** — `_review_common.py:124-185` `worktree_snapshot_guard`. The
  predicate at lines 167-171 plus the `fast_forward` line 165 and warning block
  177-182 are the change site. `_capture_head_sha`/`_capture_porcelain`/
  `_filter_porcelain`/`_porcelain_diff` are unchanged. Failing tests live in
  `unit_tests/test-review-common-guard.py` (`TestWorktreeSnapshotGuard`). Guard
  callsites (`_review_code.py:421`, `_review_discussion.py:196`,
  `_review_plan.py:554`) all pass `expected_paths=[cfg["paths"]["reviews_dir"]]`
  and are unaffected. `_pygit2_util.is_ancestor` remains exported and tested.
- **#489** — `_review_common.py:1261-1302`. `_warn_if_prose_diverges` is called
  by `parse_blocking_count`, which is called twice per discussion review from
  `finalize_scope` (severity `GAP`, then `NOTE`). The regex requires a number
  token before the severity word, so the verdict line alone rarely matches; the
  `heading_count == 0` early-return is the decisive fix.
- **#488** — `_implementer_common.py:170-319`. `finalize_from_output` →
  `_forward_output`. The parsed-success emit is line 250; inferred-success
  emits are lines 290, 299, 310. `millpy-implement.py:178-200` is the finalize
  branch (has `batch_file`, `cfg`, `project_root` in scope); line 301 is the
  `full`-stage `_forward_output` call. Batch frontmatter parser:
  `_plan_dag._read_batch_frontmatter(batch_path) -> dict` (returns `{"verify":
  ...}`; treats malformed frontmatter as no verify). Verify-execution precedent:
  `millpy-merge-in-subagent.py:175-194`.
- **#492** — `templates/implementer-brief.md` (`## Verify` section ~line 58-65
  is the natural anchor) and `agents/mill-implementer.md` (line 20 area). Both
  are prompt text; `_render.render` strips the leading HTML comment from the
  template.
- **Reusable helpers:** `_subprocess_util.run` (no `shell=True` support — use
  raw `subprocess.run` for the verify command, per precedent),
  `_plan_dag._read_batch_frontmatter`, `_cleanliness.compute_scope_violations`.

## Constraints

- No `CONSTRAINTS.md` at the hub root (checked).
- **ASCII-only** in all `print()`/`_log()`/source — Windows cp1252 crashes on
  non-ASCII stdout. The `→ → ->` fix (#486) is itself an instance; do not
  introduce any new non-ASCII (use ` -- ` for em-dash, `->` for arrows) in code
  or test files. (Note: discussion/markdown prose may contain Unicode; the
  guard only scans `test-*.py`.)
- Per-batch `verify:` commands MUST start with `PYTHONPATH=` (literal, empty)
  for this Python project, and should use `run-all.py --only <files>` to scope
  to the batch's tests (the `verify-full-suite` validator warns otherwise).
- Unit tests run via `uv run --project plugins/mill` (the documented test
  exception); operational mill calls use `$MILL_PYTHON` + cache `PYTHONPATH`.
- Public API shape stays clean: thread the new `verify_cmd` parameter through
  explicitly; do not add runtime guards to "catch" wrong calls (fix callsites).

## Testing

Full-suite baseline gate after all batches: `run-all.py` must be fully green
(this is itself acceptance for #486 and #487).

- **#486** — Acceptance is `test-guards.py` PASS (no new test). The guard
  already encodes the requirement.
- **#487** — Acceptance is the existing `test-review-common-guard.py`
  `TestWorktreeSnapshotGuard` four cells all passing:
  `test_clean_exit_clean_state` (no raise), `test_clean_exit_state_mutated`
  (raises `ReviewerOverstepError`), `test_inner_raises_clean_state`
  (`RuntimeError` propagates), `test_inner_raises_state_mutated` (raises with
  `__cause__` == the `RuntimeError`). No new test file; these are TDD anchors —
  they fail now and must pass after the fix. Optionally add a case asserting a
  reviews-dir write is still tolerated via `expected_paths`.
- **#489** — Add unit tests to `test-review-common.py`: (a) clean review with
  zero `### [GAP]` headings whose prose mentions a number + severity (and/or a
  `verdict: GAPS_FOUND` line) emits NO warning; (b) a review with ≥1 heading
  whose prose count diverges from the heading count STILL emits the warning.
  Capture stderr to assert presence/absence. `parse_blocking_count`'s return
  value must be unchanged in both cases.
- **#488** — Add unit tests to `test-implementer-common.py` exercising
  `_forward_output` (or `finalize_from_output`) with the new `verify_cmd`:
  (a) `success` JSON + a verify command that exits non-zero → emitted status is
  `stuck` with `stuck_type: verify` and verify output in `reason`; (b) `success`
  JSON + a verify command that exits 0 → `success` preserved; (c)
  `verify_cmd=None` (verify: null) → current behaviour, success preserved; (d)
  the inferred-success fallback path also gated by verify. Use a tiny git repo
  fixture (mirror `test-review-common-guard.py` setUp) and trivial shell
  commands like `exit 1` / `exit 0` as the verify string. TDD candidate.
- **#492** — No automated test (prompt-text change). Acceptance: the guardrail
  text is present in both `implementer-brief.md` and `mill-implementer.md`.
  Optionally extend `test-guards.py` with a string-presence assertion that both
  files contain the prohibition, so the guardrail can't be silently dropped.

## Q&A log

- **Q:** #487 — fix the guard or change the tests? **A:** Remove the
  fast-forward carve-out; any HEAD change during a review window is an
  overstep. Reviewers are read-only, so FF tolerance only ever masked a
  reviewer commit.
- **Q:** #489 — how to kill the false-positive warning without losing its
  value? **A:** Only warn when heading_count > 0, and exclude the `verdict:`
  line from the prose scan.
- **Q:** #488 — when does finalize re-run verify? **A:** Always, on any
  `success` claim when verify is non-null; a failing verify becomes
  `stuck_type: verify`. Review never re-runs verify, so universal is the only
  robust choice.
- **Q:** #492 — how to stop test-weakening? **A:** Add the anti-weakening
  guardrail to both `implementer-brief.md` and `mill-implementer.md`. Defer the
  per-batch tier-raise suggestion as out of scope.
- **Q:** Verify-execution mechanism for #488? **A:** Mirror
  `millpy-merge-in-subagent.py`: `subprocess.run(cmd, shell=True,
  capture_output=True, text=True, cwd=project_root)`; one divergence — cap
  `reason` to the last ~2000 chars of output.
- **Q:** (review r1 GAP) How read the batch verify command safely? **A:**
  `_read_batch_frontmatter(batch_file).get("verify")` — `.get`, not `["..."]`,
  so missing/malformed frontmatter yields `None` (the verify:null no-op).
- **Q:** (review r1 GAP) Which process/HEAD runs the verify gate? **A:** The
  `finalize`/`full` process, against `project_root` at its post-implementer
  HEAD; the agent-dispatch `prepare`→`finalize` split carries `verify_cmd` so
  it is gated identically. No `success` emit bypasses the gate.
- **Q:** (review r1 NOTE) Verify vs formatter-drift commit ordering? **A:**
  Verify runs after any drift auto-commit, on the final clean HEAD; all four
  success emit points are gated uniformly.
