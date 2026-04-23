# Batch: foundation

```yaml
task: codeguide sibling-mode + unified sibling-path convention
batch: foundation
cards: 2
verify: python plugins/mill/unit_tests/test-sibling.py
depends-on: []
```

## Batch Scope

Introduce `_sibling.py` as the single source of truth for sibling-path resolution. Publishes `resolve_path(role, repo_root) -> Path` that every consumer (mill-spawn, mill-setup, codeguide `resolve.py`) calls. Ship it with its unit tests so subsequent batches have something stable to depend on.

## Cards

### Card 1: `_sibling.py` helper

- **Reads:** `plugins/mill/scripts/_status.py`, `plugins/mill/scripts/_parent_branch.py` (pattern references for pure helpers), `CLAUDE.md` (convention reminders).
- **Modifies:** (none)
- **Creates:** `plugins/mill/scripts/_sibling.py`
- **Requirements:**
  - Expose `resolve_path(role: str, repo_root: Path) -> Path`.
  - Hub-form detection: exactly `repo_root.name == "hub"`. No alternative spellings, no case-insensitive match — `Hub/` or `HUB/` is NOT hub-form.
  - Hub-form branch returns `repo_root.parent / role`.
  - Non-hub branch returns `repo_root.parent / f"{repo_root.name}.{role}"`.
  - Module docstring explains the rule, the role whitelist (documentation, not enforced), and that the function NEVER touches disk — it is pure path arithmetic.
  - No reliance on git or subprocess calls. `repo_root` is an input; callers are responsible for resolving git-toplevel.
- **Commit:** `feat(sibling): add _sibling.py helper for uniform sibling-path resolution`

### Card 2: unit test for `_sibling.py`

- **Reads:** `plugins/mill/scripts/_sibling.py` (just authored), `plugins/mill/unit_tests/test-parent-branch.py` (template), `plugins/mill/unit_tests/run-all.py`.
- **Modifies:** (none)
- **Creates:** `plugins/mill/unit_tests/test-sibling.py`
- **Requirements:**
  - Cover every combination: role ∈ `{"wiki", "codeguide", "worktrees"}`, repo_root names `"hub"` and `"Models"` at minimum.
  - Assert hub-form path for `hub` parent, prefix-form path for every other name (including edge cases like empty-looking names or names with dots in them — the helper treats `.` as an ordinary character).
  - Verify the function does NOT touch disk (no mkdir, no stat). Using fake `Path` objects pointing at non-existent locations should return a valid computed path regardless.
  - Follow the same test-file scaffolding as the rest of `plugins/mill/unit_tests/` (sys.path insert, top-level `main()`, exit-code return).
- **Commit:** `test(sibling): unit tests for _sibling.resolve_path`

## Batch Tests

`verify:` runs `python plugins/mill/unit_tests/test-sibling.py`. On pass, `_sibling.py` is available to every downstream batch. The full unit-test runner (`run-all.py`) also picks up the new test file automatically — no manual wiring.
