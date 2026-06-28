# Plan: Fix review finding-count parser, nested-layout brief path, verify cwd, process leaks, and missing done-gate

```yaml
task: Fix review finding-count parser, nested-layout brief path, verify cwd, process leaks, and missing done-gate
slug: mill-verify-and-layout-gaps
approved: true
started: 20260628-054915
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: parser-and-brief
    file: 01-parser-and-brief.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-discussion-flow.py
  - number: 2
    name: implementer-cwd-and-dotnet
    file: 02-implementer-cwd-and-dotnet.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py
  - number: 3
    name: done-gate
    file: 03-done-gate.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
```

## Shared Decisions

### Decision: Python-project PYTHONPATH isolation

- **Decision:** Every `verify:` command starts with the literal `PYTHONPATH= ` (empty value, single space) prefix, per the mill-v2 convention for Python projects.
- **Rationale:** Prevents the test subprocess from inheriting the cache PYTHONPATH and loading stale V2-cache modules instead of worktree code.
- **Applies to:** all batches (all verify commands are Python test runners).

### Decision: New kw-args default to None for backward compat

- **Decision:** The new `git_root: Path | None = None` parameters added to `_run_verify_gate`, `_run_verify_gates`, `_forward_output`, and `finalize_from_output` default to `None`. When `None`, the function falls back to `project_root` for verify cwd — identical to today's behavior in flat layouts.
- **Rationale:** Flat layouts have `git_root == project_root`, so the fallback is zero-risk. Only nested-hub layouts pass a non-None `git_root`. No existing callers need to change.
- **Applies to:** batch 2 (implementer-cwd-and-dotnet).

### Decision: dotnet cleanup is Windows-only and best-effort

- **Decision:** The `dotnet build-server shutdown` call added after dotnet verify is guarded by `sys.platform == "win32"` and uses `subprocess.run` with `capture_output=True`, discarding the exit code.
- **Rationale:** Build-server locking only occurs on Windows (file-handle semantics). POSIX has no persistent build server. Failure to shut down is non-fatal; the intent is proactive cleanup, not a correctness gate.
- **Scope note:** `dotnet build-server shutdown` releases VBCSCompiler/MSBuild/Razor persistent servers. It does NOT kill orphaned `testhost.exe` processes from `dotnet test`. Reaping testhost processes (via `taskkill` or similar) is out of scope for this fix; #556 targets build-server locks only.
- **Applies to:** batch 2 (implementer-cwd-and-dotnet).

### Decision: done_gate null means disabled

- **Decision:** `pipeline.done_gate: null` in `mill-config.yaml` template means the gate is disabled; mill-go Handoff reads the key and runs the command only when it is a non-null string.
- **Rationale:** Backward compat: existing configs that lack the key get `null` from deep-merge. No existing task runs a done_gate unless the operator explicitly sets it.
- **Applies to:** batch 3 (done-gate).

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
