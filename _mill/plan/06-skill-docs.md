# Batch: skill-docs

```yaml
task: Instrument and bound the verify runner
batch: skill-docs
number: 6
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-brief-commit.py test-skill-helper-drift.py test-mill-go-base-agent-only.py test-agent-mode-dispatch.py
depends-on: [4, 5]
```

## Batch Scope

Updates the orchestrator SKILL text so the runner's timeout is the only bound on verify-running Bash calls (`run_in_background: true`, no Bash `timeout`), so `_done_gate` snippets pass `hub_root`, so merge-in replays go through `millpy-verify-run.py`, and so every `## Verify log` row is committed or survives rollback (the overview's "commit coverage" decision).
Docs only; no script changes.
Batch-local wording used in every card, quoted here once so all three cards say the same thing:

> Run this Bash call with `run_in_background: true` and no `timeout`. `pipeline.verify_timeout_minutes` bounds each verify command it runs, so the Bash tool's 10-minute cap must not cut it off first. Wait for the call's completion notification, then read its output; the JSON result is the last stdout line starting with `{`.

## Cards

### Card 12: mill-go-base verify-running calls run in the background

- **Context:**
  - `plugins/mill/scripts/_done_gate.py`
  - `plugins/mill/scripts/_verify_run.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/skills/mill-go-base/SKILL.md`, "## Agent-mode dispatch" step 5:
  - Replace the paragraph beginning "Give any `--stage finalize` call an extended Bash-tool timeout -- recommend 600000ms" and the scope sentence after it ("This timeout note is scoped to finalize calls ...") with: `millpy-implement.py --stage finalize` and `millpy-fix.py --stage finalize` replay `verify:` commands, so those Bash calls use the batch-local background wording above; review-CLI finalize calls run no verify and keep foreground calls.
  - In the following paragraph, replace "runs the batch's `verify:` command via `subprocess.run` with no `env=` override" with wording that it runs through `_verify_run.run_verify`, which inherits the orchestrator shell's environment and only adds `PYTHONIOENCODING`, `MSBUILDDISABLENODEREUSE` and `DOTNET_CLI_USE_MSBUILD_SERVER`; keep the PATH guidance.
  - Add one sentence to step 5: a finalize envelope that ran verify carries `verify_runs` (label, cmd, exit code, wall time, first-run, timed-out per command), and a timed-out gate is `stuck_type: verify` with `timed_out: true` and a `[verify timed out after <N>s: <label>]` reason prefix, handled by the existing verify stuck route; live progress is in `<git_root>/.scratch/verify/verify.log`.
  In "### 0.55. Done-gate baseline pre-flight": change the snippet's call to `_done_gate.run_preflight(gate_cmd, git_root, hub_root=hub_root)`, and replace the paragraph beginning "Give this Bash-tool call the same extended 600000ms" with the background wording.
  In `plugins/mill/skills/mill-go-base/handoff.md`, "0. Pre-done gate":
  - Change the snippet's call to `_done_gate.run_gate(gate_cmd, git_root, hub_root=hub_root)` (both the first run and the re-runs reuse this snippet).
  - Replace the paragraph beginning "Give this Bash-tool call the same extended 600000ms" with the background wording; note that the snippet's exit code arrives in the completion notification.
  - In the Fixer-dispatch check, before every lock-release/notify/halt on a still-`blocked` result (the step 2 still-blocked branch, its `retry`/`halt` sub-bullets, and step 3), add: when `git -C <worktree> status --porcelain -- <status_path>` is non-empty, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: keep verify log for blocked done gate"` and push, so the done gate's `## Verify log` rows are durable even though `phase: done` is not set.
- **Commit:** `docs(mill-go): run verify-replaying calls in the background, keep done-gate verify rows`

### Card 13: mill-quick done gate runs in the background

- **Context:**
  - `plugins/mill/scripts/_done_gate.py`
- **Edits:**
  - `plugins/mill/skills/mill-quick/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In "## Verify & Complete" step 1, change the snippet's call to `_done_gate.run_preflight(gate_cmd, git_root, hub_root=hub_root)` and replace the sentence beginning "Give this Bash-tool call an extended 600000ms (10-minute) timeout" with the batch-local background wording.
  Add one sentence noting that the run appends a `## Verify log` row to `status.md`, which the success-path `done` commit and the failure-path `blocked` commit both stage.
- **Commit:** `docs(mill-quick): run the done gate in the background`

### Card 14: mill-merge-in replays through millpy-verify-run and keeps rows across rollback

- **Context:**
  - `plugins/mill/scripts/millpy-verify-run.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-brief-commit.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Step 4 (Verify):
  - Replace "Run the command from that resolved cwd." with an invocation of the CLI: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-verify-run.py" --label "merge-in:<name>" --cmd "<cmd>" --cwd "<resolved cwd>"`, run with the batch-local background wording; success is exit 0 / `exit_code == 0` in its JSON.
  - On failure with `timed_out: true` in the CLI's JSON: skip the verify-fix dispatch entirely and go straight to the Rollback block, then escalate to the caller with the JSON's `reason`.
  - Otherwise on failure, the existing verify-fix dispatch, with `--label "merge-in:<name>"` added to `<args>` (agent mode) and to the subprocess/psmux command line.
    The verify-fix `--stage prepare` and `--stage finalize` Bash calls (agent mode) and the subprocess/psmux full-stage call all run verify, so each uses the background wording.
  - A `{"status": "stuck"}` line from the verify-fix prepare stage (timed-out or launch-failed initial verify, no dispatch) is handled exactly like a stuck finalize result: Rollback, then escalate.
  Step 5 (Commit dispatch briefs): in the bash block, after the existing `_mill/briefs/` staging, add `if [ -f <worktree>/_mill/status.md ]; then git -C <worktree> add _mill/status.md; fi` (relative pathspec, like the briefs line), and say in the prose that this commits the `## Verify log` rows written by step 4 before `mill-merge`'s cleanup commit removes `_mill/`.
  Keep the existing `git -C <worktree> add _mill/briefs/` line byte-identical; `test-brief-commit.py` locks it.
  "## Rollback": replace the single `git reset --hard "$CHK"` block with the four-step block from the discussion's "Verify log survives merge-in rollback" decision:
  1. a cache-form `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c` snippet resolving `status_path` exactly as Entry step 2 does and writing `json.dumps(_status.read_verify_log_rows(status_path) if status_path.exists() else [])` to `<git_root>/.scratch/verify/rollback-rows.json` (creating the directory);
  2. `git reset --hard "$CHK"` (unchanged);
  3. a snippet that reads that JSON, calls `_status.restore_verify_log_rows(status_path, rows)` when `status_path.exists()` and rows is non-empty, prints the count, and deletes the JSON file;
  4. when the count is above 0, `git add <status_path> && git commit -m "mill-merge-in: keep verify log across rollback"` and push.
  State that the checkpoint branch is still preserved and the escalation is unchanged, and that every rollback reference in steps 2-4 (each "roll back -> `git reset --hard "$CHK"`") now means this block.
- **Commit:** `docs(mill-merge-in): replay verify via millpy-verify-run and keep verify rows across rollback`

## Batch Tests

`verify:` runs the SKILL text locks: `test-brief-commit.py` (mill-merge-in step 5 staging line), `test-skill-helper-drift.py` (every `_<module>.<fn>(` reference in these SKILLs resolves to a shipped function, including the new `_status.read_verify_log_rows` / `restore_verify_log_rows` and the `_done_gate` calls), `test-mill-go-base-agent-only.py` and `test-agent-mode-dispatch.py` (mill-go-base structure).
All pass on this branch's base.
