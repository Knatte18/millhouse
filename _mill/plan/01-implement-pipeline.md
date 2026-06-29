# Batch: implement-pipeline

```yaml
task: "Fix prepare-retry atomicity, partial-batch finalize routing, and envelope field parity"
batch: "implement-pipeline"
number: 1
cards: 7
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py test-implementer-common.py test-fix-finalize.py test-finalize-cleanup.py
depends-on: []
```

## Batch Scope

This batch delivers the three implement-side pipeline fixes that all converge on
`millpy-implement.py` and its shared finalize engine `_implementer_common.py`: #568 (accept an
ignored `--round` flag), #563 (commit the prepare-stage state mutation atomically so retries do
not leave `status.md` dirty), and #570 (reclassify a partial-batch verify failure as
`stuck_type: transient` with content-commit counting, and align the existing completeness gate
to the same count). These three are grouped as one batch because two of them edit
`millpy-implement.py` and the third edits the `_implementer_common.py` helper that
`millpy-implement.py` calls; keeping them together avoids cross-batch edits to the same files
and lets the verify suite exercise every finalize consumer at once. No external interface is
produced for a downstream batch. `millpy-fix.py` is the read-only parity reference for #568 and
is never modified. Batch-local: the #570 cards introduce a shared
`_content_commit_count` helper used by both the new reclassification and the existing
`_batch_completeness_stuck` gate (see overview Shared Decisions).

## Cards

### Card 1: Accept ignored --round flag on millpy-implement.py (#568)

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-implement.py` `main()`, add a `parser.add_argument("--round", default=None, ...)` immediately after the existing `--session-id` argument (the "CLI-shape parity" block), mirroring how `millpy-fix.py` declares `--round`. The help string states it is accepted for CLI-shape parity with `millpy-fix.py` and the agent-mode dispatch loop and is ignored (the finalize branch reads `start_sha`/`implementer_session` from status.md). Do NOT reference `args.round` anywhere in the finalize branch. ASCII-only help text.
- **Commit:** `fix(implement): accept ignored --round flag for finalize parity (#568)`

### Card 2: Commit prepare state mutation atomically (#563)

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-implement.py`, replace the message-based `skip_start_commit` logic (the `last_log` computation and the `if not skip_start_commit:` add/commit/push block in the prepare/full setup path) with a staged-emptiness check. Always `git add` the status.md relative path plus the snapshot relative path; then run `git diff --cached --quiet` via `_subprocess_util.run` — when it returns a non-zero code (something is staged), call `_subprocess_util.git_commit(project_root, f"mill-go: start batch {args.batch_name}", name=git_name, email=git_email)` and then `git push origin <branch>`; when it returns 0 (nothing staged), skip both commit and push. Preserve the existing error handling (return 1 with stderr on any `git add` / `git_commit` / `git push` failure). Remove the now-unused `last_log` and `skip_start_commit` locals. This guarantees the prepare-retry's regenerated `implementer_session` write to status.md is committed on every fire, so the subsequent finalize in-scope dirty gate does not trip. Keep the commit message exactly `mill-go: start batch <name>` so `_is_only_start_batch_commit` keeps matching.
- **Commit:** `fix(implement): commit prepare state mutation atomically on retry (#563)`

### Card 3: Add _content_commit_count helper (#570)

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `_content_commit_count(project_root: Path, start_sha: str | None) -> int | None` to `_implementer_common.py`. Return `None` when `start_sha is None`. Run `git rev-list --count start_sha..HEAD` via `_subprocess_util.run`; return `None` on non-zero return code or non-numeric stdout (guard the `int()` parse exactly as `_batch_completeness_stuck` does). Then run `git log --pretty=%s start_sha..HEAD`; take the last (oldest) non-empty subject line, and when it starts with `mill-go: start batch`, subtract 1 from the count (floor at 0). Return the resulting content-commit count. Reuse the `mill-go: start batch` prefix literal already used by `_is_only_start_batch_commit`.
- **Commit:** `feat(implementer-common): add _content_commit_count helper (#570)`

### Card 4: Align _batch_completeness_stuck to content count (#570)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_batch_completeness_stuck`, replace the inline `git rev-list --count start_sha..HEAD` call and its parse with a call to `_content_commit_count(project_root, start_sha)`; when it returns `None`, return `None` (gate no-op). Keep the existing early no-ops unchanged: the `verify_cmd is not None` short-circuit, and the `start_sha is None or card_count is None or card_count <= 0` guard. Compare the content count against `card_count`; when `content < card_count`, return the stuck dict with `commits_made` set to the content count (not the raw range count). Update the reason text to say "content commit(s)" for accuracy. ASCII-only.
- **Commit:** `fix(implementer-common): count content commits in completeness gate (#570)`

### Card 5: Reclassify partial-batch verify failure at the four finalize sites (#570)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `_reclassify_verify_failure(verify_stuck: dict, project_root: Path, start_sha: str | None, card_count: int | None, session_id: str | None) -> dict` to `_implementer_common.py`. Compute `content = _content_commit_count(project_root, start_sha)`. When `content is None` or `card_count is None` or `card_count <= 0`, return `verify_stuck` unchanged. When `content == 0`, return `{"status":"stuck","stuck_type":"logic","reason":"success reported but no content commit (only batch-start commit since start_sha)","session_id": session_id or "unknown"}`. When `0 < content < card_count`, return `{"status":"stuck","stuck_type":"transient","reason": f"batch incomplete: {content} content commit(s) since start but {card_count} card(s) in batch -- implementer stopped before finishing all cards","session_id": session_id or "unknown","commits_made": content}`. When `content >= card_count`, return `verify_stuck` unchanged. Then, in `_forward_output`, at EACH of the four sites where `_run_verify_gates(...)` returns a non-None `gate_result` that is then enriched with `commit_sha` and emitted — the parsed-success path, the formatter-drift inference path, the snapshot-present clean-tree inference path, and the no-snapshot inference path — pass `gate_result` through `_reclassify_verify_failure(...)`, threading the local `start_sha`, `card_count`, and that path's session id (`_gate_session_id` in the parsed-success path, `session_id` elsewhere), before emitting. When the reclassified dict's `stuck_type` is `verify` or `transient`, keep the existing `commit_sha = git rev-parse HEAD` enrichment; when it is `logic` (the content==0 no-content case), emit without `commit_sha`, matching the sibling no-content gates. Exactly one `print(json.dumps(...))` + `return 0` per site, as today. Preserve `verify-pass-is-conclusive`: the helper only runs when verify already failed.
- **Commit:** `fix(implementer-common): reclassify partial-batch verify failure as transient (#570)`

### Card 6: Tests for --round parity and prepare-retry atomic commit (#563, #568)

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add and adjust tests in `test-millpy-implement.py`. (a) #568: add a finalize test that passes `--round 1` together with `--session-id` and `--start-sha` and asserts `main()` returns 0 (no `unrecognized arguments`) and that finalize still uses the status.md authoritative session/start_sha — mirror `test_15_stage_finalize_accepts_session_and_start_sha_flags`. (b) #563: add a test that, on a re-fire where the last commit is already `mill-go: start batch <name>` and the staged diff is non-empty (status.md dirtied by the regenerated session), `_subprocess_util.git_commit` IS called and a `git push` occurs; this requires routing the new `git diff --cached --quiet` call to return a non-zero code. UPDATE `test_skip_start_commit_on_refire`: its current `git_commit.assert_not_called()` premise is invalid under the new behavior — repoint it at the genuinely-empty staged case (mock `git diff --cached --quiet` to return code 0 → assert `git_commit` is NOT called) and treat it as guard-mechanics coverage. Keep `test_no_skip_start_commit_on_fresh_fire` green by routing its `git diff --cached --quiet` to non-zero. Extend the existing `routing_fn` mocks to handle the `diff --cached` argv.
- **Commit:** `test(implement): cover --round parity and prepare-retry atomic commit (#563, #568)`

### Card 7: Tests for partial-batch reclassification and content counting (#570)

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add tests in `test-implementer-common.py` exercising the #570 paths through `_forward_output` / `finalize_from_output`, mocking `_subprocess_util.run` so `git rev-list --count` returns a raw count and `git log --pretty=%s` returns subjects whose OLDEST line is `mill-go: start batch <name>`. (a) Partial batch: `start_sha` set, `card_count=N`, `k` content commits with `0<k<N` (raw range count `k+1`), clean non-JSON mid-work agent output (inferred-success path), verify command FAILS → assert emitted JSON is `stuck_type:transient` with `commits_made==k` (content, not `k+1`) and NOT `stuck_type:verify`. (b) Complete batch: `content>=N`, verify fails → still `stuck_type:verify`. (c) Zero-content: only the housekeeping commit, `content==0`, verify fails → `stuck_type:logic` "no content commit". (d) Squashed-but-complete: verify passes → success. Also add/adjust direct `_batch_completeness_stuck` tests so any mocked `start_sha..HEAD` range includes the housekeeping-commit subject (expected `commits_made` shifts to the content count), and add a one-card-short no-verify case (`content==N-1`) now flagged `stuck_type:transient`.
- **Commit:** `test(implementer-common): cover partial-batch reclassification and content counting (#570)`

## Batch Tests

`verify:` runs `run-all.py --only` over the four test files that exercise the edited surface:
`test-millpy-implement.py` (cards 1, 2, 6), `test-implementer-common.py` (cards 3-5, 7), plus
`test-fix-finalize.py` and `test-finalize-cleanup.py` as regression coverage. The latter two are
included because `_implementer_common.py` is a cross-cutting helper — its `_forward_output` /
`finalize_from_output` / `_batch_completeness_stuck` functions are shared by the fix and
finalize-cleanup paths — so a change there must not regress those consumers. The scope is bounded
(four named files), not the full 77-file suite, keeping each post-round verify fast. The #569
merge-in CLI is unaffected by this batch (separate parser) and is covered by batch 2.
