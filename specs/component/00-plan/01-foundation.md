# Batch: foundation

```yaml
task: codeguide sibling-mode + unified sibling-path convention
batch: foundation
cards: 2
verify: python plugins/mill/unit_tests/test-sibling.py
depends-on: []
```

## Batch Scope

Introduce `_sibling.py` as the sibling-path helper for the mill plugin. Publishes `resolve_path(role, repo_root) -> Path` as the Python API and a `__main__` CLI entry point (`python _sibling.py <role> <repo_root>` → print resolved path). Ships with its unit test so downstream batches depend on something stable.

The `_sibling.py` in the codeguide plugin is created in a later batch (codeguide-plugin Card 4); this batch only creates mill's copy.

## Cards

### Card 1: `plugins/mill/scripts/_sibling.py`

- **Reads:** `plugins/mill/scripts/_parent_branch.py` (pattern reference for pure helpers), `plugins/mill/scripts/_subprocess_util.py` (pattern reference for modules that expose both Python API and a small CLI), `CLAUDE.md` (convention reminders — `${CLAUDE_PLUGIN_ROOT}` rule; no `__main__`-smoke-tests in helpers, but CLI entry points are allowed because they are production surface, not tests).
- **Modifies:** (none)
- **Creates:** `plugins/mill/scripts/_sibling.py`
- **Requirements:**
  - Expose `resolve_path(role: str, repo_root: Path) -> Path`.
  - Hub-form detection: exactly `repo_root.name == "hub"`. No alternative spellings, no case-insensitive match — `Hub/` or `HUB/` is NOT hub-form. Document this in the module docstring.
  - Hub-form branch returns `repo_root.parent / role`.
  - Non-hub branch returns `repo_root.parent / f"{repo_root.name}.{role}"`.
  - `role` is treated as a free string but the docstring lists the known roles (`"wiki"`, `"codeguide"`, `"worktrees"`). No runtime validation — callers pass what they need.
  - Pure path arithmetic. NEVER touches disk (no `mkdir`, no `stat`, no `resolve()`). `repo_root` is an input; callers are responsible for resolving git-toplevel.
  - **CLI entry point** (`if __name__ == "__main__":`) — parses `<role> <repo_root>` positionally, prints the resolved path to stdout, exits 0. Bad args print a one-line error to stderr and exit 2. This is production surface (used by SKILL.md subprocess invocations), not a smoke test. Keep it minimal: `import sys`, `argparse` or even just `sys.argv[1:]`. No asserts.
  - Module docstring calls out the rule, the CLI, and the fact that a parallel identical copy lives in the codeguide plugin — so anyone editing one remembers to sync the other.
- **Commit:** `feat(sibling): add _sibling.py helper + CLI for mill plugin`

### Card 2: `plugins/mill/unit_tests/test-sibling.py`

- **Reads:** `plugins/mill/scripts/_sibling.py` (just authored), `plugins/mill/unit_tests/test-parent-branch.py` (template), `plugins/mill/unit_tests/run-all.py`.
- **Modifies:** (none)
- **Creates:** `plugins/mill/unit_tests/test-sibling.py`
- **Requirements:**
  - Cover every combination: role ∈ `{"wiki", "codeguide", "worktrees"}`, repo_root names `"hub"` and `"Models"` at minimum.
  - Assert hub-form path for `hub` parent, prefix-form path for every other name (including edge cases like names with dots in them — the helper treats `.` as an ordinary character).
  - Assert that `Hub/` and `HUB/` produce prefix-form, NOT hub-form (case-sensitivity).
  - Verify the function does NOT touch disk — using fake `Path` objects pointing at non-existent locations should return a valid computed path regardless.
  - Cover the CLI entry point: invoke via `subprocess.run([sys.executable, module_path, role, repo_root])`, assert stdout is the expected path. Cover the arg-error path too (exit 2).
  - Follow the same test-file scaffolding as the rest of `plugins/mill/unit_tests/` (sys.path insert, top-level `main()`, exit-code return).
- **Commit:** `test(sibling): unit tests for _sibling.resolve_path + CLI`

## Batch Tests

`verify:` runs `python plugins/mill/unit_tests/test-sibling.py`. On pass, `_sibling.py` is stable for downstream batches. The full unit-test runner (`run-all.py`) picks up the new test automatically — no wiring needed.
