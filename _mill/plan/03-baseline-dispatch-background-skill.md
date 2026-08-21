# Batch: baseline-dispatch-background-skill

```yaml
task: "mill-go: baseline-stage timeout/cold-build cost and finalize dirty-tree false positive"
batch: baseline-dispatch-background-skill
number: 3
cards: 1
verify: "PYTHONPATH= grep -q millpy-bg.py plugins/mill/skills/mill-go-base/SKILL.md"
depends-on: []
```

## Batch Scope

Fixes the dispatch-ceiling half of Bug A (issues #897, #875): `mill-go-base/SKILL.md`'s "0.5. Baseline pre-flight" and "0.6. Per-batch baseline recapture (self-hosting only)" sections currently dispatch `millpy-implement.py --stage baseline` as a foreground Bash-tool call with a documented 600000ms (10-minute) timeout, which has twice been observed to time out on tasks with several slow batch `verify:` commands. This batch switches both sections to the `millpy-bg.py` background-dispatch-and-poll pattern already established elsewhere in this codebase (`mill-start/SKILL.md`'s discussion-review subprocess/psmux branch, and throughout `mill-plan/SKILL.md`), removing the Bash-tool timeout ceiling entirely. "0.6" preserves its existing, documented `<git_root>`-form inner-command exception (the self-hosting cache-vs-worktree distinction) — only its outer `millpy-bg.py` wrapper call becomes cache-form; "0.5" has no such exception and both its outer and inner commands stay cache-form. This is a prose/orchestration-instruction edit only — no code, no runnable test surface of its own (see `_mill/discussion.md`'s Testing section).

## Cards

### Card 6: switch "0.5"/"0.6" baseline dispatch to millpy-bg background+poll

- **Context:**
  - `CLAUDE.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  **6a. "0.5. Baseline pre-flight" — replace the dispatch block.** Locate the fenced bash block immediately after the paragraph beginning `Immediately before "### 1.` (in the pre-edit file, this is the block directly under the "### 0.5. Baseline pre-flight (first batch of the task only)" heading):

  ```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" --stage baseline
  ```

  Replace it with the following (a pwd-guard note, the new dispatch block, and the poll+liveness-check instructions — insert all of it in place of the single old bash block above):

  > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
      --slug baseline-preflight -- \
      "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" --stage baseline
  ```

  This returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until the line `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
  ```

  Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed; `"dead"` -> surface a clear message to the operator: "baseline pre-flight worker died (logout?); re-run the baseline pre-flight step" and halt. Once `[mill-bg] EXIT` appears, run `grep '^{' <log-path>` to extract the two JSON summary lines.

  **6b. "0.5" — adjust the parse-source reference.** In the paragraph immediately following (beginning `(no `batch_name` positional argument`), change the phrase `Parse the two JSON lines the CLI prints` to `Parse the two JSON lines extracted above`. Leave the rest of that paragraph (the substage-shape descriptions, the idempotency note, the error/skipped handling) unchanged.

  **6c. "0.5" — replace the timeout paragraph.** Replace this exact paragraph (the last paragraph in the "0.5" section, immediately before the "### 0.6." heading):

  ```
Give this Bash-tool call the same extended 600000ms (10-minute) timeout recommended for finalize-stage verify replays above: `--stage baseline`'s `per_batch` substage replays every batch's `verify:` command to seed `verify_baseline_failures`, which is an arbitrary, potentially slow project command with no bound on runtime, sharing the identical default-2-minute-Bash-timeout risk that motivated the original finalize-stage-CLI fix.
  ```

  with:

  ```
  This background-dispatch-and-poll pattern removes the Bash-tool timeout ceiling entirely, instead of relying on a capped foreground call: `--stage baseline`'s `per_batch` substage replays every batch's `verify:` command to seed `verify_baseline_failures`, an arbitrary, potentially slow project command with no bound on runtime, and a capped foreground Bash-tool call -- even at the 600000ms (10-minute) ceiling previously recommended here -- has twice been observed to time out on tasks with several slow batch verify commands (#897, #875).
  ```

  **6d. "0.6. Per-batch baseline recapture (self-hosting only)" — replace the dispatch block.** In the "**Invoke.**" subsection, locate the fenced bash block:

  ```bash
PYTHONPATH="<git_root>/plugins/mill/scripts" "$MILL_PYTHON" "<git_root>/plugins/mill/scripts/millpy-implement.py" --stage baseline
  ```

  Replace it with the following (a pwd-guard note, the new dispatch block, and the poll instruction — insert all of it in place of the single old bash block above):

  > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
      --slug baseline-recapture -- \
      "$MILL_PYTHON" "<git_root>/plugins/mill/scripts/millpy-implement.py" --stage baseline
  ```

  Poll the same way "0.5. Baseline pre-flight" does above (`cat <log-path>` for `[mill-bg] EXIT`, with the same `_bg.check_bg_status` liveness-check branch, parsed as `(status, pid_or_code)`: `"running"` -> keep polling, `"exit"` -> proceed, `"dead"` -> surface a clear message and halt), then run `grep '^{' <log-path>` to extract the two JSON summary lines.

  **6e. "0.6" — replace the cache-form-exception paragraph.** Replace this exact two-sentence paragraph immediately after the (now-replaced) bash block:

  ```
Substitute the literal `git_root` path resolved at Path Setup — do NOT use `${CLAUDE_PLUGIN_ROOT}` here;
this is the one deliberate, narrow exception to the cache-form convention (see the plan overview's "cache-vs-worktree execution path for the retry" Shared Decision and root `CLAUDE.md`'s "Hard constraints" / "Path invariants").
  ```

  with:

  ```
  Substitute the literal `git_root` path resolved at Path Setup for the INNER `millpy-implement.py` command only — do NOT use `${CLAUDE_PLUGIN_ROOT}` there; this is the one deliberate, narrow exception to the cache-form convention (see the plan overview's "cache-vs-worktree execution path for the retry" Shared Decision and root `CLAUDE.md`'s "Hard constraints" / "Path invariants"). The OUTER `millpy-bg.py` wrapper call stays cache-form (`${CLAUDE_PLUGIN_ROOT}`), matching every other `millpy-bg` call site in this file family (e.g. "0.5. Baseline pre-flight" above).
  ```

  **6f. "0.6" — adjust the parse-source reference and failure-handling wording.** In the sentence beginning `Parse the two JSON lines this call prints`, change `Parse the two JSON lines this call prints` to `Parse the two JSON lines extracted above`. In the "**Failure handling.**" paragraph, replace this exact sentence:

  ```
Any failure of this invocation — non-zero exit, timeout, malformed or missing JSON output on either line, or `--stage baseline` not yet existing in the worktree's mid-development code — is logged (ASCII-only) and treated as a no-op: proceed to this batch's normal strict-mode finalize exactly as if no recapture had been attempted.
  ```

  with:

  ```
  Any failure of this invocation — non-zero exit, a `dead` liveness-check result (the worker died mid-run), malformed or missing JSON output on either line, or `--stage baseline` not yet existing in the worktree's mid-development code — is logged (ASCII-only) and treated as a no-op: proceed to this batch's normal strict-mode finalize exactly as if no recapture had been attempted.
  ```

  Leave the section's final sentence ("Never escalate to `stuck`/blocked over a recapture failure.") unchanged. Do not touch "### 1. Implement" or any section after it.
- **Commit:** `docs(mill-go): dispatch --stage baseline via millpy-bg background+poll instead of a capped foreground Bash call (#897, #875)`

## Batch Tests

`verify:` is a grep-based smoke check (`grep -q millpy-bg.py plugins/mill/skills/mill-go-base/SKILL.md`) confirming the new dispatch pattern's marker string is present in the edited file — this batch is prose/orchestration-instruction only with no runnable code surface of its own; the underlying `millpy-bg.py`/`_bg.check_bg_status` mechanics this card reuses already have their own existing test coverage from the `mill-plan`/`mill-start` call sites that established the pattern (see `_mill/discussion.md`'s Testing section). Real verification is a manual dry-run: the next mill-go run against a task with a configured `verify:` command exercises "0.5. Baseline pre-flight" end-to-end and confirms the two JSON summary lines are still parsed correctly from the background log.
