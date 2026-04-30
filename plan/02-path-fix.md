# Batch: path-fix

```yaml
task: 18 — par-E — Migrate Python invocation to `uv run`
batch: path-fix
cards: 3
verify: uv run --project plugins/mill plugins/mill/scripts/millpy-vscode.py --help
depends-on: [foundation]
```

## Batch Scope

Apply the cmd.exe wrapper PATH-fix pattern to the three scripts that look up Windows-Apps-installed external tools (`code.cmd`, `claude`). All three currently use `shutil.which(...)` which fails when the parent process is non-interactive (debugpy, CC's Bash tool) because WindowsApps is not added to subprocess PATH. The fix is uniform: replace the lookup with a `["cmd", "/c", "<tool>", ...]` argv that lets cmd.exe resolve the tool against its full interactive PATH. discussion.md describes millpy-vscode as "already partially patched" — this is incorrect on inspection; the actual code at `plugins/mill/scripts/millpy-vscode.py:44-55` uses `shutil.which` and the cmd-wrapper pattern is NOT applied. Implementer must apply the fix in all three files. This batch is independent of `foundation` because the changes do not require uv (the `verify:` runs uv only because that's the canonical way to run scripts post-migration; functionally, the changes work with bare `python` too).

## Cards

### Card 4: Apply cmd-wrapper PATH-fix in `millpy-vscode.py`

- **Reads:**
  - `plugins/mill/scripts/millpy-vscode.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-vscode.py`
- **Creates:** none
- **Requirements:** Refactor `_build_code_argv` so that on Windows it returns `["cmd", "/c", "code", str(worktree_path)]` (cmd.exe resolves `code.cmd` against the full interactive PATH including WindowsApps). Drop the `shutil.which("code.cmd") or shutil.which("code") or <fallback>` chain and the `os.path.join` LOCALAPPDATA fallback — cmd.exe handles all of those. Keep the function signature and the calling code (`subprocess.run(code_argv)` at the bottom of `main`) unchanged. Remove the now-unused `import os` only if no other reference to `os` remains in the file (grep before deleting). Keep `import shutil` only if other code in the file uses it (grep before deleting). On non-Windows platforms (where `os.name != "nt"`), use `["code", str(worktree_path)]` directly — no cmd wrapper needed; PATH inheritance works correctly on POSIX. Smoke-check: `uv run --project plugins/mill plugins/mill/scripts/millpy-vscode.py --help` exits 0; `uv run --project plugins/mill plugins/mill/scripts/millpy-vscode.py --list` runs to completion.
- **Commit:** `fix(mill-vscode): use cmd.exe wrapper for code.cmd PATH resolution`

### Card 5: Apply cmd-wrapper PATH-fix in `millpy-terminal.py`

- **Reads:**
  - `plugins/mill/scripts/millpy-terminal.py`
  - `plugins/mill/scripts/millpy-vscode.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-terminal.py`
- **Creates:** none
- **Requirements:** Replace the line `claude = shutil.which("claude") or "claude"` plus the immediately-following `subprocess.run([claude, "--name", selected_slug], cwd=launch_path)` with a Windows/POSIX branch that on Windows runs `subprocess.run(["cmd", "/c", "claude", "--name", selected_slug], cwd=launch_path)` and on POSIX runs `subprocess.run(["claude", "--name", selected_slug], cwd=launch_path)`. Mirror the conditional shape used in card 4 (`millpy-vscode.py`) for consistency. Drop `import shutil` if no other code in the file uses it. Smoke-check: `uv run --project plugins/mill plugins/mill/scripts/millpy-terminal.py --help` exits 0.
- **Commit:** `fix(mill-terminal): use cmd.exe wrapper for claude PATH resolution`

### Card 6: Apply cmd-wrapper PATH-fix in `_llm_claude.py`

- **Reads:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/millpy-terminal.py`
- **Modifies:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Requirements:** Replace the `_resolve_claude() -> str` helper at lines 37-51 with a new helper `_claude_argv_prefix() -> list[str]` that returns `["cmd", "/c", "claude"]` on Windows (`os.name == "nt"`) and `["claude"]` on POSIX. Update the call site at line 94 (`argv = [_resolve_claude(), "-p", ...]`) to `argv = [*_claude_argv_prefix(), "-p", ...]`. Search the rest of `_llm_claude.py` for any other use of `_resolve_claude` and update each call site to use the new prefix-list spread. Drop `import shutil` if no other code uses it (grep before removing). Update the docstring of the new helper to explain the WindowsApps PATH-truncation rationale (cite discussion.md § "PATH truncation in debugpy/subprocess environments"). Preserve all other behaviour: timeouts, env, stream-json output, error handling. Smoke-check: `uv run --project plugins/mill python -c "import _llm_claude; print('ok')"` exits 0.
- **Commit:** `fix(_llm_claude): use cmd.exe wrapper for claude review subprocess`

## Batch Tests

`verify:` runs `uv run --project plugins/mill plugins/mill/scripts/millpy-vscode.py --help` — exits 0 if the script is importable and argparse parses cleanly. The semantic correctness of the cmd-wrapper fix is verified manually by the operator (running the scripts in a debugpy or non-interactive context and confirming the external tool launches). Per-card smoke-checks cover importability of each script. The `_llm_claude.py` change is exercised by the existing review subsystem; the smoke import in card 6 is the minimum bar; full verification happens when batch 03/04 SKILL.md changes flow through to a real mill-go run after the task is merged. No new tests added — the existing integration-test suite (`plugins/mill/integration_tests/test-review-*.py`) already covers `_llm_claude.py` invocation and will be migrated to `uv run` in batch 05.
