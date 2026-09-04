# Batch: done-gate-run-gate

```yaml
task: "mill-go: done-gate halt path and cleanliness-gate recovery are under-documented"
batch: "done-gate-run-gate"
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-done-gate.py
depends-on: []
```

## Batch Scope

Adds `_done_gate.run_gate(gate_cmd, git_root) -> dict` — a classifier-safe, DRY sibling to the existing `_done_gate.run_preflight` that `handoff.md`'s "0. Pre-done gate" block will call in batch 2 instead of inlining a raw `subprocess.run(shell=True, ...)` snippet directly in a Bash-tool Python call. This is the root dependency of the whole plan: batch 2's Handoff rewrite imports and calls `run_gate`, so this batch lands first. No other batch touches `_done_gate.py` or `test-done-gate.py`.

## Cards

### Card 1: Add `run_gate()` to `_done_gate.py`

- **Context:**
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Edits:**
  - `plugins/mill/scripts/_done_gate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `import platform` to the existing import block (alongside `import subprocess` and `from pathlib import Path`). Add `run_gate(gate_cmd: str, git_root: Path) -> dict` immediately after `run_preflight` in the same module. Implementation:
  - Call `subprocess.run(gate_cmd, cwd=git_root, shell=True, capture_output=True, text=True)` inside a `try/except Exception as exc` block identical in shape to `run_preflight`'s own — on any exception from the subprocess launch itself, return `{"result": "blocked", "reason": str(exc)}` (same never-raise contract `run_preflight` documents).
  - On `result.returncode != 0`: build `reason` using the identical stdout+stderr concatenation and 2000-character tail truncation `run_preflight` already implements (`out = (result.stdout + result.stderr).strip(); reason = out[-2000:] if len(out) > 2000 else out`) and return `{"result": "blocked", "reason": reason}`.
  - On `result.returncode == 0`: if `'dotnet' in gate_cmd.lower()` and `platform.system() == 'Windows'`, attempt `subprocess.run(['dotnet', 'build-server', 'shutdown'], capture_output=True, timeout=30)` wrapped in its own inner `try/except Exception: pass` — this mirrors the Windows-only dotnet cleanup currently inlined at the end of `handoff.md`'s "0. Pre-done gate" Python snippet (see `handoff.md` lines ~118-121 for the exact condition and call being ported), and a failure in this best-effort cleanup must never turn a successful gate result into a raised exception. Then return `{"result": "ok"}`.
  - No `"skipped"` result case — unlike `run_preflight`, `run_gate`'s caller (`handoff.md`'s "0. Pre-done gate") already checks `gate_cmd is None` before ever calling this function, so `run_gate` assumes `gate_cmd` is a non-null string.
  - Update the module's top docstring: add a `run_gate(gate_cmd, git_root) -> dict` line to the existing `Public API:` list, in the same style as the `run_preflight` entry immediately above it — state that it additionally performs the Windows dotnet-build-server-shutdown cleanup on success and has no `"skipped"` case. Add a function docstring on `run_gate` itself, in the same style as `run_preflight`'s docstring, noting: this function mirrors `run_preflight`'s subprocess-invocation shape and never-raise contract exactly, is the call site `handoff.md`'s "0. Pre-done gate" now uses in place of its own inline `subprocess.run`, and that callers needing an exit-code-based halt contract (as Handoff does) must branch on the returned `result["result"] == "blocked"` themselves — `run_gate` itself never calls `sys.exit`.
- **Commit:** `feat(done-gate): add run_gate() classifier-safe gate invocation`

### Card 2: Add unit tests for `run_gate` to `test-done-gate.py`

- **Context:**
  - `plugins/mill/scripts/_done_gate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-done-gate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `from _done_gate import run_preflight` import's companion `run_gate` to the existing `from _done_gate import run_preflight` line (import both names). Add new numbered cases 6-9 to `main()`, following the file's existing `# Case N: ...` / `try/except AssertionError` / `PASS`/`FAIL` print pattern used by cases 1-5, mocking `_done_gate.subprocess.run` and, where needed, `_done_gate.platform.system` — no real shell command or platform call is ever executed:
  - **Case 6:** mocked `subprocess.run` returns `returncode=0`; `gate_cmd` does not contain `'dotnet'`. Assert `run_gate(gate_cmd, git_root) == {"result": "ok"}` and assert `subprocess.run` (the mock) was called exactly once — the dotnet-shutdown branch must not fire when `'dotnet'` is absent from `gate_cmd`, regardless of platform.
  - **Case 7:** mocked `subprocess.run` returns `returncode=0` on its first call; `gate_cmd` contains `'dotnet'` (e.g. `"dotnet test foo.csproj"`); `_done_gate.platform.system` mocked to return `"Windows"`. Assert the result is `{"result": "ok"}` and assert the mock's second call was `["dotnet", "build-server", "shutdown"]` with `capture_output=True, timeout=30` (inspect `mock_run.call_args_list[1]`).
  - **Case 8:** identical setup to Case 7 except `_done_gate.platform.system` mocked to return `"Linux"`. Assert the result is still `{"result": "ok"}` and assert `subprocess.run` (the mock) was called exactly once — the dotnet-shutdown branch must not fire on a non-Windows platform even when `'dotnet'` is present in `gate_cmd`.
  - **Case 9:** mocked `subprocess.run` returns `returncode=1` with `stdout` set to a 3000-character string and empty `stderr`. Assert `result["result"] == "blocked"` and `len(result["reason"]) == 2000` and `result["reason"] == long_output[-2000:]` — the same tail-truncation shape as `run_preflight`'s own Case 4, confirming `run_gate` reuses the identical truncation logic.
  - Update the module docstring at the top of `test-done-gate.py` to note it now also covers `_done_gate.run_gate`.
- **Commit:** `test(done-gate): cover run_gate() success/dotnet-cleanup/failure paths`

## Batch Tests

`verify:` runs the full `test-done-gate.py` file (both the existing `run_preflight` cases and this batch's new `run_gate` cases) — the whole file is one cohesive unit for `_done_gate.py`, small and fast (mocked subprocess only, no real shell/network I/O), so the unbounded per-file run is appropriately scoped, not the unbounded-suite carve-out.
