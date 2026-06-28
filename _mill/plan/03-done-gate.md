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
  > import json, sys, subprocess, platform
  > import _paths, _config
  > git_root = _paths.resolve_git_root()
  > hub_root = _paths.resolve_hub_path()
  > cfg = _config.load_config(hub_root, git_root)
  > gate_cmd = (cfg.get('pipeline') or {}).get('done_gate')
  > if not gate_cmd:
  >     sys.exit(0)
  > result = subprocess.run(gate_cmd, cwd=git_root, shell=True, capture_output=True, text=True)
  > if result.returncode != 0:
  >     out = (result.stdout + result.stderr).strip()
  >     reason = out[-2000:] if len(out) > 2000 else out
  >     print(json.dumps({'status': 'blocked', 'reason': f'done gate failed: {reason}'}))
  >     sys.exit(1)
  > # dotnet cleanup: if gate command contains 'dotnet' and we are on Windows,
  > # run build-server shutdown to release process locks before mill-finalize runs.
  > if platform.system() == 'Windows' and 'dotnet' in gate_cmd.lower():
  >     subprocess.run(['dotnet', 'build-server', 'shutdown'], capture_output=True, timeout=30)
  > "
  > ```
  >
  > Parse stdout for a JSON line. If the exit code is non-zero and the JSON line has `status: blocked`, halt with: `BLOCKED: done gate failed — <reason>`. Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can investigate the failure. `subprocess.run` with `capture_output=True` does not raise on non-zero exit code — check `result.returncode`.

  The existing step 1 (`_status.append_phase(status_path, "done", ...)`) and later steps are renumbered accordingly (step 0 is inserted before the existing numbered steps, so the existing numbered list does not change — step 0 is new). The existing step text for "1. `_status.append_phase(status_path, 'done', ...)`" stays as-is.

  The snippet above uses inline `subprocess.run` with `capture_output=True` — `_subprocess_util` is NOT imported in this snippet (it does not expose a `run_allow_fail` helper). The SKILL.md text must exactly match the snippet above.
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
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/unit_tests/test-config.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `test-config.py`, add a new test function `test_load_config_done_gate_key_present()` that:

  1. Does NOT use `_setup_plugin_template` (which seeds a synthetic template that lacks the new `done_gate` key and would make the assertion meaningless).
  2. Resolves the real template path via `Path(__file__).resolve().parent.parent / "templates" / "mill-config.yaml"` and patches `_config`'s `resolve_plugin_template_path` (or whichever internal call `_config.load_config` makes to locate the template) to return this real path.
  3. Creates a minimal temp hub dir (no overlay `mill-config.yaml`) and calls `_config.load_config(hub_root, hub_root)` against it.
  4. Asserts `cfg.get("pipeline", {}).get("done_gate") is None` — the key must exist in the template and its value must be null.

  The pattern to use: inspect the existing `test-config.py` tests that do NOT use `_setup_plugin_template` and follow their pattern for pointing at the real template. If all existing tests use `_setup_plugin_template`, add the real-template fixture as a one-off in this test function. The goal is to assert against the actual shipped template, so that removing `done_gate` from the template breaks the test.

  Add the function immediately before the `if __name__ == "__main__"` block. Call it from `main()` and print `"PASS: pipeline.done_gate key present and null in template"` on success.
- **Commit:** `test(config): verify pipeline.done_gate key is present and null in template (#561)`

## Batch Tests

The `verify:` command runs `test-config.py` directly (single-file form). This file tests the config loading layer and will pick up the new `test_load_config_done_gate_key_present` function. The SKILL.md changes (Cards 9 and 10) have no Python-testable surface; they are validated by manual integration when mill-go is next run with a non-null `done_gate` configured. The config template test (Card 11) is the regression pin: if `done_gate` is removed from the template or its value changes from null, the test fails.
