# Discussion: Fix prepare-retry atomicity, partial-batch finalize routing, and envelope field parity

```yaml
task: Fix prepare-retry atomicity, partial-batch finalize routing, and envelope field parity
slug: mill-pipeline-finalize-gaps
status: discussing
parent: main
```

## Problem

Four independent bugs in the mill-go agent-dispatch prepare/finalize pipeline surfaced
during real mill-go runs (issues #563, #568, #569, #570). Each one wastes an orchestrator
turn or mis-routes a recoverable situation into a manual-intervention escalation:

1. **#563 — prepare-retry leaves status.md dirty.** When an implementer agent is
   interrupted and `millpy-implement.py <batch> --stage prepare` is re-run as an idempotent
   retry, it generates a fresh `implementer_session` UUID and re-records `start_sha` into
   `_mill/status.md`, but **skips committing** that mutation (the message-based
   `skip_start_commit` guard fires because HEAD is already the `mill-go: start batch <name>`
   commit from the first run). The subsequent `--stage finalize` then hits the in-scope
   dirty-tree gate and returns `stuck_type: logic` ("in-scope working tree dirty:
   [' M _mill/status.md']"), forcing a manual stage+commit.

2. **#570 — partial-batch turn-exhaustion mis-routes to `stuck_type: verify`.** When a
   multi-card implementer runs out of turn budget after committing *some* (not all) cards
   and stops with a clean non-JSON message, mill-go runs `--stage finalize`. finalize's
   inferred-success path runs the batch `verify` command (e.g. `go build ./...`) which fails
   because the partial work left the tree non-building, and returns
   `{"status":"stuck","stuck_type":"verify",...}` with **no `commits_made` field**. That
   routes to the user escalation (edit-plan/skip/block) instead of the documented
   `commits_made > 0` "re-dispatch a fresh implementer to finish the batch" path. The verify
   gate runs *before* the completeness gate, and the completeness gate is additionally
   disabled whenever a `verify_cmd` is present — so for the exact #570 scenario (a batch with
   a verify command) completeness can never fire. **Commit-count caveat (review gap):**
   `start_sha` is captured during prepare *before* the `mill-go: start batch` housekeeping
   commit (`millpy-implement.py` L277 vs L313), so a raw `git rev-list --count
   start_sha..HEAD` includes that housekeeping commit and over-counts content by one — the
   reclassification must count **content** commits, not the raw range count (see the decision
   below).

3. **#568 — `millpy-implement.py --stage finalize` rejects `--round`.** The implement
   *prepare* envelope emits a `"round": 1` field (via the shared `emit_prepare` helper), and
   the mill-go Agent-mode dispatch guidance instructs the orchestrator to "thread applicable
   prepare-envelope fields into the finalize call." Passing `--round 1` to implement finalize
   fails with `error: unrecognized arguments: --round 1`, wasting a finalize invocation.

4. **#569 — `millpy-merge-in-subagent.py --stage finalize` rejects `--session-id`.** The
   merge-in-subagent *prepare* envelope emits a `session_id` field (also via `emit_prepare`),
   but its finalize parser accepts none of `--session-id`, `--start-sha`, `--round`. Threading
   `--session-id <id>` per the generic guidance fails with `unrecognized arguments`.

**Why now:** all four were observed and filed in live runs over 2026-06-28/29 across multiple
downstream repos (loomyard, millhouse). Each is a recurring papercut that breaks the
agent-dispatch pipeline's promise that prepare/finalize is a clean two-phase contract.

## Scope

**In:**

- `plugins/mill/scripts/millpy-implement.py` — (a) #563: commit the prepare/full stage's own
  status.md + snapshot mutation atomically on every fire (fresh *and* retry); (b) #568: accept
  an ignored `--round` flag on the parser for finalize-threading parity.
- `plugins/mill/scripts/_implementer_common.py` — #570: add a shared
  `_content_commit_count(project_root, start_sha)` helper (raw range count minus the
  `mill-go: start batch` housekeeping commit); use it to reclassify a verify-gate failure at
  every verify-gate failure site in `_forward_output` (content==0 → no-content `stuck_type:
  logic`; `0 < content < card_count` → `stuck_type: transient` + `commits_made`; else pass the
  `verify` stuck through); and align the existing `_batch_completeness_stuck` gate to the same
  content-commit count so both emitters agree.
- `plugins/mill/scripts/millpy-merge-in-subagent.py` — #569: accept ignored `--session-id`,
  `--start-sha`, and `--round` flags on the parser for finalize-threading parity.
- `plugins/mill/unit_tests/` — add/adjust tests for all four fixes (see Testing).

**Out:**

- `millpy-fix.py` — already accepts `--round`, `--start-sha`, `--session-id` (it is the parity
  reference); no change.
- The shared `emit_prepare` helper and the prepare envelope shape — the chosen resolution is
  parser accept-and-ignore parity, so the envelopes keep emitting `round`/`session_id`
  unchanged. We do **not** strip fields from envelopes.
- mill-go / mill-merge-in SKILL.md docs — accept-and-ignore makes the existing generic
  "thread applicable fields" guidance correct as written; no doc edits required.
- The `verify-pass-is-conclusive` semantics — a *passing* verify still short-circuits the
  completeness heuristic; #570 only changes behavior when verify *fails* on an incomplete batch.
- The merge-in-subagent verify-fix mode finalize behavior (it re-runs verify directly and never
  threads session/round through `finalize_from_output`) — the new flags are accepted-ignored only.

## Decisions

### envelope-field-parity-resolution (#568, #569)

- Decision: Resolve by **accept-and-ignore parser parity**, not by stripping fields from
  envelopes. Add an ignored `--round` argument to `millpy-implement.py`; add ignored
  `--session-id`, `--start-sha`, and `--round` arguments to `millpy-merge-in-subagent.py`.
  Each is declared `default=None` with a help string noting it is accepted for CLI-shape parity
  and ignored (finalize reads authoritative state from status.md / re-runs verify directly).
- Rationale: `millpy-fix.py` already accepts all three ignored flags, and `millpy-implement.py`
  already accepts ignored `--start-sha`/`--session-id` with an explicit "CLI-shape parity"
  comment. Accept-and-ignore makes mill-go's generic "thread applicable prepare-envelope fields
  into finalize" guidance universally safe, requires no skill-doc surgery, and matches the
  established project pattern. Stripping fields would instead make each CLI's prepare/finalize
  contract bespoke and leave the generic guidance subtly wrong.
- Rejected: (a) stop emitting `round`/`session_id` from `emit_prepare` — would diverge the
  implement/merge envelopes from fix and break the shared helper's uniform shape; (b) edit the
  SKILL docs to scope `--round` to review CLIs only — fragile prose fix that still leaves the
  parser asymmetric and the next CLI's threading a latent bug.

### prepare-retry-atomic-commit (#563)

- Decision: In `millpy-implement.py`'s prepare/full setup path, replace the message-based
  `skip_start_commit` guard with a **staged-emptiness** check. Always `git add` status.md +
  the cleanliness snapshot, then commit **and push** only when the staged diff is non-empty
  (`git diff --cached --quiet` returns non-zero). The commit message stays
  `mill-go: start batch <name>`.
- Rationale: A retry always rewrites `implementer_session` (fresh UUID) and `start_sha`, so
  status.md is genuinely dirty and must be committed atomically — exactly as the first run
  does. Gating on "is anything actually staged" both fixes the retry (status.md changed → it
  commits) and preserves the original intent of avoiding an empty/duplicate housekeeping commit
  (truly-no-op re-run → nothing staged → skip). It is robust across multiple consecutive
  retries, unlike the message-based guard which silently re-skips every time HEAD is a
  start-batch commit.
- **Empty-staged branch is defensive-only.** `session_id = str(uuid.uuid4())`
  (`millpy-implement.py` L283) is regenerated unconditionally before `set_batch_fields` (L285),
  so status.md is dirty after *every* fire and the `git diff --cached --quiet` "nothing staged →
  skip" path never fires in normal flow. Keep the emptiness check as a defensive guard (it
  correctly avoids an empty commit should the staged content ever be identical, e.g. a future
  change that stops rewriting the session UUID), but treat it as belt-and-suspenders, not a
  reachable production retry path.
- Rejected: (a) keep the message guard but add a separate "if status.md dirty, commit it"
  branch — two code paths that can disagree; (b) use a distinct `mill-go: resume batch <name>`
  message — needless message proliferation and risks confusing `_is_only_start_batch_commit`,
  which keys on the `mill-go: start batch` prefix.

### partial-batch-verify-reclassification (#570)

- Decision: Add a single helper in `_implementer_common.py` that, given a verify-gate stuck
  result, reclassifies it to `{"status":"stuck","stuck_type":"transient","commits_made":<n>,
  "session_id":...,"reason":...}` **when** `card_count` is known and `0 < content_commits <
  card_count`. Apply it at every site in `_forward_output` where `_run_verify_gates(...)`
  returns a non-None stuck dict (the parsed-success path and all inferred-success paths). The
  reason should make clear the batch is incomplete (partial cards) so the failure is not
  mistaken for a genuine verify regression.
- **Content-commit counting (resolves review GAP).** `commits_made`/`content_commits` MUST
  exclude the `mill-go: start batch <name>` housekeeping commit. `start_sha` is recorded in
  prepare *before* that commit (`millpy-implement.py` L277 vs L313), so the raw
  `git rev-list --count start_sha..HEAD` is `content + 1` whenever the housekeeping commit
  exists. Factor this into a shared helper `_content_commit_count(project_root, start_sha) ->
  int | None`: raw `git rev-list --count start_sha..HEAD`, minus 1 when the oldest commit in
  `start_sha..HEAD` is a `mill-go: start batch` commit (inspect the tail of
  `git log --pretty=%s start_sha..HEAD`; reuse the `_is_only_start_batch_commit` prefix logic),
  else the raw count. Returns `None` on git failure or non-numeric output (safe no-op).
  Intended outcomes for an N-card batch:
  - `content_commits == 0` (only the housekeeping commit, or HEAD == start_sha): emit the
    existing no-content **`stuck_type: logic`** result ("no content commit" / "only batch-start
    commit since start_sha"). See Precedence below — the verify-failure handler must route
    this case to the no-content emit rather than leaving it as `stuck_type: verify`.
  - `0 < content_commits < N` (e.g. the common one-card-short case, content = N-1):
    **reclassify** to `stuck_type: transient` with `commits_made = content_commits`.
  - `content_commits >= N`: not partial — leave the verify failure as `stuck_type: verify`
    (genuine regression on a complete batch).
- **Precedence (resolves review GAP).** A failed verify currently returns early (parsed-success
  path `_implementer_common.py` ~L745-757; inferred paths ~L974+) **before** the no-content /
  start-batch-only checks ever run, so a zero-content + failing-verify batch would otherwise
  emit `stuck_type: verify`. The reclassification helper therefore runs **at** each verify-gate
  failure site and owns the full branch: `content_commits == 0` → emit the no-content
  `stuck_type: logic`; `0 < content_commits < card_count` → `stuck_type: transient` +
  `commits_made`; otherwise → pass the original `stuck_type: verify` through unchanged. This is
  a deliberate, narrow reordering — the no-content classification is pulled ahead of the verify
  emit, but **only on the verify-failure path** and only via the content-commit count. The
  existing no-content checks further down remain as the authority for the verify-*passing* and
  parsed-success branches; they become a no-op on the failing-verify path because the helper has
  already emitted. Make the helper emit-and-return so exactly one JSON line is printed per site.
- **Align the existing completeness gate (resolves review NOTE).** `_batch_completeness_stuck`
  (`_implementer_common.py` L77-101) currently compares the **raw** `git rev-list --count`
  against `card_count`, carrying the same housekeeping off-by-one (a one-card-short no-verify
  batch has raw count == card_count and is never flagged). Switch it to call the shared
  `_content_commit_count` helper and compare/report **content** commits, so both stuck/transient
  emitters report a consistent `commits_made` and the `< card_count` boundary is correct on the
  no-verify path too. Its existing `verify_cmd is not None` short-circuit and `None`-input
  no-ops are preserved.
- Rationale: This is the surgical fix the issue requests: a half-finished batch trivially fails
  verify, and the correct response is to re-dispatch the implementer to finish remaining cards,
  not to escalate as a plan/logic problem. Reclassifying *at the verify-failure site* preserves
  `verify-pass-is-conclusive` (the helper only runs when verify already failed) and avoids
  false-incomplete reports when an implementer legitimately squashes multiple cards into fewer
  commits and verify passes. Counting content commits (not the raw range), shared by both the
  new reclassification and the existing completeness gate, makes the `< card_count` boundary
  correct for the common one-card-short case and keeps zero-content batches on the no-content
  `stuck_type: logic` path.
- Rejected: (a) move the completeness gate before the verify gate and have it fire on
  `commits < cards` regardless of verify — would mis-report a complete-but-squashed batch
  (fewer commits than cards, verify green) as incomplete; (b) drop the `verify_cmd is not None`
  short-circuit in `_batch_completeness_stuck` outright — same false-incomplete risk on the
  success path. The reclassification only triggers on an actual verify *failure*, so a passing
  batch is never second-guessed.

## Technical context

- **Pipeline shape.** `millpy-implement.py` (and `millpy-fix.py`, `millpy-merge-in-subagent.py`)
  run in three stages: `prepare` (render brief, record state, emit a JSON envelope, dispatch a
  sub-agent), `finalize` (read the agent's captured output, run gates, emit a status JSON), and
  `full` (legacy single-process path that does both). Agent-dispatch mode uses prepare+finalize;
  mill-go threads fields from the prepare envelope into the finalize call.
- **Shared helpers** live in `plugins/mill/scripts/_implementer_common.py`:
  - `emit_prepare(briefs_dir, role, scope, round_n, prompt_text, model_tier, session_id, start_sha=None)`
    builds the prepare envelope and always includes `"round": round_n` and `"session_id":
    session_id` (this is why finalize must tolerate `--round`/`--session-id`). Do **not** change
    its signature or emitted keys.
  - `_forward_output(...)` is the finalize/success-inference engine. The verify gate is
    `_run_verify_gates(project_root, verify_cmd, module_wide_verify_cmd, git_root=...)`; it
    returns a stuck dict on failure. The completeness gate is `_batch_completeness_stuck(...)`,
    which returns `None` when `verify_cmd is not None` (verify-pass-is-conclusive) or when
    `start_sha`/`card_count` is absent or `card_count <= 0`. There are four success-emit
    branches (parsed-success at ~L744; formatter-drift inference at ~L895; snapshot-present
    clean-tree inference at ~L975; no-snapshot inference at ~L1055) — the #570 reclassification
    must be applied at the `_run_verify_gates` failure return in each.
  - `finalize_from_output(...)` reads the agent output file and delegates to `_forward_output`.
- **`millpy-implement.py` specifics.** The parser already declares ignored `--start-sha` and
  `--session-id` (lines ~92–101) with a "CLI-shape parity" comment; `--round` is the only
  missing one. The start-batch commit/push block is the `skip_start_commit` logic at lines
  ~291–330 — that is the #563 surface. `start_sha`/`implementer_session` are written via
  `_status.set_batch_fields(status_path, batch_name, {...})` (~L285). `card_count` is computed
  by counting `### Card N:` headings (~L218) and is already threaded into both the finalize and
  full `_forward_output` calls — so the #570 helper has `card_count` available.
- **`millpy-merge-in-subagent.py` specifics.** Its parser (lines ~107–143) declares
  `--mode/--files/--cmd/--checkpoint/--stage/--agent-output` only — none of `--session-id`,
  `--start-sha`, `--round`. Both `conflicts` and `verify-fix` prepare paths call `emit_prepare`,
  which emits `session_id` (#569). The finalize stage for conflicts mode delegates to
  `finalize_from_output(..., session_id=None)`; verify-fix finalize re-runs `--cmd` directly.
  The new flags are accepted-ignored only.
- **`_is_only_start_batch_commit(project_root, start_sha)`** keys on commit subjects starting
  with `mill-go: start batch`; the #563 fix keeps that message so this guard keeps working.
- ASCII-only stdout rule (CLAUDE.md): keep all new reason strings / messages ASCII.

## Constraints

- Python project: verify commands MUST be prefixed with `PYTHONPATH=` (literal, empty,
  single space) per CLAUDE.md so the test subprocess does not inherit the cache `PYTHONPATH`
  and load V2-cache modules instead of worktree code. `_plan_validate.py`'s
  `verify-not-isolated` check enforces this.
- Unit tests run via `uv run --project plugins/mill` (the documented exception to the
  `$MILL_PYTHON` cache form), discovered/executed by `plugins/mill/unit_tests/run-all.py`.
- Tests use in-memory/tempfile fixtures and mock `_subprocess_util.run` / `_implementer_claude.run`
  / `_subprocess_util.git_commit`; no real git or LLM. Preserve that style.
- Do not change `emit_prepare`'s emitted keys or signature; do not strip envelope fields.
- Keep `verify-pass-is-conclusive`: a passing verify must still short-circuit the completeness
  heuristic.

## Testing

TDD per fix; all under `plugins/mill/unit_tests/`, run with `run-all.py`.

- **#563 (`test-millpy-implement.py`).** Add a test for the retry case: HEAD already at a
  `mill-go: start batch <name>` commit (refire), `set_batch_fields` dirties status.md with a
  new session — assert that the staged-emptiness path **commits and pushes** the status.md +
  snapshot mutation (i.e. `git_commit` *is* called and a push occurs). **Update the existing
  `test_skip_start_commit_on_refire`**: its current premise (`git_commit.assert_not_called()`
  on refire) is invalidated by this fix — on a refire the new session makes status.md dirty, so
  a commit *should* now occur; re-point that test at the genuinely-empty case (nothing staged →
  no commit) or fold it into the new test. The genuinely-empty "no commit" test is
  **guard-mechanics coverage only** — in production the unconditional `uuid.uuid4()` session
  rewrite (L283) guarantees a non-empty staged diff every fire, so the empty branch is never
  hit by a real retry; the test must force an empty staged diff explicitly (mock) rather than
  rely on a refire. Keep `test_no_skip_start_commit_on_fresh_fire` (fresh fire still commits)
  green.
- **#568 (`test-millpy-implement.py`).** Add a finalize test that passes `--round 1` (alongside
  `--session-id`/`--start-sha`) and asserts the parser accepts it (rc 0, no `unrecognized
  arguments`) and that finalize still uses status.md authoritative values — mirroring the
  existing `test_15_stage_finalize_accepts_session_and_start_sha_flags`.
- **#569 (`test-millpy-merge-in-subagent.py` / `test-merge-in-subagent.py`).** Add a
  conflicts-mode finalize test passing `--session-id <id>` (and `--start-sha`, `--round`) and
  assert the parser accepts them (rc 0) and finalize proceeds normally.
- **#570 (`test-implementer-common.py`).** Add a `_forward_output` (or `finalize_from_output`)
  test where: `start_sha` set, `card_count = N`, the range `start_sha..HEAD` contains a
  leading `mill-go: start batch` housekeeping commit plus `k` content commits with `0 < k < N`
  (so the raw range count is `k + 1`), agent output is a clean non-JSON mid-work message
  (inferred-success path), and the verify command fails. Assert the emitted JSON is
  `stuck_type: transient` with `commits_made == k` (the **content** count, not the raw `k+1`)
  and a session id, **not** `stuck_type: verify` — this assertion is what catches the
  housekeeping-commit off-by-one. Add guard tests: (a) a *complete* batch (`content_commits >=
  N`) whose verify fails still reports `stuck_type: verify` (no false reclassification);
  (b) a zero-content batch (only the housekeeping commit, `content_commits == 0`) whose verify
  fails emits `stuck_type: logic` "no content commit" — this is the reachability case: the
  reclassification helper must pull the no-content emit ahead of the verify emit, so assert the
  helper, not the downstream check, produced the `logic` result; (c) a squashed-but-complete
  batch (verify passes) emits success. Mock `git log`/`git rev-list` so the housekeeping-commit
  subject is present in the range. **Also re-check/adjust existing `_batch_completeness_stuck`
  tests:** now that the gate counts content commits, any test whose mocked `start_sha..HEAD`
  range omitted the housekeeping commit must add it (or its expected `commits_made`/boundary
  shifts by one); add a one-card-short no-verify case (`content == N-1`) that the gate now
  correctly flags as `stuck_type: transient`.
- Full sweep: `uv run --project plugins/mill plugins/mill/unit_tests/run-all.py` must be green.

## Q&A log

- **Q:** How should the envelope-field parity gaps (#568 implement `--round`, #569
  merge-in-subagent `--session-id`) be resolved — accept-and-ignore the flags on the finalize
  parsers, or stop emitting the fields from the prepare envelopes? **A:** [auto-pick]
  Accept-and-ignore parser parity (add `--round` to implement; add `--session-id`/`--start-sha`/
  `--round` to merge-in-subagent). **Why:** `millpy-fix.py` already accepts all three ignored
  flags and implement already accepts ignored `--start-sha`/`--session-id` — this is the
  established pattern; it makes mill-go's generic "thread applicable fields" guidance safe with
  no doc changes and no divergence of the shared `emit_prepare` envelope shape.
- **Q:** For #570, fix by reordering the gates (run completeness before verify, unconditionally)
  or by reclassifying a verify *failure* to transient/commits_made only when the batch is
  incomplete? **A:** [auto-pick] Reclassify at the verify-failure site when `card_count` known
  and `0 < commits_made < card_count`. **Why:** preserves `verify-pass-is-conclusive` and avoids
  false-"incomplete" reports when an implementer legitimately squashes multiple cards into fewer
  commits and verify passes; only an actual verify failure on a demonstrably partial batch is
  reclassified.
- **Q:** For #563, keep the message-based `skip_start_commit` guard plus a separate "commit if
  dirty" branch, or replace it with a single staged-emptiness check (stage status.md + snapshot,
  commit+push only when the staged diff is non-empty)? **A:** [auto-pick] Replace with a single
  staged-emptiness check. **Why:** one code path that can't disagree with itself; commits the
  retry's genuine state mutation atomically, still avoids empty/duplicate housekeeping commits,
  and is robust across multiple consecutive retries (the message guard silently re-skips each
  time HEAD is a start-batch commit).
- **Q:** Should the retry state commit reuse the `mill-go: start batch <name>` message or a new
  `resume` message? **A:** [auto-pick] Reuse `mill-go: start batch <name>`. **Why:** avoids
  message proliferation and keeps `_is_only_start_batch_commit` (which keys on the
  `mill-go: start batch` prefix) working unchanged.
- **Q:** Should scope extend to `millpy-fix.py` or to editing mill-go/mill-merge-in SKILL docs?
  **A:** [auto-pick] No — `millpy-fix.py` already has full flag parity, and accept-and-ignore
  makes the generic threading guidance correct as written. **Why:** YAGNI; keep the change to the
  two affected scripts + `_implementer_common.py` + tests.
- **Q:** Should `emit_prepare` stop emitting `round`/`session_id`, or keep the envelope shape?
  **A:** [auto-pick] Keep the envelope shape unchanged. **Why:** the parser-parity resolution
  makes the emitted fields harmless; changing the shared helper would diverge implement/merge
  envelopes from fix and ripple through every caller.
