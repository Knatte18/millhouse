# Batch: foundation

```yaml
task: 57 (A) -- Move config.yaml and agents.yaml from wiki to hub worktree
batch: foundation
number: 1
cards: 7
verify: python plugins/mill/unit_tests/test-paths.py && python plugins/mill/unit_tests/test-autonomous.py
depends-on: []
```

## Batch Scope

This batch lays the additive foundation: the two new plugin templates (`mill-config.yaml`, `mill-agents.yaml`), the new `_autonomous.py` flag-file API, the new `_paths.resolve_mill_config_path` helper, accompanying unit tests, and the CLAUDE.md docs update. Nothing in this batch changes the behaviour of existing callers -- old templates (`wiki-config.yaml`, `reviewers.yaml`, `config.machine.yaml`) and old code paths (`_machine`, `wiki/config.yaml` reads) keep working untouched. Batch 2 (loaders refactor) and Batch 3 (mill-setup migration) consume the new templates and helpers added here; batch 4 deletes the old templates after both refactors have landed.

External interface for next batches: `_paths.resolve_mill_config_path(repo_root) -> Path`; the two template files at the standard plugin paths; the `_autonomous` module's three functions.

Batch-local decisions:

- The new `mill-agents.yaml` plugin template's content is a verbatim copy of production `C:/Code/millhouse/wiki/agents.yaml` (12 entries). No edits to entries themselves -- only the header comment is new.
- The new `mill-config.yaml` plugin template's content is a verbatim copy of the existing plugin template `plugins/mill/templates/wiki-config.yaml`, modulo the header comment block which is rewritten to document overlay precedence + env-var registry. The existing template does NOT contain `pipeline.autonomous_mode`, so no key-removal is needed in this batch.

## Cards

### Card 1: Add `_paths.resolve_mill_config_path` helper

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new public function `resolve_mill_config_path(repo_root: Path) -> Path` that returns `repo_root / "mill-config.yaml"`. Place it next to `resolve_wiki_path` in source order. Add the string `"resolve_mill_config_path"` to the existing `__all__` list immediately after `"resolve_wiki_path"`. The function is a one-line return; no I/O, no validation, no existence check. Match the docstring style of the surrounding helpers (one-sentence summary, "Args:" and "Returns:" blocks).
- **Commit:** `feat(paths): add resolve_mill_config_path helper`

### Card 2: Cover `resolve_mill_config_path` in `test-paths.py`

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a test function `test_resolve_mill_config_path_returns_repo_root_yaml` that constructs an arbitrary `repo_root` (use `tmp_path` from pytest if the surrounding test style is pytest, else a hand-rolled `Path("/some/repo")`), calls `_paths.resolve_mill_config_path(repo_root)`, and asserts the return is `repo_root / "mill-config.yaml"`. Match the import / runner pattern used by adjacent tests in the same file (do NOT introduce pytest if the file currently uses a different runner). Single test function is sufficient -- the helper is a one-liner.
- **Commit:** `test(paths): cover resolve_mill_config_path`

### Card 3: New `_autonomous.py` module

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_autonomous.py`
- **Deletes:** none
- **Requirements:** Create a new module `plugins/mill/scripts/_autonomous.py` with three public functions: `is_autonomous(hub_dir: Path) -> bool`, `set_autonomous(hub_dir: Path) -> None`, `clear_autonomous(hub_dir: Path) -> None`. All three derive a path `flag_path = hub_dir / ".millhouse" / "autonomous.flag"`. `is_autonomous` returns `flag_path.exists()`. `set_autonomous` ensures the parent directory exists via `flag_path.parent.mkdir(parents=True, exist_ok=True)` then calls `flag_path.touch(exist_ok=True)` to produce a zero-byte file (idempotent). `clear_autonomous` calls `flag_path.unlink(missing_ok=True)` (idempotent). All paths are derived from the `hub_dir` argument -- no global state, no env-var reads. The module docstring explains that the flag file represents ephemeral autonomous-mode state, replacing the removed `pipeline.autonomous_mode` config key. Declare `__all__ = ["is_autonomous", "set_autonomous", "clear_autonomous"]`. Match the file-style header of `_status.py` (`from __future__ import annotations` + `from pathlib import Path` imports only, no third-party deps).
- **Scope note:** this card creates `_autonomous.py` as foundational scaffolding only. Wiring the two stuck-escalation check sites in `plugins/mill/skills/mill-go/SKILL.md` to call `_autonomous.is_autonomous(hub_dir)` instead of reading `cfg.get("pipeline", {}).get("autonomous_mode")` is explicitly out of scope for this task. The `pipeline.autonomous_mode` config key becomes an unknown-key warning (caught by the new `warn_unknown_keys` validator in batch 2) but is not actively removed; mill-go continues to read it from the merged config dict until a follow-up task wires in the flag-file API.
- **Commit:** `feat(autonomous): add flag-file API`

### Card 4: Cover `_autonomous` in `test-autonomous.py`

- **Context:**
  - `plugins/mill/scripts/_autonomous.py`
  - `plugins/mill/unit_tests/test-paths.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-autonomous.py`
- **Deletes:** none
- **Requirements:** Create a new unit-test file mirroring the style of `test-paths.py` (same runner: stdlib unittest or pytest, whichever the neighbouring test files use). Cover: (a) `test_is_autonomous_false_when_flag_absent` -- pass a fresh `tmp_path` as hub_dir; assert `is_autonomous` returns False. (b) `test_set_autonomous_creates_zero_byte_flag` -- call `set_autonomous(tmp_path)`; assert `(tmp_path / ".millhouse" / "autonomous.flag").exists()` AND `.stat().st_size == 0`. (c) `test_is_autonomous_true_after_set` -- call `set_autonomous` then `is_autonomous`; assert True. (d) `test_clear_autonomous_deletes_flag` -- set then clear; assert flag gone AND `is_autonomous` returns False. (e) `test_clear_autonomous_idempotent_when_absent` -- call `clear_autonomous` on a fresh tmp_path (no flag); assert no exception raised. (f) `test_set_autonomous_idempotent_when_present` -- call set twice; assert no exception AND flag still exists. All paths derived from `tmp_path`; never write outside the temp dir.
- **Commit:** `test(autonomous): cover flag-file API`

### Card 5: New plugin template `mill-config.yaml`

- **Context:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Edits:** none
- **Creates:**
  - `plugins/mill/templates/mill-config.yaml`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/templates/mill-config.yaml` whose body content (the YAML keys themselves) is identical to the current `plugins/mill/templates/wiki-config.yaml` body. Replace the existing header comment block (the lines starting with `#` at the top of `wiki-config.yaml`) with a new header comment block documenting: (1) "This file is the plugin template for `mill-config.yaml` at the hub repo root." (2) Overlay precedence -- ASCII arrows only: `plugin template -> mill-config.yaml at hub repo root -> .millhouse/config.local.yaml`. (3) The env-var override registry -- list each of the six env vars and the dotted key path it overrides (`MILL_DISCUSSION_REVIEWER -> roles.discussion-review.holistic.reviewer`, `MILL_PLAN_REVIEWER -> roles.plan-review.holistic.reviewer`, `MILL_PLAN_BATCH_REVIEWER -> roles.plan-review.batch.reviewer`, `MILL_CODE_REVIEWER -> roles.code-review.holistic.reviewer`, `MILL_CODE_BATCH_REVIEWER -> roles.code-review.batch.reviewer`, `MILL_IMPLEMENTER -> roles.implementer.model`). (4) "Unknown keys emit a stderr warning at load time; load proceeds." Use only ASCII characters in the header (em-dash -> ` -- `, arrow -> ` -> `). Keep the existing per-section comment blocks already inside `wiki-config.yaml` unchanged.
- **Commit:** `feat(templates): add mill-config.yaml plugin template`

### Card 6: New plugin template `mill-agents.yaml`

- **Context:**
  - `C:/Code/millhouse/wiki/agents.yaml`
- **Edits:** none
- **Creates:**
  - `plugins/mill/templates/mill-agents.yaml`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/templates/mill-agents.yaml`. The body content (every agent entry) is a verbatim copy of the production `C:/Code/millhouse/wiki/agents.yaml` -- all 14 entries (g25flash, g25flash_tool, g25pro, g25pro_tool, g3flash_preview, g3flash_preview_tool, haiku, opushigh, opusmax, opusmedium, sonnethigh, sonnetmax, sonnetmax_tool, sonnetmedium) -- with no edits to keys or values. Add a header comment block above the first entry documenting: (1) "This file is the plugin template for the mill agent catalogue." (2) Overlay precedence -- ASCII: `plugin template -> .millhouse/agents.local.yaml`. (3) "Per-machine model swaps belong in `.millhouse/agents.local.yaml`, not here -- this file ships with the plugin." (4) A one-line schema reminder: each entry is keyed by reviewer name and has `type: single|cluster` plus type-specific fields (`provider`, `model` for single; `workers`, `handler` for cluster). ASCII only. Do NOT add `__all__`-style declarations or top-level YAML keys other than the agent entries themselves -- the file is a YAML mapping of name -> spec, no wrapping.
- **Commit:** `feat(templates): add mill-agents.yaml plugin template`

### Card 7: Update CLAUDE.md wiki-contents claims

- **Context:** none
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Edit two specific bullets in the hub-root `CLAUDE.md` (NOT the user-global one in `~/.claude/CLAUDE.md`). (a) In the `## Constraints` section, locate the bullet starting with "**Working state is never written to the wiki.**" Find the sub-sentence "The wiki holds only `Home.md` and `config.yaml`." and replace it with "The wiki holds only `Home.md`." Leave the rest of the bullet unchanged. (b) In the `## Path invariants` section, locate the bullet starting with "**Working state lives in `_mill/` on the task branch.**" Find the sub-sentence "The wiki holds only the task index (`Home.md`) and shared config (`config.yaml`)." and replace it with "The wiki holds only the task index (`Home.md`)." Leave the rest unchanged. No other CLAUDE.md edits in this card -- specifically, do NOT touch the wiki-config.yaml-template-mirror bullet (that survives until batch 4 deletes the template).
- **Commit:** `docs(claude.md): drop config.yaml from wiki-contents description`

## Batch Tests

The `verify:` command runs the two new unit-test files (`test-paths.py` covers card 2; `test-autonomous.py` covers card 4). Cards 1, 3, 5, 6, 7 are static additions/edits (a one-line helper, a new module, two new templates, two CLAUDE.md sentence edits) whose correctness is established by the tests in cards 2 and 4 (helpers) plus visual review (templates and docs).
