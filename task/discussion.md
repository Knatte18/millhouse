# Discussion: 29 (A) — mill-merge-in: delegate konflikter og verify-feil til sub-agent

```yaml
task: '29 (A) — mill-merge-in: delegate konflikter og verify-feil til sub-agent'
slug: mill-merge-subagent
status: discussing
parent: main
```

## Problem

`mill-merge-in` currently resolves real-code conflicts and fixes verify failures inline inside the Builder (Opus) session. During the holistic-fix-agent merge run (2026-05-07), a single diverging commit on `main` caused conflicts in `millpy-implement.py` and `test-millpy-implement.py`. Resolving them required the Builder to read 4–5 files inline. Then verify failed (4 pre-existing broken tests), requiring the Builder to read `test-review-plan-flow.py` (~1090 lines), `_review_plan.py` (~600 lines), and `_reviewer_test_stub.py`. The Builder's context was nearly exhausted by the end of the merge.

The "lean Builder" principle that governs `mill-go` — the Builder reads only JSON verdicts, never source files or diffs — does not apply to `mill-merge-in`. This task closes that gap: both conflict resolution and verify-fix are delegated to a dedicated Sonnet sub-agent that returns a structured JSON verdict to the Builder.

## Scope

**In:**
- New script `millpy-merge-in-subagent.py` — unified CLI for both modes (`--mode conflicts|verify-fix`). Spawns `_implementer_sonnet.run()`, emits JSON on stdout (`{"status":"success|stuck",...}`).
- New templates `merge-in-conflict-brief.md` and `merge-in-verify-brief.md`.
- Updated `mill-merge-in/SKILL.md` — Steps 3 and 4 now call the new CLI instead of describing inline resolution. Builder reads only the JSON verdict.
- New config key `merge.verify_fix_rounds` (int, default 3) in `plugins/mill/templates/wiki-config.yaml`.
- Unit test `test-millpy-merge-in-subagent.py` — mock `_implementer_sonnet.run`, verify brief construction and verdict forwarding.
- Updated `mill-merge-in/SKILL.md` Step 3 and Step 4 describe calling the CLI and mapping stuck → existing checkpoint rollback (pre-existing rollback behavior is preserved; the SKILL update specifies only the delegation path, not a new rollback step).

**Out:**
- `millpy-implement.py` and `millpy-implement-holistic.py` path bug (`project_root / "status.md"` vs `task/status.md`) — pre-existing issue, separate task.
- `mill-merge` SKILL.md — mill-merge calls mill-merge-in; the interface is unchanged.
- No status.md tracking of sub-agent session IDs (not needed; Builder reads only the JSON verdict).
- No retry/resume of the conflict sub-agent session (fresh start per call; conflicts are idempotent after `git reset --hard checkpoint`).
- No changes to the conflict policy table (whitespace/lock-files/build-artefacts still handled by the SKILL before spawning).

## Decisions

### single-cli-two-modes

- Decision: One CLI `millpy-merge-in-subagent.py` with `--mode conflicts|verify-fix`. Separate templates for each mode brief.
- Rationale: Setup/dispatch code is identical between modes (path resolution, config load, `_implementer_sonnet.run`, `_forward_output`). One file to test, one entry point. Different templates keep the brief wording mode-specific without coupling the CLI logic.
- Rejected: Two separate CLIs (`millpy-merge-in-conflict.py` + `millpy-merge-in-verify.py`) — unnecessary duplication when dispatch logic is the same.

### conflict-context-to-sub-agent

- Decision: Pass only the list of conflicting file paths to the sub-agent. The sub-agent reads them with Read/Bash and resolves the conflict markers. The sub-agent stages each resolved file with `git add <file>` but does NOT commit. After the sub-agent returns `{"status":"success"}`, the SKILL runs `git merge --continue` to create the merge commit.
- Rationale: Keeps the brief size predictable. Sub-agent has full Read/Bash access. `git merge --continue` is a git state transition that belongs to the SKILL, not the sub-agent — keeping commit authority with the SKILL and code resolution with the sub-agent. Embedding raw diffs upfront would balloon the brief for repos with many large conflicts.
- Rejected: Including raw `git show MERGE_HEAD -- <file>` output per file in the brief. Sub-agent running `git merge --continue` or individual per-file `git commit` — would bypass the SKILL's checkpoint and rollback ownership.

### verify-fail-context

- Decision: The CLI embeds verify output as inline content in the brief (`tokens["VERIFY_OUTPUT"] = captured_stdout_stderr`). Also passes the checkpoint-to-HEAD diff inline (`tokens["MERGE_DIFF"] = git diff checkpoint..HEAD output`). The brief token `<VERIFY_OUTPUT>` receives the raw captured output string; `<MERGE_DIFF>` receives the diff string. No temp file is passed to the sub-agent — the CLI captures output in memory, builds tokens, and spawns the sub-agent.
- Rationale: Brief is self-contained (sub-agent needs no file I/O for context). Simpler cleanup (no file to manage after spawn). Content fits in sub-agent context (200k tokens; typical test failure output is small). Consistent with how holistic review briefs inline diffs.
- Rejected: Passing a file path as token and having the sub-agent read it — requires file to stay alive across spawn, complicates deletion timing, and contradicts the "brief is self-contained" principle.

### verify-fix-rounds-config

- Decision: New config key `merge.verify_fix_rounds` (int, default 3). Read by the CLI via deep-merged config. The CLI is single-shot: it spawns one sub-agent session and passes `<VERIFY_FIX_ROUNDS>` as a token in the brief. The sub-agent self-fixes internally up to that many times before reporting `stuck_type: verify`. The SKILL calls the CLI once and reads the JSON verdict — there is no outer loop in the SKILL.
- Rationale: Consistent with how the batch implementer works (self-fixes internally up to `self_fix_rounds`, reports stuck after exhaustion). The SKILL stays lean; the sub-agent owns the fix iteration. Different semantic from `review.code.self_fix_rounds` (merge verify vs. code-review implementation fix).
- Rejected: SKILL-driven loop (SKILL calls CLI once per fix attempt) — adds loop logic to the SKILL, breaking lean-Builder principle.

### no-status-tracking

- Decision: The sub-agent does not update `task/status.md`. CLI returns JSON on stdout; Builder reads verdict only.
- Rationale: mill-merge-in is not a task-lifecycle operation. It doesn't own status.md transitions. Adding status writes would couple merge-in to the task lifecycle unnecessarily and break the clean caller/callee separation.
- Rejected: Recording sub-agent session ID in status.md for debug traceability — the archive tag and git log already provide full trace.

## Technical context

### Existing implementer pattern
`millpy-implement.py` and `millpy-implement-holistic.py` define the canonical dispatch pattern:
1. `project_root = Path.cwd()`, resolve wiki, config, slug.
2. Update status (batch state → running) and commit on task branch. **Not applicable here — merge-in has no status tracking.**
3. Render brief template via `_render.render(template_path, tokens)`.
4. Call `_implementer_sonnet.run(prompt_text, session_id=..., resume=False, cwd=project_root, timeout=timeout)`.
5. Return `_forward_output(output, project_root)` — extracts last `{"status":...}` JSON from output.

`millpy-merge-in-subagent.py` follows the same shape but omits all status.md mutation.

### Path layout
Working state lives in `task/` on the task branch. `millpy-merge-in-subagent.py` is called from the worktree root (cwd), so `project_root = Path.cwd()` is the worktree root. It does **not** need `task/plan/` or `task/status.md` (no batch context, no status tracking).

### Conflict detection
After a non-clean `git merge`, conflicting files are enumerated via:
```bash
git diff --name-only --diff-filter=U
```
The SKILL.md conflict policy table (whitespace / lock files / build artefacts) is applied before spawning the sub-agent. Only unresolved "real code" conflicts reach the sub-agent.

### Verify commands
mill-merge-in's current Step 4 calls `_plan_dag.iter_batch_verifies(plan_dir)`. The `plan_dir` is `Path("task/plan/").resolve()`. When no plan exists (`iter_batch_verifies` returns `[]`), verify is skipped entirely. The verify-fix sub-agent is only spawned when a verify command actually fails; if iter_batch_verifies returns empty, no sub-agent is needed.

### _implementer_sonnet
`plugins/mill/scripts/_implementer_sonnet.py` — thin wrapper over `_llm_claude.run_implementer`. Spawns `claude -p --allowedTools Read,Edit,Write,Bash,Grep,Glob,Skill --output-format stream-json ...`. Returns `(text, session_id)`. Raises `_llm_claude.LLMError` on failure.

### _forward_output
`_implementer_common._forward_output(output: str, project_root: Path) -> int` — extracts the last `{"status":...}` JSON line from output, injects current HEAD sha as `commit_sha`, prints JSON to stdout. Returns 0.

### _render.render
`_render.render(template_path: Path, tokens: dict[str, str]) -> str` — substitutes `<TOKEN>` placeholders in template, strips the leading HTML comment. Returns the rendered prompt string.

### Config loading
`_review_common.load_config(wiki_path, mill_dir)` — deep-merges `<wiki_path>/config.yaml` with `.millhouse/config.local.yaml`. Returns merged dict.

### Timeout config
`cfg.get("llm", {}).get("implementer_timeout", 1800)` — used for both conflict and verify-fix sub-agent. No separate timeout key.

### plugin_root
`plugin_root = Path(__file__).resolve().parent.parent` — works correctly when script runs from the plugin cache.

### Verify output capture
The CLI runs each verify command via `subprocess.run([...], capture_output=True, text=True, cwd=project_root)`. On failure, captures stdout+stderr in memory. Also captures `git diff <checkpoint>..HEAD` output in memory. Both strings are passed as inline tokens to the verify-fix brief — no temp files. The sub-agent receives the full context without any file I/O.

## Constraints

No CONSTRAINTS.md at hub root. Constraints from CLAUDE.md and exploration:

- **Junctions never used by scripts.** `.wiki`, `.portals`, `.active` are IDE convenience only. `_paths.resolve_wiki_path` is the only way to get the wiki path.
- **`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths.** `plugin_root = Path(__file__).resolve().parent.parent` is the correct pattern inside scripts (equivalent at runtime).
- **Working state stays in `task/` on task branch.** The new CLI does NOT write to `task/` — it's a stateless dispatcher.
- **No junctions in recursive deletions.** Not relevant here — the sub-agent doesn't delete directories.
- **Verify output temp files go to `.scratch/`.** Per conversation skill File Writing rules: never `/tmp/`, never `$TEMP`, always `.scratch/` in the worktree root.
- **`_forward_output` returns 0 even on stuck.** Exit code 1 means pre-launch error (no JSON). The SKILL.md already handles both cases for per-batch implement; same convention applies here.

## Testing

### test-millpy-merge-in-subagent.py

Location: `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`

Setup: use `tempfile.TemporaryDirectory` (or `.scratch/` equivalent) for a minimal fake worktree with `.millhouse/active.slug.md` and wiki config files. Mock `_implementer_sonnet.run` to return `('{"status":"success",...}', 'fake-session-id')`.

Scenarios to cover:

**conflicts mode:**
- Happy path: conflicting files list → brief rendered with correct tokens → sub-agent returns success → stdout emits `{"status":"success",...}`.
- Sub-agent returns stuck → stdout emits `{"status":"stuck","stuck_type":"logic",...}`.
- No conflicting files passed → exit 1 on stderr, no JSON.
- `_implementer_sonnet.run` raises `LLMError` → stdout emits `{"status":"stuck","stuck_type":"transient",...}`, exit 1.

**verify-fix mode:**
- Happy path: verify output file + checkpoint + cmd → brief rendered correctly → success.
- Verify output file missing → exit 1.
- Sub-agent stuck → forwarded as-is.

**Shared:**
- Missing `--mode` → argparse error, exit 2.
- Missing `.millhouse/active.slug.md` → exit 1 with message.

TDD candidates: brief token set (verify tokens present in rendered output), `_forward_output` interaction (commit_sha injected).

## Q&A log

- **Q:** Single CLI or two CLIs for conflict vs. verify-fix? **A:** Single CLI `millpy-merge-in-subagent.py --mode conflicts|verify-fix`.
- **Q:** What context does the conflict sub-agent get? **A:** List of conflicting file paths only; sub-agent reads conflict markers itself.
- **Q:** What context does the verify-fix sub-agent get? **A:** Failing command, stdout+stderr output (temp file), and `git diff <checkpoint>..HEAD`.
- **Q:** Config key for verify-fix rounds? **A:** New `merge.verify_fix_rounds` (default 3) in config.
- **Q:** Should the sub-agent write to status.md? **A:** No — merge-in is not a task-lifecycle operation; Builder reads JSON verdict only.
- **Q:** Test approach? **A:** Unit test with mocked `_implementer_sonnet.run`; no new integration test.
- **Q:** Does the verify-fix loop run in the SKILL or the CLI? **A:** CLI is single-shot; sub-agent self-fixes internally up to `merge.verify_fix_rounds` times before reporting stuck. SKILL calls CLI once.
- **Q:** Does the conflict sub-agent commit or complete the merge? **A:** Sub-agent stages (`git add`) resolved files only. SKILL runs `git merge --continue` after success to create the merge commit.
- **Q:** Is verify output passed as a file path or inline content? **A:** Inline content in the brief token (`VERIFY_OUTPUT`). No temp file involved — captured in memory, embedded in brief.
- **Q:** Is the checkpoint rollback on stuck a new SKILL step or pre-existing? **A:** Pre-existing. The SKILL update maps `{"status":"stuck"}` verdict → existing rollback path (already described in SKILL.md Step 3 as "if unresolvable, roll back to checkpoint").
