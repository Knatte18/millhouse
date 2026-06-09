# Discussion: Fix agent-pipeline reliability gaps in finalize/success contract

```yaml
task: Fix agent-pipeline reliability gaps in finalize/success contract
slug: agent-pipeline-reliability
status: discussing
parent: main
```

## Problem

The agent-mode dispatch pipeline (dispatch: agent) uses a prepare→Agent→finalize three-stage pattern. The prepare stage renders a brief and returns a JSON envelope; mill-go calls the Agent tool; the finalize stage reads the agent output and returns a verdict JSON. Four reliability gaps were found in this pipeline that cause incorrect verdicts or fragile derivation in the finalize stage:

- **Gap A** (`millpy-fix.py`): `start_sha` is never persisted from prepare to finalize, so `finalize_from_output`'s inferred-success fallback is disabled for all fixer invocations. If the fixer agent does not emit a JSON status line, finalize emits `stuck/logic: "no structured report"` even when the fixer committed valid work.
- **Gap B** (`millpy-fix.py`): `session_id` is regenerated as a fresh UUID in finalize instead of reusing the one from the prepare stage (which was rendered into the brief). The inferred-success path would emit the wrong session_id.
- **Gap C** (`millpy-review-code.py`, `millpy-review-plan.py`, `millpy-review-discussion.py`): The finalize stage re-invokes `prepare()` to obtain `round_n` and `reviews_dir`. Under the builder lock this works, but it double-loads config and re-derives state that was already known at prepare time.
- **Gap D** (`millpy-merge-in-subagent.py`, conflicts mode): Same as Gap A — `start_sha=None, session_id=None` passed to `finalize_from_output`; inferred-success fallback disabled for conflict-resolver.

These gaps were introduced when subprocess dispatch was replaced with Agent SDK calls in commit 7ddc1e28. The implement CLI (`millpy-implement.py`) was fixed correctly (it persists `start_sha` and `session_id` in status.md); fix and merge-in-subagent were not.

## Scope

**In:**
- `millpy-fix.py`: Add `--start-sha` and `--session-id` to the finalize stage CLI; emit them in the prepare stage envelope; pass them through to `finalize_from_output`.
- `_implementer_common.py`: Add optional `start_sha: str | None = None` kwarg to `emit_prepare()`; include it in the emitted envelope when non-None. Implement.py does not pass it (backward-compatible); fix.py passes it; merge-in-subagent conflicts prepare does NOT pass it (inferred-success cannot fire there, so there is no benefit — see Scope-Out).
- `millpy-review-code.py`: Add `--round` to finalize stage; derive `reviews_dir` via `_review_common.resolve_path(cfg["paths"]["reviews_dir"], slug)`; stop re-invoking `prepare()` in finalize.
- `millpy-review-plan.py`: Same as code review.
- `millpy-review-discussion.py`: Same as code review.
- `mill-go/SKILL.md`: Amend the "Agent-mode dispatch" pattern in two places: (a) step 2 — extend the prepare-envelope parse to also extract `session_id`, `round`, and `start_sha` (the latter for fix/implementer CLIs only); (b) step 5 — document threading those extracted fields into the finalize call (`--round <round>`, `--start-sha <start_sha>`, `--session-id <session_id>` for applicable CLIs). Also update the specific dispatch subsections for fix and review CLIs to show the new finalize flags.
- `mill-start/SKILL.md`: At the two discussion-review finalize call sites (subprocess branch step 2 and agent-mode finalize), thread `--round <round>` from the prepare envelope into the finalize CLI invocation. mill-start references mill-go's pattern rather than owning its own copy; the concrete edit is at those two call sites.
- New unit tests: `test-fix-finalize.py` and `test-review-finalize.py`.

**Out:**
- `millpy-implement.py` — already correct; no changes.
- `_forward_output` / `_implementer_common.py` (logic) — no changes to the inferred-success logic itself; only `emit_prepare` signature changes.
- `_review_code.py`, `_review_plan.py`, `_review_discussion.py` backend `finalize()` functions — their signatures already accept `round_n` and `reviews_dir`; no changes needed.
- `_status.py` — no schema changes needed (start_sha is passed via CLI args, not persisted to status.md for fix/merge).
- `millpy-merge-in-subagent.py` — the `finalize_from_output(start_sha=None, snapshot_path=None, session_id=None)` call at the top of the finalize early-exit block is mode-agnostic (handles both conflicts and verify-fix before the mode branch at line 216). Leaving `start_sha=None` is intentionally correct for both modes: in conflicts mode HEAD has not moved (merge --continue runs after finalize); in verify-fix mode the finalize branch explicitly checks verify results and emits success/stuck directly, bypassing `finalize_from_output` entirely. No changes needed.
- `mill-merge-in/SKILL.md` — no changes needed (conflicts finalize is correct).
- End-to-end integration tests with real Agent tool calls.

## Decisions

### persist-start-sha-via-cli-arg

- **Decision:** Pass `start_sha` from prepare to finalize via a `--start-sha` CLI argument added to `millpy-fix.py`. The prepare stage captures `start_sha` via `git rev-parse HEAD` after its pre-commit, includes it in the prepare envelope JSON, and mill-go picks it up and passes it to the finalize call. `millpy-merge-in-subagent.py` conflicts mode is explicitly excluded: at finalize time HEAD == start_sha (the merge commit happens via `merge --continue` in the SKILL after finalize returns success), so `_forward_output`'s inferred-success branch (requires HEAD != start_sha AND clean tree) cannot fire regardless. Conflicts finalize is correct as-is.
- **Rationale:** Explicit contract — no hidden sidecar files, no status.md schema changes, no cross-stage file reads. The CLI arg approach is lighter and consistent with the SKILL's existing "pass prepare envelope fields as finalize args" pattern.
- **Rejected:** (a) Sidecar `.meta.json` next to the brief — works but creates implicit coupling via the filesystem. (b) Persist to status.md for fixer — requires new `_status.py` API for holistic scope and adds schema complexity. (c) Adding `--start-sha` to conflicts finalize — reviewer confirmed this is infeasible since the inferred-success condition (HEAD moved AND clean tree) is structurally impossible to satisfy in conflicts mode.

### session-id-via-cli-arg

- **Decision:** Add `--session-id` to the finalize stage of `millpy-fix.py` only. The prepare envelope already includes `session_id`; pass it to finalize. The finalize branch must drop the local `uuid.uuid4()` call that currently generates a fresh session_id at the top of `main()` and instead read session_id solely from `--session-id`. `millpy-merge-in-subagent.py` finalize is unchanged (inferred-success cannot fire there; no `--session-id` needed).
- **Rationale:** Completes the contract so both fields (start_sha and session_id) round-trip cleanly. Prevents the inferred-success path from emitting `session_id: "unknown"` in the future.
- **Rejected:** Using `"unknown"` as a fallback — technically acceptable today since the fixer session_id is not used by the builder for anything after finalize, but defers a correctness fix that has zero cost to implement alongside Gap A.

### round-via-cli-arg-for-review-finalize

- **Decision:** Add `--round` to the finalize stage of all three review CLIs (`millpy-review-code.py`, `millpy-review-plan.py`, `millpy-review-discussion.py`). The prepare envelope already returns `round` in its JSON; the SKILL passes it to finalize. In finalize, derive `reviews_dir` via `_review_common.resolve_path(cfg["paths"]["reviews_dir"], slug)` (not `_paths.resolve_task_path` directly — `resolve_path` applies slug substitution and active-hub resolution that the bare helper skips); do not call `prepare()`.
- **Rationale:** Eliminates the double-config-load and fragile round-re-derivation. Makes the finalize stage stateless relative to prepare's side effects. The `round` field is already in every prepare envelope, so no new serialization is needed.
- **Rejected:** Adding `--reviews-dir` as another CLI arg — over-specifying; reviews_dir is always config-derived and does not need to cross the CLI boundary. Using `_paths.resolve_task_path` directly — omits slug substitution + active-hub resolution that `_review_common.resolve_path` provides.

### no-backend-changes

- **Decision:** Do not change the backend `finalize()` function signatures in `_review_code.py`, `_review_plan.py`, or `_review_discussion.py`. They already accept `round_n` and `reviews_dir` as parameters.
- **Rationale:** The CLIs are already calling them with the right types. The only change is WHERE the CLI gets those values (from the CLI args instead of from a re-invoked prepare()).
- **Rejected:** Adding a new `finalize_from_round()` variant — unnecessary abstraction.

### unit-tests-only

- **Decision:** Write unit tests for the new finalize path logic. No integration tests with real Agent tool calls.
- **Rationale:** The gap is in Python code paths that are fully exercisable without LLM calls. `_forward_output` and `finalize_from_output` are pure-Python with git subprocess calls; the existing integration test infrastructure (real git repos in `.scratch/`) is sufficient. LLM end-to-end tests would be slow, expensive, and flaky.

## Technical context

### Prepare→Agent→finalize pattern (mill-go SKILL.md "Agent-mode dispatch")

The SKILL describes six steps:
1. Resolve dispatch mode.
2. Run CLI with `--stage prepare`; parse envelope for `brief_path`, `subagent_type`, `model` (currently — to be amended to also extract `session_id`, `round`, `start_sha`).
3. Call Agent tool with `prompt = "Read this file and follow the instructions exactly: <brief_path>"`.
4. Write Agent's final message to `<brief_path>.out.md`.
5. Run CLI with `--stage finalize` + same standard args + `--agent-output <brief_path>.out.md` (to be amended to also pass envelope-derived fields).
6. Branch on verdict.

**Two-step amendment required:** The live Agent-mode dispatch pattern has 6 steps (1: resolve dispatch mode, 2: run prepare, 3: call Agent tool, 4: capture output to `.out.md`, 5: run finalize, 6: branch on verdict). Two amendments are needed:
- **Step 2 (prepare parse):** Currently extracts only `brief_path`, `subagent_type`, `model`. Must be extended to also extract `session_id`, `round`, and `start_sha` from the prepare envelope. Without this, step 5 has no values to thread.
- **Step 5 (finalize invocation):** "Same standard arguments" refers to the original invocation args (`--batch`, `--review-file`, `--scope`, etc.), not the prepare envelope. Must be amended to document: additionally thread prepare-envelope fields into finalize — `start_sha` → `--start-sha`, `session_id` → `--session-id` (fix CLIs), `round` → `--round` (review CLIs).

### Key files

- `plugins/mill/scripts/_implementer_common.py` — `_forward_output()`, `finalize_from_output()`, `emit_prepare()`. The inferred-success fallback lives in `_forward_output`; it requires `start_sha is not None` to trigger.
- `plugins/mill/scripts/millpy-fix.py` — Gaps A and B. Per-batch: commits status + review file before dispatching. Holistic: commits status + review file. `start_sha` captured after pre-commit but not persisted.
- `plugins/mill/scripts/millpy-merge-in-subagent.py` — Gap D. Conflicts mode: calls `emit_prepare()`; `_run_conflicts()`. `start_sha` not captured in prepare.
- `plugins/mill/scripts/millpy-review-code.py` — Gap C. Finalize re-calls `prepare()` for `round_n` and `reviews_dir`.
- `plugins/mill/scripts/millpy-review-plan.py` — Gap C (same pattern as code review).
- `plugins/mill/scripts/millpy-review-discussion.py` — Gap C (same pattern).
- `plugins/mill/scripts/_review_code.py` — `finalize(cfg, slug, raw_text, scope, round_n, reviews_dir, ...)` — already parameterised.
- `plugins/mill/scripts/_review_plan.py` — `finalize(...)` — same.
- `plugins/mill/scripts/_review_discussion.py` — `finalize(...)` — same.
- `plugins/mill/integration_tests/test-agent-mode-commit-target.py` — reference integration test using real git + `_forward_output` directly; no LLM.

### `_forward_output` inferred-success contract

```
if start_sha is not None and snapshot_path is not None and snapshot_path.exists():
    new_dirt = compute_new_dirt(...)
    if new_dirt == []:
        if HEAD != start_sha:
            if tree clean: emit success
elif start_sha is not None and snapshot_path is None:
    if HEAD != start_sha:
        if tree clean: emit success
else:
    fall through to stuck/logic
```

For fix finalize, `snapshot_path` is checked for existence; if the fixer snapshot file (`_mill/.cleanliness-snapshot-fixer.txt`) exists it is passed, otherwise `None`. So the `elif` branch applies — inferred success triggers when `start_sha is not None` AND head moved AND tree is clean.

### prepare envelope structure (current)

For implement:
```json
{"stage":"prepare","brief_path":"...","subagent_type":"mill-implementer","model":"sonnet","session_id":"<uuid>","role":"implement","scope":"<batch_name>","round":1}
```

For review (code/plan/discussion):
```json
{"stage":"prepare","brief_path":"...","subagent_type":"mill-reviewer","model":"sonnet","session_id":null,"role":"review-code","scope":"<scope>","round":2}
```

For fix (after this task):
```json
{"stage":"prepare","brief_path":"...","subagent_type":"mill-implementer","model":"sonnet","session_id":"<uuid>","role":"fix","scope":"<batch_name>","round":1,"start_sha":"<sha>"}
```

For merge-in-subagent conflicts (after this task):
```json
{"stage":"prepare","brief_path":"...","subagent_type":"mill-implementer","model":"sonnet","session_id":"<uuid>","role":"merge","scope":"conflicts","round":1,"start_sha":"<sha>"}
```

### `dispatch_needed: false` (out of scope)

`emit_prepare_no_dispatch` is used only by `millpy-merge-in-subagent.py` verify-fix mode. It is handled correctly in `mill-merge-in/SKILL.md`. mill-go never calls a CLI that can return `dispatch_needed: false`; no change needed.

### Existing `millpy-implement.py` as the reference implementation

The implement CLI correctly handles the prepare→finalize boundary:
- prepare: `_status.set_batch_fields(status_path, batch_name, {"start_sha": start_sha, "implementer_session": session_id})`
- finalize: reads `batch_status.get("start_sha")` and `batch_status.get("implementer_session")` from status.md

For fix, the equivalent is passing these values via CLI args (no batch entry for holistic fix; no per-fix status entry). `millpy-merge-in-subagent.py` conflicts mode is intentionally left without start_sha passthrough — the inferred-success branch can never fire there (HEAD does not move before finalize returns; the merge commit is created by the SKILL after success is confirmed).

### `emit_prepare` signature change

`emit_prepare(briefs_dir, role, scope, round_n, prompt_text, model_tier, session_id)` in `_implementer_common.py` must gain an optional `start_sha: str | None = None` kwarg. When non-None, it is included in the emitted envelope JSON as `"start_sha": <value>`. When None (the default), it is omitted. This preserves backward compatibility: `millpy-implement.py` does not pass `start_sha` (it persists via status.md instead); `millpy-fix.py` passes it; `millpy-merge-in-subagent.py` conflicts prepare does NOT pass it (inferred-success cannot fire for conflicts mode — HEAD does not move before finalize returns — so there is no value to supply and no benefit to adding the capture).

**Ordering invariant:** In `millpy-fix.py`'s shared dispatch tail, `start_sha` must be captured via `git rev-parse HEAD` BEFORE the `--stage prepare` early-return (which calls `emit_prepare`). Both lines appear in the shared dispatch tail after the batch/holistic scope branches complete; the rev-parse comes first, then the prepare guard, then `emit_prepare`. Any restructuring must preserve this ordering; a rev-parse after the early-return would silently emit a stale or wrong SHA.

### Discussion-review finalize differs from code/plan

`millpy-review-discussion.py`'s finalize is NOT a literal copy of the code-review change. Key differences:
- `_review_discussion.finalize(cfg, slug, raw_text, round_n, reviews_dir, mill_dir, project_root, wiki_root)` — no `scope` or `git_root` params.
- The CLI's prepare call site uses positional args for the first five (`cfg, slug, mill_dir, project_root, wiki_root`) with `max_rounds` as a keyword arg: `prepare(cfg, slug, mill_dir, project_root, wiki_root, max_rounds=args.max_rounds)` — different signature from the code/plan prepare.
- The finalize stage must wire `round_n=args.round` and derive `reviews_dir` from config; then call `finalize(...)` without `scope` or `git_root`. **Read `_review_discussion.finalize` signature before editing.**

### `reviews_dir` resolution in review finalize

The correct helper is `_review_common.resolve_path(cfg["paths"]["reviews_dir"], slug)` — this applies the `<SLUG>` substitution pattern and resolves against the active hub root, matching what the existing prepare() call returns. `_paths.resolve_task_path(project_root, ...)` is the wrong helper: it does not apply slug substitution and resolves against `project_root` (the task worktree), not the hub.

**Caution:** verify the exact helper call by reading the existing `prepare()` functions in `_review_code.py`, `_review_plan.py`, and `_review_discussion.py` before wiring up finalize. The path must match exactly what prepare() returns.

## Constraints

- `print()` / `_log()` output must be ASCII only — no em-dashes, smart quotes, or Unicode arrows (Windows cp1252 stdout constraint).
- All new Bash commands in SKILL.md must use `${CLAUDE_PLUGIN_ROOT}` literally, not expanded.
- Tests use `.scratch/` for ephemeral fixtures, never `/tmp/` or `$env:TEMP`.
- Verify commands for Python projects must start with `PYTHONPATH=` (empty prefix) to avoid inheriting the cache PYTHONPATH.

## Testing

### `test-fix-finalize.py` (new)

Tests `millpy-fix.py --stage finalize` end-to-end with real git:
- **Happy path**: Agent output contains valid JSON `{"status":"success"}` → finalize emits correct envelope with real HEAD sha.
- **Inferred-success path**: Agent output is prose (no JSON) + fixer committed work + tree clean + `--start-sha` provided → finalize emits `{"status":"success","inferred":true}`.
- **No-json, no-commits path**: Agent output is prose + HEAD == start_sha → finalize emits `stuck/logic: "no structured report"`.
- **session_id passthrough**: `--session-id` is reflected in the inferred-success envelope.
- Both `--scope batch` and `--scope holistic` variants.

### `test-review-finalize.py` (new)

Tests that review finalize correctly uses `--round` without re-invoking prepare:
- Mock `prepare()` to raise an exception; call `main()` with `--stage finalize --round 1 --agent-output <file>` → should NOT call prepare(), should not raise.
- **Round number**: The review file is written under the correct round-stamped filename.
- Cover `millpy-review-code.py`, `millpy-review-plan.py`, `millpy-review-discussion.py` with the same fixture pattern.

### Existing tests to run after changes

- `plugins/mill/unit_tests/run-all.py` — full suite must pass.
- `test-agent-mode-commit-target.py` — must pass unchanged (no changes to `_forward_output`).

## Q&A log

- **Q:** What approach should be used to persist `start_sha` across the prepare→finalize boundary for the fixer? **A:** [auto-pick] Add `start_sha` to the prepare JSON envelope and add `--start-sha` flag to the finalize CLI stage. **Why:** Explicit contract with no hidden side-files; consistent with SKILL's existing pattern of passing prepare envelope fields as finalize args.
- **Q:** Should Gap C (review finalize re-invoking prepare()) be fixed in this task? **A:** [auto-pick] Yes — pass `round_n` as `--round` CLI arg to finalize and drop the prepare() re-invocation. **Why:** Eliminates double-config-load and fragile round re-derivation.
- **Q:** Is Gap D (merge-in-subagent conflicts-mode) in scope? **A:** [auto-pick] Yes — same root cause and same fix pattern. **Why:** Half-fixing creates a confusing inconsistency between fix and merge-in-subagent pipelines.
- **Q:** Should `--round` flag be named `--round`? **A:** [auto-pick] Yes. **Why:** Matches the `"round"` field in every prepare envelope.
- **Q:** Should mill-go SKILL pass `--round` from prepare envelope to review finalize? **A:** [auto-pick] Yes. **Why:** Removes the re-derive entirely; round is already authoritative in the envelope.
- **Q:** Testing approach? **A:** [auto-pick] New unit tests `test-fix-finalize.py` and `test-review-finalize.py`. **Why:** Pure Python, no LLM needed; fast and focused.
- **Q:** Should `millpy-review-discussion.py` be included? **A:** [auto-pick] Yes — same Gap C pattern. **Why:** Fixing all three reviewers together is safer than a partial fix.
- **Q:** Should `--session-id` also be added to fix/merge-in finalize? **A:** [auto-pick] Yes. **Why:** Completes the contract so inferred-success path emits the correct session_id.
- **Q:** How should reviews_dir be obtained in review finalize without calling prepare()? **A:** [auto-pick] Derive from `cfg['paths']['reviews_dir']` via `_paths.resolve_task_path`. **Why:** Single authoritative source; no new CLI arg needed.
- **Q:** Extend existing integration test or write new unit tests? **A:** [auto-pick] New unit tests. **Why:** Focused on the specific finalize path logic; no LLM call needed.
- **Q (review gap 1):** Does `emit_prepare` need to change to include `start_sha`? **A:** Yes — add optional `start_sha` kwarg; backward-compatible (implement.py doesn't pass it). Added `_implementer_common.py` to scope.
- **Q (review gap 2):** Is `--start-sha` applicable to `millpy-merge-in-subagent.py` conflicts finalize? **A:** No — at finalize time HEAD == start_sha (merge --continue hasn't run yet) and tree is dirty, so `_forward_output` inferred-success can never fire. Conflicts finalize is correct as-is; removed from scope.
- **Q (review gap 3):** What is the correct helper for reviews_dir in review finalize? **A:** `_review_common.resolve_path(cfg["paths"]["reviews_dir"], slug)` — not `_paths.resolve_task_path`; the former applies slug substitution + active-hub resolution.
- **Q (review note 4):** Does conflicts mode have a pre-commit before capturing start_sha? **A:** No — conflicts mode (`_run_conflicts`) has no pre-commit. Moot since conflicts finalize is now out of scope.
- **Q (review note 5):** Does step 5 of Agent-mode dispatch cover prepare-envelope-derived args? **A:** No — "same standard arguments" only covers the original invocation args. SKILL update must explicitly amend step 5 to thread `start_sha`/`session_id`/`round` from the prepare envelope into finalize.
- **Q (r2 gap 1):** Should conflicts prepare pass `start_sha` to `emit_prepare` "for future use"? **A:** No — YAGNI. Inferred-success cannot fire for conflicts (HEAD unchanged at finalize time), so there is no value to capture and no benefit. Removed the contradicting clause; conflicts mode stays fully out of scope.
- **Q (r2 gap 2):** Where would conflicts prepare get `start_sha` if needed? **A:** Moot (conflicts passes nothing). Noted that `_run_conflicts` has no pre-commit and no rev-parse in the prepare path.
- **Q (r2 note 3):** Is discussion-review finalize wiring identical to code/plan? **A:** No — `_review_discussion.finalize` omits `scope` and `git_root`; prepare call site uses positional args. Added explicit caution; implementer must read the signature before editing.
- **Q (r2 note 4):** Is start_sha capture ordering in fix prepare documented? **A:** Added explicit invariant: rev-parse must precede `emit_prepare` early-return in the shared dispatch tail.
- **Q (r3 gap 1):** Does merge-in-subagent finalize get `--session-id`? **A:** No — conflicts finalize is out of scope entirely. Removed from session-id decision; now scoped to millpy-fix.py only.
- **Q (r3 note 2):** Are start_sha line number citations accurate? **A:** No — line 314 is the prepare guard, 318 is emit_prepare. Replaced exact line numbers with structural description.
- **Q (r3 note 3):** Is `max_rounds` positional in discussion-review prepare? **A:** No — it is keyword-only; the first five args are positional. Updated the description.
- **Q (r4 gap 1):** Does the SKILL step 2 already capture session_id/round? **A:** No — step 2 currently parses only brief_path, subagent_type, model. Both step 2 (extract) and step 5 (thread into finalize) must be amended. Added step 2 amendment to scope.
- **Q (r4 note 2):** How many steps does the Agent-mode dispatch pattern have? **A:** Six (resolve-mode, prepare, Agent-call, capture-output, finalize, branch-verdict). Corrected from five; finalize = step 5.
- **Q (r4 note 3):** Does mill-start have its own copy of the dispatch pattern? **A:** No — it references mill-go's pattern. The concrete mill-start edit is threading `--round` at the two discussion-review finalize call sites in mill-start/SKILL.md.
