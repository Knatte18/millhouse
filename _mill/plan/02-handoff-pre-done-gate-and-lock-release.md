# Batch: handoff-pre-done-gate-and-lock-release

```yaml
task: "mill-go: done-gate halt path and cleanliness-gate recovery are under-documented"
batch: "handoff-pre-done-gate-and-lock-release"
number: 2
cards: 3
verify: null
depends-on: [1]
```

## Batch Scope

Rewrites `handoff.md`'s "0. Pre-done gate" section to call the new `_done_gate.run_gate` (batch 1) instead of inlining a raw `subprocess.run(shell=True, ...)` snippet, adds a conditional `mill-done-gate-fixer` dispatch before it halts, and brings all four of `handoff.md`'s halt points (pre-done-gate, unfixed-nits gate, terminal-dirt gate's three call sites, scope-violations gate) up to the same builder-lock-release + `_notify.notify` shape every other `BLOCKED:` halt in this file family already uses. This is one batch because all three cards edit the same file's halt-path prose and the discussion's own round-2/round-4 review findings caught cross-card consistency gaps (notify-parity wording, halt-site counts) that are easiest to keep coherent when authored together. Depends on batch 1 because Card 3 imports and calls `_done_gate.run_gate`, which does not exist until batch 1 lands.

## Cards

### Card 3: Rewrite "0. Pre-done gate" to call `_done_gate.run_gate`

- **Context:**
  - `plugins/mill/scripts/_done_gate.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `handoff.md`'s "0. Pre-done gate" section (`### 0. Pre-done gate` heading), replace the existing fenced bash block containing the inline Python snippet (the one starting `import json, sys, subprocess, platform` and ending with the Windows dotnet-cleanup `if platform.system() == 'Windows'` block) with:
  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  import json, sys
  import _paths, _config, _done_gate
  git_root = _paths.resolve_git_root()
  hub_root = _paths.resolve_hub_path()
  cfg = _config.load_config(hub_root, git_root)
  gate_cmd = (cfg.get('pipeline') or {}).get('done_gate')
  if not gate_cmd:
      sys.exit(0)
  result = _done_gate.run_gate(gate_cmd, git_root)
  print(json.dumps(result))
  sys.exit(1 if result['result'] == 'blocked' else 0)
  "
  ```
  Keep the paragraph immediately after this block ("Give this Bash-tool call the same extended 600000ms (10-minute) timeout...") unchanged — it still applies verbatim to the new snippet (`run_gate` still invokes the same potentially-slow `gate_cmd`). Replace the sentence "Parse stdout for a JSON line. If the exit code is non-zero and the JSON line has `status: blocked`, halt with: `BLOCKED: done gate failed — <reason>`." with: "Parse stdout for a JSON line. If the exit code is non-zero and the JSON line has `result: blocked`, proceed to the fixer-dispatch check below before halting." Delete the trailing sentence "`subprocess.run` with `capture_output=True` does not raise on non-zero exit code — check `result.returncode`." — it describes raw-`subprocess.run` semantics that no longer apply now that `_done_gate.run_gate` (which never raises) does the invocation. Keep the "Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can investigate the failure." sentence — it still applies and stays immediately before the numbered `1. _status.append_phase(status_path, "done", ...)` step that follows.
- **Commit:** `refactor(handoff): call _done_gate.run_gate instead of inline subprocess.run`

### Card 4: Add conditional `mill-done-gate-fixer` dispatch and lock-release/notify to Pre-done gate's halt

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Immediately after Card 3's "proceed to the fixer-dispatch check below before halting" sentence, add a new "fixer-dispatch check" step, replacing the section's final `BLOCKED: done gate failed — <reason>` halt with the following control flow (the halt itself moves to the end of this new logic, not immediately after the JSON parse):
  1. Check whether `<git_root>/.claude/agents/mill-done-gate-fixer.md` exists (a plain filesystem existence check, e.g. `Path(git_root, ".claude", "agents", "mill-done-gate-fixer.md").exists()`).
  2. **If it exists:** dispatch it once via `Agent(subagent_type: "mill-done-gate-fixer")` — not through the CLI prepare/finalize family `SKILL.md`'s "## Agent-mode dispatch" documents for implementer/reviewer/fixer — with a brief naming the plan overview (`<plan_dir>/00-overview.md`), the configured `done_gate` command (`gate_cmd`), and the captured failure output (the JSON's `reason` field). Wait for the dispatch to complete, then re-run the same "0. Pre-done gate" snippet from Card 3 once more (a second `_done_gate.run_gate(gate_cmd, git_root)` call). If this re-run's `result['result'] == 'ok'`, proceed to the existing numbered step 1 (`_status.append_phase(status_path, "done", ...)`) as normal — the gate now passes. If it is still `'blocked'`: release the builder lock and notify (`_notify.notify("<VARIANT_LABEL>.blocked", "done gate failed", slug=slug)` then `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release`), then halt with `BLOCKED: done gate failed — <reason>` (the re-run's `reason` field), appending the note "mill-done-gate-fixer was already attempted and did not resolve the failure."
  3. **If it does not exist:** skip the dispatch entirely and go straight to the same lock-release/notify sequence and halt as step 2's still-blocked branch, but without the "already attempted" note — `BLOCKED: done gate failed — <reason>` using the original run's `reason` field.
  Keep the existing "Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can investigate the failure." sentence attached to both halt outcomes in step 2 and step 3 above.
- **Commit:** `feat(handoff): dispatch mill-done-gate-fixer on done-gate failure when registered`

### Card 5: Add builder-lock release and `_notify.notify` to the other three `handoff.md` halt points

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `_notify.notify(...)` immediately followed by the builder-lock release call, immediately before each of the following three existing `BLOCKED:` halt messages in `handoff.md` (unchanged message text, only the two new calls inserted directly above each):
  - **Nit-enforcement gate** halt: "`BLOCKED: unfixed nits in scope(s): <scope-list> -- NIT-fix pass did not clear them`" — insert `_notify.notify("<VARIANT_LABEL>.blocked", f"unfixed nits in scope(s): {scope_list}", slug=slug)` then `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release`.
  - **Terminal cleanliness gate**, all three of its `BLOCKED:` call sites (the initial `in_scope_dirt is None` check, the re-check after self-resolve — which shares the same message text as the initial check, so both need the two calls inserted independently even though the halt message itself is identical — and the still-non-empty case): insert `_notify.notify("<VARIANT_LABEL>.blocked", "cannot determine in-scope dirt at task completion", slug=slug)` then the same lock-release call before the first two call sites (the `in_scope_dirt is None` message, both occurrences), and `_notify.notify("<VARIANT_LABEL>.blocked", "dirty working tree at task completion", slug=slug)` then the same lock-release call before the still-non-empty case's `BLOCKED: dirty working tree at task completion -- ...` message.
  - **Scope violations cleanup gate** halt: "`BLOCKED: out-of-scope untracked file(s): <file-list>`" — insert `_notify.notify("<VARIANT_LABEL>.blocked", f"out-of-scope untracked file(s): {file_list}", slug=slug)` then the same lock-release call.
  Do not add `batch=` to any of these four gates' `_notify.notify` calls — all four are task-scoped, not batch-scoped, and have no `batch_name` in scope (unlike `SKILL.md`'s canonical `### Blocked` section, which passes `batch=batch_name` because it fires mid-batch). Do not modify any halt message text, the "Do NOT set `phase: done`" sentences, or any other prose in these three gates beyond inserting the two new calls at each of the four total call sites (1 + 3 + 1... i.e. nit-gate ×1, terminal-dirt ×3, scope-violations ×1 = 5 insertion points across three gates — Card 4 already handled the sixth insertion point, pre-done-gate's own halt).
- **Commit:** `feat(handoff): release builder lock and notify on nit/terminal-dirt/scope-violation halts`

## Batch Tests

`verify: null` — this batch edits only `handoff.md`, an orchestrator-prose skill file with no runnable Python surface. Per `_mill/discussion.md`'s Testing section, mill-pause/handoff-style prose changes are not exercisable by mill's Python unit-test suite (in-memory/tempfile fixtures, no real git/LLM); correctness here is verified by holistic plan/code review scrutiny of the prose itself (does the fixer-dispatch control flow route correctly, does every halt site actually gain both new calls).
