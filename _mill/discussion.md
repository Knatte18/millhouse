# Discussion: 66 (A) — Review sandbox follow-up: guard exceptions + bare-exit + sandbox argv

```yaml
task: 66 (A) — Review sandbox follow-up: guard exceptions + bare-exit + sandbox argv
slug: review-sandbox-followup
status: discussing
parent: main
```

## Problem

Task 63 (commit `666bb16b`) introduced `worktree_snapshot_guard` and the `--disallowedTools Edit,Write,Bash,NotebookEdit` flag so reviewer subprocesses cannot mutate git state. The mill-misc-fixes-8 holistic run on 2026-05-17 showed three orthogonal gaps that defeat that protection plus three adjacent reliability bugs in the same code paths:

- **#335 — `_llm_claude._build_argv` drops `--allowedTools ""`.** `if allowed_tools` is falsy for the empty string `run_bulk` passes, so the entire allow-list is omitted. The reviewer process inherits Claude CLI's default tool surface (Skill, Agent, MCP, WebFetch, …). `Skill` lets the reviewer invoke `@git-commit` → real commits; `Agent` lets it spawn a sub-agent with the full default tool surface. The deny-list intent was right; the implementation defeats it.
- **#336 — `worktree_snapshot_guard` short-circuits its after-snapshot on inner exception.** Sequence in the same incident: reviewer overstepped (commits + push + GH issue) AND returned non-yaml prose; `parse_verdict` raised; exception propagated through `except Exception: raise` before the post-snapshot ran; `ReviewerOverstepError` never fired. The system reported "could not parse verdict" while the real story was sandbox breach.
- **#338 — `millpy-review-code.py` exits 1 with bare stderr on parse failure.** When `parse_verdict` raises `ReviewError` inside the run() function it propagates to the CLI's top-level `except ReviewError` which now (via `_review_cli.print_error_envelope`) does emit a JSON envelope on stdout — but exits 1. mill-go's ERROR-only-aggregate retry path is documented to fire when the JSON envelope carries `verdict: "ERROR"`. The current shape (envelope on stdout + exit 1) is ambiguous: pre-launch errors (slug missing, config broken — not retry-eligible) and reviewer parse failures (one-shot model misbehaviour — retry-eligible) are indistinguishable to the caller. Discussion review's backend additionally converts `LLMError` to `ReviewError` instead of returning `verdict: ERROR`, diverging from code-review's pattern.
- **#333 — mill-go holistic has no recovery when reviewer bg subprocess exits without writing a review file.** Holistic step 1's crash-recovery scan handles "review file already exists" but not "bg subprocess died, no file ever appeared". The operator had to write the review file by hand, append the phase, commit, and inline the entire Handoff sequence.
- **#337 — `_wiki.write_commit_push` emits confusing `git commit failed: ''` when `set_phase_at` is a no-op.** The body already has fallback handling (`if "nothing to commit" in combined`), but the check is fragile: when stdout AND stderr come back empty (or git's locale changes the message), the WikiPushError fires with no actionable detail. The condition should be detected positively via `git diff --cached --quiet` BEFORE attempting the commit, so the no-op path is the explicit happy path rather than an error-message-substring rescue.

**Why now:** the same incident hit all five bugs in one run. Sandbox enforcement is the load-bearing one; the other four are reliability gaps that turned a recoverable reviewer hallucination into a four-step manual cleanup. Shipping these together is correct — they share files and the diagnostic story makes more sense as one PR.

## Scope

**In:**

- `plugins/mill/scripts/_llm_claude.py` — change the empty-allow-list guard to `is not None` so `--allowedTools ""` is emitted explicitly. Keep the existing `--disallowedTools` deny-list as defence-in-depth.
- `plugins/mill/scripts/_review_common.py` — rewrite `worktree_snapshot_guard` so the after-snapshot ALWAYS runs and `ReviewerOverstepError` is raised in preference to any inner exception (preserving the inner via `__cause__`).
- `plugins/mill/scripts/_review_code.py`, `_review_discussion.py` — catch `ReviewError` (from `parse_verdict`) inside `run()` and convert it to a `verdict: ERROR` `ReviewResult` matching the existing `LLMError` branch in `_review_code.run`. Discussion-review also converts its `LLMError → ReviewError` branch to the `verdict: ERROR` return-shape for consistency.
- `plugins/mill/scripts/_review_plan.py` — VERIFY/ADJUST ONLY. The per-batch path ([line 251](plugins/mill/scripts/_review_plan.py#L251)) and the holistic path ([line 607](plugins/mill/scripts/_review_plan.py#L607)) already catch `ReviewError` from `parse_verdict` and return `verdict: ERROR` review entries. No new try/except is needed. The task is to confirm the existing error-entry shape matches the `{"scope", "verdict": "ERROR", "file", "error", "session_id"}` standard used by code-review and discussion-review and to add the equivalent `_aggregate_top_verdict` "all-ERROR → top-level ERROR" check at the result-assembly site if it isn't already there (currently lines 620-621 handle this — confirm the assertion still holds after batch-1/batch-2 standard alignment, and adjust dict keys only if drift is found).
- `plugins/mill/scripts/millpy-review-code.py`, `millpy-review-plan.py`, `millpy-review-discussion.py` — return exit code 0 for `verdict: ERROR` envelopes (review-engine errors emit a JSON envelope and exit 0 — the JSON line is the contract); keep exit 1 reserved for pre-launch errors (config missing, slug not derivable, registry validation, plan validator findings, `--extra-file` not found).
- `plugins/mill/scripts/_wiki.py` — `_write_commit_push_body` runs `git diff --cached --quiet` after `git add`; exit code 0 means nothing staged → log "no changes, skipping commit" and return cleanly. The existing "nothing to commit" stdout-substring fallback is removed since the new check covers the same case more reliably. The fallback `git commit failed:` error message includes both stdout and stderr.
- `plugins/mill/skills/mill-go/SKILL.md` — Holistic step 1 (Crash-recovery) gains a "no review file AND no live bg subprocess" branch that proceeds straight to step 3 (fire fresh CLI via `millpy-bg`) rather than falling through silently. Step 1 also references the new helper that tests whether the most recent `bg-*-review-code-holistic-r{H}.log` indicates a still-running worker (presence of `[mill-bg] WORKER PID=N START` AND absence of `[mill-bg] EXIT`, combined with an `os.kill(pid, 0)` liveness check).
- `plugins/mill/scripts/_bg.py` — new tiny helper module `is_bg_worker_alive(log_path: Path) -> tuple[bool, int | None]` that parses the log header for `WORKER PID=N` and uses `os.kill(pid, 0)` (Windows: `OpenProcess`-via-`psutil` is out of scope; fall back to "treat as not alive after 5 minutes of log silence" — see Decisions). Returns `(alive, pid_or_None)`.
- Unit tests under `plugins/mill/unit_tests/`:
  - `test-llm-claude-argv.py` — `_build_argv` with `allowed_tools=""` MUST include `--allowedTools ""` in argv; `allowed_tools=None` MUST omit the flag entirely (regression guard for the new `is not None` check).
  - `test-review-common-guard.py` — four cases (clean exit + clean state → no error; clean exit + state mutated → `ReviewerOverstepError`; inner raise + clean state → inner propagates unchanged; inner raise + state mutated → `ReviewerOverstepError` with inner preserved via `__cause__`).
  - `test-review-cli-error-envelope.py` — `print_error_envelope` shape (stdout JSON + stderr line) plus exit-code semantics for `_review_code.run` returning `verdict: ERROR` vs. raising `ReviewError`.
  - `test-wiki-noop-commit.py` — `_write_commit_push_body` against a fixture wiki where the staged change is a no-op (file rewritten with identical content) returns cleanly without raising.
  - `test-bg-liveness.py` — `is_bg_worker_alive` against synthetic log files (header only / header + EXIT / header but PID is reused by another process — see Decisions).

**Out:**

- Reviewer prompt template auditing for orchestrator-vocabulary leakage (#334 follow-up suggestion 2). The root cause of #334 was sandbox enforcement, not template phrasing — once the sandbox is intact, a hallucinated handoff-summary cannot do harm. Template hygiene belongs in a separate `66 (B)`-class task scoped to prompt content rather than runtime defences.
- Auto-rollback on `ReviewerOverstepError`. v2's current behaviour (raise, operator inspects, manual reset) is correct because the wiki side-effects are not git-revertable (a GH issue was filed; rebase doesn't undo that). The PR makes the overstep detectable; cleanup stays manual.
- Replacing the existing `--disallowedTools` deny-list. The allow-list is now the primary mechanism; deny-list stays for defence-in-depth against future tool surface that doesn't honour the allow-list shape. We do not remove it.
- Reviewer subprocess timeouts in mill-go. #333's "subprocess died without writing" path is addressed by detecting liveness on next mill-go resume; we do not add a wall-clock timeout to the poll loop because legitimate `claude -p` runs can exceed 15 minutes on large bulks.
- Windows-native process-liveness via `psutil` or `OpenProcess`. We use the same `os.kill(pid, 0)` probe on both platforms — Python's `os.kill(pid, 0)` raises `OSError(errno.EPERM)` on Windows for live PIDs the caller doesn't own (still a positive liveness signal) and `OSError(errno.ESRCH)` / `ProcessLookupError` for missing PIDs. If that signal proves unreliable on Windows during testing, fall back to "log unchanged for > 5 min → treat as dead". No new dependency.

## Decisions

### sandbox-argv-explicit-empty

- Decision: Change `_llm_claude._build_argv` line 104 from `*(["--allowedTools", allowed_tools] if allowed_tools else [])` to `*(["--allowedTools", allowed_tools] if allowed_tools is not None else [])`. `run_bulk` already passes `allowed_tools=""`; this makes the flag emit as `--allowedTools ""` instead of being dropped.
- Rationale: matches the docstring on `run_bulk` ("Spawns: claude -p --allowedTools '' …") and matches the documented Claude CLI semantics where an empty allow-list disables every tool. Defence-in-depth `--disallowedTools` stays in place for future-proofing.
- Rejected:
  - Pass `None` from `run_bulk` to signal "no flag" — that semantic is wrong; bulk mode means "no tools", not "default tools". `None` is for callers who want the CLI default.
  - Replace the deny-list with an exhaustive allow-list — the allow-list approach is the primary mechanism per #335's analysis, but the deny-list is cheap defence-in-depth against new tool families.

### guard-always-runs-after-snapshot

- Decision: `worktree_snapshot_guard` becomes (option 1 from #336):
  ```python
  inner_exc: Exception | None = None
  try:
      yield
  except Exception as exc:
      inner_exc = exc
  after_sha = _capture_head_sha(project_root)
  after_porcelain = _capture_porcelain(project_root)
  before_filtered = _filter_porcelain(before_porcelain, expected_paths)
  after_filtered = _filter_porcelain(after_porcelain, expected_paths)
  if before_sha != after_sha or set(before_filtered) != set(after_filtered):
      diff = _porcelain_diff(before_filtered, after_filtered)
      raise ReviewerOverstepError(before_sha, after_sha, diff) from inner_exc
  if inner_exc is not None:
      raise inner_exc
  ```
- Rationale: a reviewer that ran orchestrator code is categorically more dangerous than a downstream parse failure, so the overstep error takes priority. The inner exception is preserved via `__cause__` so debugging the parse failure remains possible. mill-go's ERROR-only-retry path is only intended for transient LLM misbehaviour, not for reviewers that mutated state — surfacing the overstep prevents auto-retry from masking a real sandbox breach.
- Rejected:
  - Option 2 (log overstep to stderr, re-raise inner): the overstep would not propagate as a typed exception, so callers couldn't `except ReviewerOverstepError`. Loses programmatic detection.
  - Move snapshot capture into a `finally` block and raise only the overstep: would swallow the inner exception entirely. We want both pieces of information.

### review-cli-error-envelope-exit-zero

- Decision: For each of `millpy-review-code.py`, `millpy-review-plan.py`, `millpy-review-discussion.py`, catch `ReviewError` raised by `parse_verdict` (or any other engine-internal failure inside `run()`) at the backend layer — convert to a `ReviewResult(type=…, round=…, verdict="ERROR", reviews=[{"scope": "holistic", "verdict": "ERROR", "error": str(exc), "session_id": None}])` and return normally. The CLI then prints the JSON envelope on stdout and exits 0. Exit 1 is reserved for **pre-launch** errors raised BEFORE `run()` is called: config-load failure, registry validation failure, slug derivation failure, plan-validator findings, `--extra-file` resolution failure.
  - `_review_discussion.run` also stops wrapping `LLMError` as `ReviewError`; instead it returns a `verdict: ERROR` ReviewResult mirroring `_review_code.run`. The discussion-review CLI's main path no longer raises on LLM failure.
- Rationale: aligns the three reviewer CLIs on a single contract — "exit 0 + JSON envelope" means a reviewer round completed (success OR retryable failure); "exit 1 + stderr line" means the engine never ran (operator must intervene). mill-go's ERROR-only-aggregate retry path then becomes unambiguous: it fires when stdout has a JSON envelope with `verdict: "ERROR"` regardless of exit code, but the documented exit code matches the documented semantics. Removes a category of false-positive operator panic ("bare CLI failure! must be config!" when it's really a one-shot reviewer hiccup).
- Rejected:
  - Keep exit 1 + envelope (current state): muddies the distinction between recoverable and unrecoverable. mill-go does poll the JSON envelope regardless, but the exit-code mismatch leaks into operator-facing logs ("bg log shows exit 1!") and makes debugging the ERROR-only path harder.
  - Convert pre-launch errors to envelope too (always exit 0): pre-launch failures are not retryable — the next round will hit the same config bug. Forcing the orchestrator to retry-then-block would waste a round and obscure the real problem.

### wiki-write-noop-via-diff-cached

- Decision: `_write_commit_push_body` runs `git diff --cached --quiet` immediately after `git add --`. Exit code 0 (nothing staged) → log `[wiki] write_commit_push: no changes staged, skipping commit` and return cleanly (no commit, no push). Exit code 1 (something staged) → proceed with `git commit`. The fallback `if "nothing to commit" in combined: return` branch is removed since the new positive check covers the same case more reliably. The `WikiPushError` message for a failed `git commit` is updated to include both `commit.stdout` and `commit.stderr` so future failures with non-empty stdout are debuggable.
- Rationale: `git diff --cached --quiet` is the canonical, locale-independent way to ask "is anything staged?" The current substring check on `"nothing to commit"` depends on git's English locale and is empty-string-fragile (#337's incident). Making the no-op path the happy path also matches the broader idempotency goal — `set_phase_at` is intentionally a no-op when the wiki is already in the target state, and that should be a clean return, not an error-message rescue.
- Rejected:
  - Keep the substring fallback and add stdout to the error message: still locale-dependent; addresses the symptom not the cause.
  - Compare file SHAs before vs. after `set_phase_at` in the caller: pushes the check up the stack into every caller; `_write_commit_push_body` is the right layer because it owns the git invocation.

### mill-go-holistic-recovery-dead-bg

- Decision: mill-go Holistic step 1 (Crash-recovery) becomes a three-way branch. NOTE: branches 2 and 3 do NOT re-execute step 2 (`_status.append_phase("holistic-reviewing", …)`) — that phase entry was already appended on the original (pre-crash) run, and appending again would duplicate the timeline. They jump directly to step 3 (`millpy-bg` invocation of `millpy-review-code.py`).
  1. Review file present → use it, skip the CLI (current behaviour); proceed to step 4 (verdict branch).
  2. No review file AND no `bg-*-review-code-holistic-r{H}.log` exists in `.scratch/` → jump directly to step 3 (fire fresh CLI via `millpy-bg`); skip step 2's phase-append because the original run already wrote it.
  3. No review file AND a bg log exists for round H → call `_bg.is_bg_worker_alive(log_path)`. If alive → poll the log until `[mill-bg] EXIT` appears, then resume at step 4 (parse JSON, branch on verdict). If dead → jump directly to step 3 (fire fresh CLI via `millpy-bg`), logging `[mill-go] previous holistic round H bg worker died (pid=N); re-firing CLI`; skip step 2's phase-append for the same reason as branch 2. Step 1 wording in `SKILL.md` is updated to enumerate these three branches explicitly and to document the skip-step-2 invariant.
- Rationale: the current SKILL.md only handles branch 1, so an operator-resumed mill-go with a dead bg subprocess silently fell through to step 2 — which DID fire a fresh CLI in practice, but with no diagnostic and no detection of the prior crash. Per #333 the operator did manual recovery because they did not trust the silent fall-through (correctly, because the fresh round would have collided with the still-running bg worker if it had been alive). Making the liveness check explicit lets the orchestrator do the right thing in both directions: wait for a live worker, re-fire a dead one.
- Rejected:
  - Add a wall-clock timeout to the step 3 poll loop: legitimate large-bulk holistic runs exceed 15 minutes; any reasonable timeout produces false positives.
  - Always re-fire on resume without checking liveness: risks a second worker racing against an alive one — both would attempt to write to `_mill/reviews/`, both would call `_status.append_phase`, conflicting commits.
  - Detect liveness inside `millpy-bg.py` itself: the launcher exits immediately on Windows (the worker is detached); liveness has to be checked from the orchestrator at resume time. The right layer is mill-go, not the launcher.

### bg-liveness-helper-module

- Decision: New `plugins/mill/scripts/_bg.py` exposes one public function:
  ```python
  def is_bg_worker_alive(log_path: Path) -> tuple[bool, int | None]:
      """Return (alive, pid). alive=True iff log has WORKER PID=N START, no EXIT line, and os.kill(pid, 0) signals process exists.

      Liveness probe semantics:
        - log missing or no WORKER PID line                 -> (False, None)
        - log has EXIT line                                 -> (False, pid)
        - os.kill(pid, 0) raises ProcessLookupError/ESRCH   -> (False, pid)
        - os.kill(pid, 0) raises PermissionError/EPERM      -> (True, pid)   (process exists, owned by someone else)
        - os.kill(pid, 0) returns                           -> (True, pid)

      Windows fallback: if os.kill probing is inconclusive AND log's mtime
      is older than 5 minutes, return (False, pid) -- ample margin over
      claude -p's typical between-line interval (sub-second to seconds).
      ```
- Rationale: tiny, focused helper that both mill-go SKILL.md and any future caller (mill-cleanup, mill-status) can use. PID-based liveness is the canonical UNIX pattern; Windows `os.kill(pid, 0)` works on CPython by going through `OpenProcess` so the same code path covers both platforms. The 5-minute mtime fallback is the same staleness window already used by `_wiki._STALE_SECONDS` — symmetry helps operator intuition.
- Rejected:
  - Add `psutil` as a dependency for cross-platform process introspection: heavyweight for a one-function need; mill has been disciplined about stdlib-only dependencies.
  - Probe via `tasklist` / `ps` subprocess: extra process spawn per probe; the `os.kill` route is in-process.

### no-template-audit-this-task

- Decision: Do not include reviewer-prompt template audit (#334 suggestion 2) in this task. File a separate backlog entry later if template hygiene becomes a recurring problem.
- Rationale: with the sandbox fix (#335) and overstep detection (#336) in place, a reviewer hallucinating handoff-summary prose is detected and quarantined. The prompt-template work is independent and adding it here would expand the diff and review surface unnecessarily.
- Rejected: bundle the template audit. Scope discipline — task 63 already split sandbox into two waves; this is the second wave. A third wave for prompt content is fine.

## Technical context

### Files this task touches

- [plugins/mill/scripts/_llm_claude.py:104](plugins/mill/scripts/_llm_claude.py#L104) — the one-line `is not None` fix.
- [plugins/mill/scripts/_review_common.py:118-153](plugins/mill/scripts/_review_common.py#L118-L153) — `worktree_snapshot_guard` rewrite per Decision `guard-always-runs-after-snapshot`. Helper functions `_capture_head_sha`, `_capture_porcelain`, `_filter_porcelain`, `_porcelain_diff` and class `ReviewerOverstepError` already exist and are unchanged.
- [plugins/mill/scripts/_review_code.py:336](plugins/mill/scripts/_review_code.py#L336) — wrap `verdict = parse_verdict(raw)` (and the post-NEED_CONTEXT-retry call on line 374) in try/except `ReviewError` → return `verdict: ERROR` ReviewResult mirroring the existing `LLMError` branch at lines 320-334. The `_aggregate_top_verdict` helper already returns `"ERROR"` when every review entry is ERROR.
- [plugins/mill/scripts/_review_plan.py](plugins/mill/scripts/_review_plan.py) — same pattern. The file's existing per-batch `try/except LLMError` blocks and aggregate-verdict logic show how `verdict: ERROR` ReviewResult is built. Apply the same shape to `parse_verdict` failures in both per-batch and holistic paths.
- [plugins/mill/scripts/_review_discussion.py:116-122](plugins/mill/scripts/_review_discussion.py#L116-L122) — replace the `LLMError → ReviewError` branch with a `verdict: ERROR` ReviewResult return (matches code/plan). Wrap `parse_verdict` in try/except `ReviewError` → `verdict: ERROR` return.
- [plugins/mill/scripts/millpy-review-code.py:106-108](plugins/mill/scripts/millpy-review-code.py#L106-L108), [millpy-review-plan.py:116-118](plugins/mill/scripts/millpy-review-plan.py#L116-L118), [millpy-review-discussion.py:61-63](plugins/mill/scripts/millpy-review-discussion.py#L61-L63) — the `except ReviewError as exc:` blocks remain for PRE-LAUNCH errors only (config / slug / registry / plan validator / extra-file). Engine-internal errors now route through `run()` returning a ReviewResult, and the CLI exits 0 by printing `result.to_dict()`. Pre-launch errors still call `print_error_envelope` and exit 1.
- [plugins/mill/scripts/_wiki.py:465-506](plugins/mill/scripts/_wiki.py#L465-L506) — `_write_commit_push_body` per Decision `wiki-write-noop-via-diff-cached`. Insert `git diff --cached --quiet` check between `git add` and `git commit`. Remove the `if "nothing to commit" in combined: return` fallback at lines 482-485 (positively detected upstream now). Update the `WikiPushError` message at line 486 to include `commit.stdout`.
- [plugins/mill/skills/mill-go/SKILL.md:331](plugins/mill/skills/mill-go/SKILL.md#L331) — Holistic step 1 wording change per Decision `mill-go-holistic-recovery-dead-bg`. Add the three-branch decision tree with the inline Bash invocation pattern that calls `_bg.is_bg_worker_alive`.
- New file `plugins/mill/scripts/_bg.py` — `is_bg_worker_alive` helper per Decision `bg-liveness-helper-module`. Stdlib only (`os`, `re`, `pathlib`, `time`).
- New unit tests under `plugins/mill/unit_tests/`:
  - `test-llm-claude-argv.py`
  - `test-review-common-guard.py`
  - `test-review-cli-error-envelope.py`
  - `test-wiki-noop-commit.py`
  - `test-bg-liveness.py`

### Adjacent code worth knowing

- `_subprocess_util.run` (the project's standard subprocess wrapper) is the right call for `git diff --cached --quiet`; capture the returncode without raising on non-zero.
- `print_error_envelope` ([plugins/mill/scripts/_review_cli.py:23-38](plugins/mill/scripts/_review_cli.py#L23-L38)) already emits the envelope shape the new exit-0 path needs to match. The CLI continues to use it for pre-launch errors only.
- `_aggregate_top_verdict` ([plugins/mill/scripts/_review_code.py:68-74](plugins/mill/scripts/_review_code.py#L68-L74)) already handles "every entry ERROR → top-level ERROR" — reuse it in plan and discussion if convenient, or duplicate the same 4-line pattern.
- `millpy-bg.py` worker mode writes `[mill-bg] WORKER PID=<N> START <ts>` on entry ([millpy-bg.py:56-59](plugins/mill/scripts/millpy-bg.py#L56-L59)) and `[mill-bg] EXIT <code>` in a try-block (NOT in `finally` — see `millpy-bg.py:60-67`). This is fine for the helper: a crash before `[mill-bg] EXIT` is precisely what the helper needs to detect (presence of START, absence of EXIT, liveness probe on PID).
- `worktree_snapshot_guard`'s `expected_paths` arg already covers `cfg["paths"]["reviews_dir"]` writes — the after-snapshot only fires on changes OUTSIDE that whitelist, so the existing approve-flow that writes a review file does not trip the guard.

### Why discussion-review still raises on pre-launch

`millpy-review-discussion.py` line 45's `except (ReviewError, ValueError, SystemExit) as exc:` block — config loading, wiki path resolution — keeps exit 1. The `try: slug = find_active_slug(...); result = run(...)` block at lines 56-62 also catches `ReviewError` for the pre-launch case (e.g. `find_active_slug` raising). The new pattern is: backend (`_review_discussion.run`) catches and converts engine-internal `ReviewError` to `verdict: ERROR`; CLI's `except ReviewError` still catches PRE-LAUNCH `ReviewError`s (e.g. slug derivation, registry validation). The distinction is "raised inside `run()` after it began LLM work" vs. "raised before `run()` could enter its work loop".

## Constraints

- `CONSTRAINTS.md` at the hub root: not present (`_constraints.read_if_exists()` returns empty).
- ASCII-only stdout/stderr per `CLAUDE.md` `## Conventions worth carrying`: log lines added by this task use `--` and `->` (not `—`, `→`).
- Windows-path / cmd-shim caveats per `_llm_claude._claude_argv_prefix`: not relevant — this task does not change the subprocess launch shape, only the argv composition.
- All path resolution stays within `_paths.py` per `## Path invariants`. The new `_bg.py` does not resolve paths; callers pass `log_path` directly.
- Plugin scripts reference `${CLAUDE_PLUGIN_ROOT}`, never the source repo: not applicable — `_bg.py` is a Python module imported by sibling scripts, not a SKILL.md invocation.

## Testing

### TDD candidates (write the test first, then the fix)

- **`test-llm-claude-argv.py`** (`_build_argv`): three cases — `allowed_tools=""` MUST include `--allowedTools ""`; `allowed_tools="Read,Grep,Glob"` MUST include `--allowedTools Read,Grep,Glob`; `allowed_tools=None` MUST omit the flag entirely. The current code passes case 2 and fails case 1 — writing the test FIRST catches the bug; the one-line fix turns it green. Also assert `--disallowedTools Edit,Write,Bash,NotebookEdit` IS present when `allowed_tools` is empty or a read-only tool list, and IS NOT present when `allowed_tools` contains any mutating tool (regression guard for `_has_mutating_tool`).

- **`test-review-common-guard.py`** (`worktree_snapshot_guard`): four scenarios — (a) clean exit, clean state → no exception; (b) clean exit, HEAD changed → `ReviewerOverstepError`; (c) inner raises `RuntimeError("inner")`, state clean → `RuntimeError("inner")` propagates unchanged; (d) inner raises `RuntimeError("inner")`, state mutated → `ReviewerOverstepError` raised, `exc.__cause__` is the `RuntimeError`. Cases (c) and (d) are the new behaviour; (a) and (b) are regression guards. Use an in-memory `tempfile.TemporaryDirectory` with `git init` + a commit, plus `subprocess.run(["git", "commit", "--allow-empty", "-m", "x"])` to simulate HEAD changes. No real reviewer.

- **`test-review-cli-error-envelope.py`** (CLI exit-code contract): two paths — (a) pre-launch failure (mock `find_active_slug` to raise `ReviewError`) → CLI exits 1, stdout has envelope, stderr has `ERROR:` line; (b) engine-internal failure (mock `_review_discussion.run` to return `ReviewResult(verdict="ERROR", reviews=[...])`) → CLI exits 0, stdout has JSON envelope. Cover code, plan, discussion (parameterize the test).

### Direct asserts (no TDD ceremony)

- **`test-wiki-noop-commit.py`**: fixture wiki with one file; `_write_commit_push_body(wiki, ["file.md"], "msg")` against an UNCHANGED file → returns cleanly, no commit, no push call attempted. Mock `_subprocess_util.run` to assert the `git diff --cached --quiet` call AND assert `git commit` was NOT invoked when diff exit is 0.

- **`test-bg-liveness.py`**: synthetic log files — (a) no log file → `(False, None)`; (b) log with `[mill-bg] WORKER PID=99999999 START …` and no EXIT, PID 99999999 does not exist → `(False, 99999999)`; (c) log with valid PID (use `os.getpid()` for the test) and no EXIT → `(True, <pid>)`; (d) log with EXIT line → `(False, <pid>)`. Skip the cross-platform-Windows assertion test if `os.name != "nt"` — the helper's behaviour matrix is documented but a fixture exercising the EPERM path requires another user's PID which test harnesses don't have.

### Integration test (manual, not automated)

After the PR is merged: run a plan-or-code reviewer call where the reviewer subprocess deliberately attempts `git commit --allow-empty` (use a mock reviewer registry entry that spawns a Bash one-liner via Skill). Without the sandbox fix, the commit succeeds and `ReviewerOverstepError` fires. With the fix, the Bash invocation is denied at the CLI layer and the reviewer cannot reach git in the first place. This integration test belongs in `plugins/mill/integration_tests/` if added, but is not blocking for the PR.

## Q&A log

- **Q:** Should the sandbox fix also remove the deny-list `--disallowedTools`? **A:** [auto-pick] Keep both. **Why:** allow-list is primary; deny-list is cheap defence-in-depth against future tool families that might bypass an empty allow-list in a future Claude CLI version.
- **Q:** Should `worktree_snapshot_guard` use option 1 (always-check, chain via `__cause__`) or option 2 (log overstep, re-raise inner)? **A:** [auto-pick] Option 1. **Why:** typed `ReviewerOverstepError` is required for callers that `except ReviewerOverstepError`; option 2 loses that. The `__cause__` chain preserves the inner failure for debugging.
- **Q:** Should review CLIs exit 0 with envelope on engine-internal errors, or keep exit 1 + envelope? **A:** [auto-pick] Exit 0. **Why:** disambiguates "the engine ran and produced a retryable result" from "the engine could not start". Aligns the three review CLIs on one contract.
- **Q:** Should `_wiki._write_commit_push_body` use `git diff --cached --quiet` or just improve the substring fallback? **A:** [auto-pick] `git diff --cached --quiet`. **Why:** positive locale-independent check beats string-matching git's English output.
- **Q:** Should mill-go's holistic recovery use a wall-clock timeout or a PID liveness check? **A:** [auto-pick] PID liveness via the new `_bg.is_bg_worker_alive` helper. **Why:** holistic runs legitimately take > 15 minutes; any timeout produces false positives. PID liveness is precise.
- **Q:** Should `_bg.py` depend on `psutil` or stay stdlib-only? **A:** [auto-pick] Stdlib only — `os.kill(pid, 0)` works on both Linux and Windows CPython. **Why:** mill has been disciplined about stdlib-only dependencies; the cross-platform behaviour of `os.kill(pid, 0)` is well-documented.
- **Q:** Should this task also audit reviewer prompt templates for orchestrator-vocabulary leakage (#334 suggestion 2)? **A:** [auto-pick] No, defer. **Why:** with sandbox enforcement in place, hallucinated prose is detected and quarantined. Template hygiene is independent and belongs in a separate task.
- **Q:** Should the integration test (reviewer-attempts-real-git-commit) be in this PR? **A:** [auto-pick] No, defer or run manually. **Why:** integration tests under `plugins/mill/integration_tests/` need a real `claude` invocation and a curated registry stub — adds review surface without changing the unit-test confidence story.
