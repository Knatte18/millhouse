# Batch: done-gate

```yaml
task: Fix review finding-count parser, nested-layout brief path, verify cwd, process leaks, and missing done-gate
batch: done-gate
number: 3
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
depends-on: []
```

## Batch Scope

Adds the `pipeline.done_gate` feature (#561): a config key that lets operators specify a repo-wide test command that mill-go runs from `git_root` before marking a task `done`. When the gate fails, mill-go halts with a BLOCKED message. When `done_gate: null` (the default), behavior is unchanged. Changes span: the `mill-config.yaml` template (new key), `mill-go/SKILL.md` (new Handoff step), `mill-plan/SKILL.md` (documentation note about the gate), and `test-config.py` (regression test that the key is present and null in the template). No Python CLI scripts are modified.

## Cards

### Card 8: Add `pipeline.done_gate: null` to `mill-config.yaml` template (#561)

- **Context:**
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `plugins/mill/templates/mill-config.yaml`, in the `pipeline:` section (currently around line 119), add the `done_gate` key immediately after `autonomous_mode:`:

  ```yaml
  pipeline:
    auto_merge: false
    auto_report: true
    autonomous_mode: false  # Set true by mill-autofix; read by mill-go and mill-plan for autonomous stuck-handling
    done_gate: null  # Repo-wide test command run from git_root before marking done. null = disabled. e.g. "go test ./..." or "dotnet test". (#561)
    max_cards_per_batch: 10  # batch-oversized validator gate (#371)
    max_batch_context_tokens: 120000  # batch-oversized validator gate (#371)
  ```

  Only the insertion of the `done_gate: null` line matters; the surrounding lines must not be removed or reordered.
- **Commit:** `feat(mill-config): add pipeline.done_gate null key for repo-wide done gate (#561)`

---

### Card 9: Add pre-done gate step to `mill-go/SKILL.md` Handoff (#561)

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `mill-go/SKILL.md`, locate the Handoff section. Currently the sequence ends with a scope-violations check (line ~703-712) followed by step 1 (`_status.append_phase("done")` at line ~716). Insert a new numbered step between the scope-violations gate and step 1.

  The new step is titled **"0. Pre-done gate"** and reads:

  > **0. Pre-done gate.** Read `cfg.get("pipeline", {}).get("done_gate")` (deep-merged config). If the value is `None` or absent, skip. If it is a non-null string, run the command from `git_root` (not hub dir) as a best-effort verify:
  >
  > ```bash
  > PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  > import json, sys, subprocess
  > import _paths, _config, _subprocess_util
  > git_root = _paths.resolve_git_root()
  > hub_root = _paths.resolve_hub_path()
  > cfg = _config.load_config(hub_root, git_root)
  > gate_cmd = (cfg.get('pipeline') or {}).get('done_gate')
  > if not gate_cmd:
  >     sys.exit(0)
  > result = _subprocess_util.run_allow_fail(gate_cmd, cwd=git_root, shell=True)
  > if result.returncode != 0:
  >     out = (result.stdout + result.stderr).strip()
  >     reason = out[-2000:] if len(out) > 2000 else out
  >     print(json.dumps({'status': 'blocked', 'reason': f'done gate failed: {reason}'}))
  >     sys.exit(1)
  > # dotnet cleanup: if gate command contains 'dotnet' and we are on Windows,
  > # run build-server shutdown to release process locks before mill-finalize runs.
  > import platform
  > if platform.system() == 'Windows' and 'dotnet' in gate_cmd.lower():
  >     subprocess.run(['dotnet', 'build-server', 'shutdown'], capture_output=True, timeout=30)
  > "
  > ```
  >
  > Parse stdout for a JSON line. If the exit code is non-zero and the JSON line has `status: blocked`, halt with: `BLOCKED: done gate failed — <reason>`. Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can investigate the failure. The `run_allow_fail` helper does not raise on non-zero exit code; check `result.returncode`.

  The existing step 1 (`_status.append_phase(status_path, "done", ...)`) and later steps are renumbered accordingly (step 0 is inserted before the existing numbered steps, so the existing numbered list does not change — step 0 is new). The existing step text for "1. `_status.append_phase(status_path, 'done', ...)`" stays as-is.

  **Important:** `_subprocess_util.run_allow_fail` must exist (check the file). If it does not exist, use `subprocess.run(gate_cmd, cwd=git_root, shell=True, capture_output=True, text=True)` inline instead (no raise on non-zero). Inspect `_subprocess_util.py` via Context if needed — but do not add it to Context: if using inline subprocess, since the inline approach has no dependency on that helper. The SKILL.md text must be accurate about which approach is used.
- **Commit:** `feat(mill-go): add pre-done gate step to Handoff for repo-wide test guard (#561)`

---

### Card 10: Add done_gate note to `mill-plan/SKILL.md` (#561)

- **Context:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `mill-plan/SKILL.md`, in **Phase: Plan** after the **Verify command scope** subsection (or the closest natural paragraph about plan verify commands), add a short advisory note:

  > **Done-gate reminder.** If the plan's batch-verify scopes do not cover the entire module tree (the common case for scoped plans), consider setting `pipeline.done_gate` in `mill-config.yaml` to a cheap repo-wide test command (e.g. `go test ./...` for Go repos, `dotnet test` for .NET solutions). mill-go runs this command from `git_root` before marking the task `done`, catching regressions in packages outside the batch-verify scope. Leave `done_gate: null` (the default) if a repo-wide test would be too slow or is not meaningful for the project.

  Place this note as a standalone paragraph (not inside a list item or code block). The exact surrounding text will vary — find a natural break near the verify-command discussion.
- **Commit:** `docs(mill-plan): add done_gate reminder note in Phase Plan (#561)`

---

### Card 11: Add `pipeline.done_gate` config template test (#561)

- **Context:**
  - `plugins/mill/templates/mill-config.yaml`
  - `plugins/mill/unit_tests/test-config.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `test-config.py`, add a new test function `test_load_config_done_gate_key_present()` that:

  1. Uses the existing `_setup_plugin_template` helper and `unittest.mock.patch` pattern already present in the file.
  2. Calls `_config.load_config(hub_root, hub_root)` with a mocked `resolve_plugin_template_path` pointing at the real `plugins/mill/templates/mill-config.yaml` (resolve via `Path(__file__).resolve().parent.parent / "templates" / "mill-config.yaml"` or `HUB / "plugins" / "mill" / "templates" / "mill-config.yaml"`).
  3. Asserts `cfg.get("pipeline", {}).get("done_gate") is None` — the template key exists and its value is null.

  Add the function immediately before the `if __name__ == "__main__"` block (or wherever the other test functions are). Call it from `main()` and print `"PASS: pipeline.done_gate key present and null in template"` on success.

  This test does not require a hub overlay or local config — the template alone must provide the key.
- **Commit:** `test(config): verify pipeline.done_gate key is present and null in template (#561)`

## Batch Tests

The `verify:` command runs `test-config.py` directly (single-file form). This file tests the config loading layer and will pick up the new `test_load_config_done_gate_key_present` function. The SKILL.md changes (Cards 9 and 10) have no Python-testable surface; they are validated by manual integration when mill-go is next run with a non-null `done_gate` configured. The config template test (Card 11) is the regression pin: if `done_gate` is removed from the template or its value changes from null, the test fails.
