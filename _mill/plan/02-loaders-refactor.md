# Batch: loaders-refactor

```yaml
task: 57 (A) -- Move config.yaml and agents.yaml from wiki to hub worktree
batch: loaders-refactor
number: 2
cards: 11
verify: python plugins/mill/unit_tests/test-config.py && python plugins/mill/unit_tests/test-review-common.py && python plugins/mill/unit_tests/test-reviewers.py
depends-on: [1]
```

## Batch Scope

This batch rewrites the three production loaders -- `_config.load_config`, `_review_common.load_config`, `_reviewers.load` -- to consume the new plugin templates added in batch 1, drop the machine layer, gain three-layer (or two-layer for agents) overlay, gain env-var overrides for reviewer/implementer selection, gain warn-only unknown-key validation, gain a load-time fallback to `wiki/config.yaml` / `wiki/agents.yaml` for in-flight task branches that pre-date the migration, then migrates every callsite (twenty-plus combined) to the new signatures. The `_machine` module is still imported by tests and templates that get deleted in batch 4 -- this batch only removes the two `_machine.load_layer()` calls inside the two `load_config` implementations, leaving `_machine.py` itself in place.

External interface for downstream batches: the new signatures `_config.load_config(repo_root, worktree_root) -> dict`, `_review_common.load_config(repo_root, mill_dir) -> dict`, `_reviewers.load(hub_dir) -> dict[str, dict]`. Batch 3 (mill-setup migration) does NOT call these; it operates at the filesystem layer. Batch 4 (cleanup) deletes `_machine.py` after this batch has removed both of its callsites.

Batch-local decisions:

- The `apply_env_overrides`, `walk_unknown_keys`, `warn_unknown_keys`, and the `ENV_REGISTRY` constant live as module-level definitions in `_config.py`. `_review_common.py` imports them via `from _config import ENV_REGISTRY, apply_env_overrides, walk_unknown_keys, warn_unknown_keys`. `_reviewers.py` uses an analogous local walker against the agent-registry shape (each top-level key is an agent name, so unknown-key validation walks the per-entry sub-shape instead of treating agent names as schema keys); it does NOT call `walk_unknown_keys` from `_config.py` because the shape is fundamentally different (map of names, not nested config tree). The implementer adds a per-agent walker named `_walk_unknown_agent_keys(actual_entry, template_entry) -> list[str]` inside `_reviewers.py`.
- For the legacy `wiki/config.yaml` fallback inside the two `load_config` implementations: each function resolves `wiki_path` itself via `_paths.resolve_wiki_path(repo_root)` when needed (the caller no longer threads `wiki_path` in). If resolution fails for any reason (no wiki configured), the fallback simply does not fire. The integration with `_paths.resolve_wiki_path` adds one new caller -- existing helper, no change there.
- The `apply_env_overrides` helper handles "missing intermediate dicts" by NOT auto-creating them. If an env var is set to override `roles.implementer.model` but the merged config has no `roles` block at all, the override creates `cfg["roles"] = {"implementer": {"model": value}}`. Use `cfg.setdefault(...)` chained across the key tuple. Empty-string env value is treated as unset; do not write an empty string into the config.
- `_reviewers.load` MUST preserve every existing validation (`_NAME_REGEX`, type enum, cluster cross-refs, cycle detection). The two-layer overlay runs BEFORE validation -- merge plugin + local first, then validate the merged registry. This is the only safe order: validation looks at cluster `use:` references which may span layers.
- Callsites that previously computed both `wiki_path` and `git_root` (most of them do) need only minimal refactoring -- replace `wiki_path` with the appropriate repo-root variable (typically `git_root` for the lenient `_config.load_config` callers; `git_root` or `repo_root` for the strict `_review_common.load_config` callers; `hub_dir` -- which equals `git_root` in the standard worktree layout, or `resolve_active_hub(...)` in the cross-worktree scripts -- for `_reviewers.load`). The implementer must not invent new path-resolution code; reuse existing variables in scope.
- Test coverage targets: `test-config.py` and `test-review-common.py` cover the new overlay + env + validation + fallback paths; `test-reviewers.py` covers the new two-layer overlay + legacy-wiki fallback. Each test uses `tmp_path` and `monkeypatch` (pytest fixtures); no real wiki, no real LLM. If existing files use stdlib `unittest` instead of pytest, match that style -- consult the file header before writing tests.

## Cards

### Card 8: Add `ENV_REGISTRY` and `apply_env_overrides` to `_config.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a module-level constant `ENV_REGISTRY: dict[str, tuple[str, ...]]` with these six entries in this exact order:

  ```python
  ENV_REGISTRY = {
      "MILL_DISCUSSION_REVIEWER": ("roles", "discussion-review", "holistic", "reviewer"),
      "MILL_PLAN_REVIEWER":       ("roles", "plan-review",       "holistic", "reviewer"),
      "MILL_PLAN_BATCH_REVIEWER": ("roles", "plan-review",       "batch",    "reviewer"),
      "MILL_CODE_REVIEWER":       ("roles", "code-review",       "holistic", "reviewer"),
      "MILL_CODE_BATCH_REVIEWER": ("roles", "code-review",       "batch",    "reviewer"),
      "MILL_IMPLEMENTER":         ("roles", "implementer",       "model"),
  }
  ```

  Add a pure function `apply_env_overrides(cfg: dict) -> dict` that: (a) makes a deep copy of `cfg` (use `copy.deepcopy`); (b) iterates `ENV_REGISTRY.items()`; (c) for each entry reads `os.environ.get(env_var, "")` and skips if the value is empty; (d) walks the key tuple in the copy using `dict.setdefault(seg, {})` for each non-final segment and sets the final segment to the env value via subscript assignment; (e) returns the modified copy. Add `import os` and `import copy` at the top of the file (next to the existing `import yaml`). Add both `"ENV_REGISTRY"` and `"apply_env_overrides"` to a new module-level `__all__` if one is not already present; otherwise extend the existing `__all__`. Do NOT call `apply_env_overrides` from `load_config` yet -- card 10 wires it in.
- **Commit:** `feat(config): add env-var override registry`

### Card 9: Add unknown-key validation walker to `_config.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a pure function `walk_unknown_keys(actual: dict, template: dict, prefix: str = "") -> list[str]` that returns a list of dotted key paths present in `actual` but not in `template`. Recurse into nested dicts only when both `actual[key]` and `template[key]` are dicts (so a non-dict value at a key whose template counterpart IS a dict is reported as that path itself -- NOT descended). Lists are leaves; do not descend. The dotted-path format uses `.` between segments and does NOT quote segments. Add a helper `warn_unknown_keys(actual: dict, template: dict, source_label: str) -> None` that calls `walk_unknown_keys(actual, template)` and, for each returned path, writes one line to `sys.stderr` in the form `[config] unknown key: <path> (in <source_label>)`. ASCII only. Add `import sys` at the top if not already imported. Add `"walk_unknown_keys"` and `"warn_unknown_keys"` to `__all__`. Do NOT wire `warn_unknown_keys` into `load_config` yet -- card 10 does that.
- **Commit:** `feat(config): add unknown-key validation walker`

### Card 10: Rewrite `_config.load_config` with overlay + env + fallback + validation

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Rewrite the `load_config` function. New signature: `load_config(repo_root: Path, worktree_root: Path) -> dict`. Delete the line `import _machine` near the top of the file. Remove the line `cfg = deep_merge(cfg, _machine.load_layer())` from the body. Add a helper `resolve_plugin_template_path(filename: str) -> Path` at module scope (no leading underscore -- it is exported for use by `_review_common.py` and `_reviewers.py`) that returns `Path(os.environ["CLAUDE_PLUGIN_ROOT"]).resolve() / "templates" / filename` when the env var is set and non-empty, else `Path(__file__).resolve().parent.parent / "templates" / filename`. Add `"resolve_plugin_template_path"` to `__all__`. Replace the body of `load_config` with: (1) Load plugin template via `resolve_plugin_template_path("mill-config.yaml")`; if the file exists, `cfg = yaml.safe_load(...) or {}`, else `cfg = {}`. Keep a separate variable `template_cfg = cfg.copy()` (deep copy) for later validation. (2) Resolve `mill_cfg_path = _paths.resolve_mill_config_path(repo_root)`. Resolve the wiki via `try: wiki_cfg_path = _paths.resolve_wiki_path(repo_root) / "config.yaml"` wrapped in `except (Exception, SystemExit): wiki_cfg_path = None` (matches card 11's wording -- `_paths.resolve_wiki_path` raises `SystemExit` on missing wiki and a bare `except Exception` would NOT catch that). (3) Determine the "repo-layer" source per discussion's both-files-present and fallback rules: if `mill_cfg_path.exists()` -- use it; if `wiki_cfg_path` also exists, additionally print to stderr `[config] stale wiki/config.yaml detected at <wiki_cfg_path>; mill-config.yaml wins -- remove the wiki file via mill-setup` (ASCII). Else if `mill_cfg_path` does NOT exist but `wiki_cfg_path` exists -- use the wiki file and print `[config] using legacy wiki/config.yaml at <wiki_cfg_path>; rebase onto main to pick up mill-config.yaml` (ASCII). Else neither exists -- skip the repo layer (empty merge). Deep-merge the selected repo layer onto `cfg` if any. (4) Apply the existing stub-aware two-tier local-config logic from the OLD body: read the stub at `worktree_root / ".millhouse" / "config.local.yaml"`, deep-merge it, follow `hub_relative_path` to the real config if non-`.`, deep-merge that too. Preserve this logic verbatim from the existing code. (5) After merge, call `warn_unknown_keys(cfg, template_cfg, "<source-label>")` where `<source-label>` is the most-recently-applied non-template source's basename (best-effort; for the typical case `mill-config.yaml` or `config.local.yaml` is acceptable -- a single combined label `"merged config"` is fine if per-source tracking is too fiddly; the SHARED decisions block makes per-source tracking optional). (6) Apply env overrides: `cfg = apply_env_overrides(cfg)`. (7) Return `cfg`. The function remains lenient (returns whatever it can; never raises on missing files). Update the module docstring at the top of the file to reflect the new signature and merge order (plugin -> repo -> local stub -> local real, then env). Keep `set_local_wiki_overrides` and `deep_merge` unchanged.
- **Commit:** `refactor(config): three-layer overlay + env overrides`

### Card 11: Rewrite `_review_common.load_config` with overlay + env + fallback + strict-missing

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Rewrite the `load_config` function inside `_review_common.py` (lines 1017-1052 in the current file). New signature: `load_config(repo_root: Path, mill_dir: Path) -> dict`. Delete the `import _machine` import (currently at line 52) and the line `cfg = _deep_merge(cfg, _machine.load_layer())` (currently at line 1036). Add `from _config import ENV_REGISTRY, apply_env_overrides, walk_unknown_keys, warn_unknown_keys, resolve_plugin_template_path` to the imports near the top of the file (use the public helper from card 10 -- do NOT duplicate it here). Replace the body with: (1) Load plugin template via `resolve_plugin_template_path("mill-config.yaml")`; keep `template_cfg` for later validation. (2) Resolve `mill_cfg_path = _paths.resolve_mill_config_path(repo_root)` and `wiki_cfg_path = _paths.resolve_wiki_path(repo_root) / "config.yaml"` wrapped in `try: ... except (Exception, SystemExit): wiki_cfg_path = None` (the helper raises `SystemExit` -- a bare `except Exception` would NOT catch it). (3) Apply the same both-files-present / fallback rules as card 10. (4) Preserve the strict-missing semantics: if neither the plugin template nor the repo layer (mill-config.yaml OR wiki/config.yaml) produced any keys -- i.e. the merged config is still an empty dict at this point -- raise `ReviewError(f"Missing config: searched plugin template at {plugin_path}, mill-config.yaml at {mill_cfg_path}, and wiki/config.yaml at {wiki_cfg_path}")`. The strict rule is "at least one source present"; an operator with ONLY the plugin template is allowed to run reviews. (5) Deep-merge the local layer from `mill_dir / "config.local.yaml"` if present, preserving the existing `review:` legacy-block warning (lines 1042-1049 in the current file -- keep verbatim). (6) After merge, call `warn_unknown_keys(cfg, template_cfg, "merged config")`. (7) Apply env overrides: `cfg = apply_env_overrides(cfg)`. (8) Return `cfg`. ASCII only in all warnings/errors. Keep `_deep_merge` unchanged (it stays a separate local helper for now).
- **Commit:** `refactor(review-common): three-layer overlay + env overrides`

### Card 12: Migrate every `_config.load_config` callsite to repo_root signature

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-inspect.py`
  - `plugins/mill/scripts/millpy-migrate-layout.py`
  - `plugins/mill/scripts/millpy-status.py`
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/millpy-color.py`
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/millpy-terminal.py`
  - `plugins/mill/scripts/millpy-vscode.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** First, re-grep `grep -rn 'load_config(' plugins/mill/scripts/` at the start of this card to get the authoritative call list. Treat the resulting list (minus function definitions inside `_config.py`) as the work-item. Expected call locations (verify and update each):

  - `millpy-inspect.py:47` -- change `_config.load_config(wiki, git_root)` to `_config.load_config(git_root, git_root)`. The unused `wiki` variable assignment two lines above (typically `wiki = _paths.resolve_wiki_path(git_root)`) MUST be kept ONLY if `wiki` is used elsewhere in the function; if not, remove the unused assignment.
  - `millpy-migrate-layout.py:199` -- change `_config.load_config(wiki_path, hub_root)` to `_config.load_config(hub_root, hub_root)`.
  - `millpy-status.py:26` -- change `_config.load_config(wiki, git_root)` to `_config.load_config(git_root, git_root)`.
  - `millpy-claim.py:57-68` and `millpy-claim.py:169` -- the file defines a local `_load_config(wiki_path, git_root)` wrapper. Update the wrapper's signature to `_load_config(repo_root, worktree_root)` and its internal call to `_config.load_config(repo_root, worktree_root)`. Update the callsite at line 169 to pass the appropriate variables (typically `git_root, resolve_hub_path()`; verify against surrounding code).
  - `millpy-cleanup.py:594` -- update the local `_load_config(wiki_path, git_root)` wrapper signature and the callsite to pass `(git_root, git_root)`.
  - `millpy-color.py:90` -- update the local `_load_config` wrapper and callsite to use `(git_root_or_repo_root, resolve_hub_path())` per surrounding code.
  - `millpy-spawn.py:58-75` and `millpy-spawn.py:111` -- update the local wrapper's signature and internal call; update line 111 callsite to pass `(git_root, resolve_hub_path())`.
  - `millpy-terminal.py:56` and `millpy-terminal.py:107` -- update the local wrapper + both callsites.
  - `millpy-vscode.py:79, 118, 177, 258` -- update the local wrapper + all four callsites.

  For every local `_load_config(wiki_path, ...)` wrapper updated above: rename the first parameter to `repo_root` and update every reference inside the wrapper body accordingly. If the wrapper previously discarded the `wiki_path` argument (e.g. only used `worktree_root`), drop the unused parameter at the wrapper level too. Any caller in the same file that imports `wiki_path = _paths.resolve_wiki_path(...)` ONLY to feed it into `_load_config` and not for anything else should remove that import too. Run `grep -n 'wiki' <each-file>` after edits to confirm no orphan `wiki_path` variables remain.

  **Strict-check disposition for wrappers that previously raised on missing wiki config.** Two scripts have a strict pre-check before delegating to the lenient loader: `millpy-claim.py` lines 57-67 (`_load_config` raises `SystemExit("Missing config at <wiki>/config.yaml")` when `wiki/config.yaml` is absent) and `millpy-spawn.py` lines 58-67 (same pattern). After the rename, the existence check must reflect the new schema: change the body to check both the new and legacy sources. Concretely, replace the existing `shared_path = wiki_path / "config.yaml"; if not shared_path.exists(): raise SystemExit(...)` block with:

  ```python
  mill_cfg = repo_root / "mill-config.yaml"
  wiki_cfg = None
  try:
      wiki_cfg = _paths.resolve_wiki_path(repo_root) / "config.yaml"
  except SystemExit:
      wiki_cfg = None
  if not mill_cfg.exists() and (wiki_cfg is None or not wiki_cfg.exists()):
      raise SystemExit(f"Missing config: searched {mill_cfg} and {wiki_cfg}")
  ```

  This preserves the strict semantics (mill-claim and mill-spawn still refuse to run on a hub with no config source at all) while accommodating both the migrated state (mill-config.yaml present) and the in-flight legacy state (wiki/config.yaml only). Update the wrapper's docstring to reflect the new search order.

  After this card the only `_config.load_config(...)` callsites in the repo MUST be the function definition itself (inside `_config.py`) and the updated callers listed above. Re-run `grep -rn 'load_config(' plugins/mill/scripts/` at the end to verify. Tests in `unit_tests/` may still reference the old signature -- card 14 updates `test-config.py`; do not touch test files in this card.
- **Commit:** `refactor: migrate _config.load_config callers to repo_root signature`

### Card 13: Migrate every `_review_common.load_config` callsite to repo_root signature

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-abandon.py`
  - `plugins/mill/scripts/millpy-implement-holistic.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-validate-plan.py`
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Re-grep `grep -rn 'load_config(' plugins/mill/scripts/` AND `grep -rn 'from _review_common import' plugins/mill/scripts/` at the start to get the authoritative call list. Expected callsites:

  - `millpy-abandon.py:42` -- `cfg = _review_common.load_config(wiki_path, mill_dir)` -> `cfg = _review_common.load_config(repo_root, mill_dir)`. The variable `repo_root` is typically derivable from existing in-scope variables (`git_root` or `_paths.resolve_git_root()`); add an assignment if needed.
  - `millpy-implement-holistic.py:67`, `millpy-implement.py:82`, `millpy-merge-in-subagent.py:79` -- same pattern, swap `wiki_path` for `repo_root`.
  - `millpy-review-code.py:69`, `millpy-review-discussion.py:43`, `millpy-review-plan.py:79`, `millpy-validate-plan.py:43` -- these import `load_config` directly: `cfg = load_config(wiki_root, mill_dir)`. Change to `cfg = load_config(repo_root, mill_dir)` where `repo_root` is computed via `_paths.resolve_git_root()` if not already in scope.
  - `_review_common.py:176` (inside `resolve_path` helper, which calls `load_config(wiki_root, hub_dir / '.millhouse')`) -- change to `load_config(git_root, hub_dir / '.millhouse')`, using the `git_root` variable already computed in the `resolve_path` body. The external signature of `resolve_path` is unchanged; no callers need updating for this line.

  For every script touched above: if `wiki_path` / `wiki_root` was computed only to feed into `load_config` and is not used elsewhere in the function, remove the unused assignment. Otherwise leave it -- some scripts genuinely need `wiki_path` for other helpers.

  Re-grep `load_config(` at the end of the card. The only remaining references MUST be the two function definitions (in `_config.py` and `_review_common.py`) plus the now-updated callers. Test files are NOT touched in this card.
- **Commit:** `refactor: migrate _review_common.load_config callers to repo_root signature`

### Card 14: Extend `test-config.py` for new overlay, env, validation, fallback

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/templates/mill-config.yaml`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** First read the existing `test-config.py` to determine the test framework (unittest vs pytest) and the fixture pattern (tmp_path vs hand-rolled TemporaryDirectory). Match that style.

  **Update existing tests for the new signature.** The current file (as of this plan) has seven `load_config` tests that pass `wiki` as the first positional argument: `test_load_config_shared_present`, `test_load_config_local_override_wins`, `test_load_config_wiki_config_absent`, `test_load_config_subfolder_install`, `test_load_config_stub_only_real_absent` (lines ~54-160), plus two machine-layer tests `test_load_config_machine_layer_present_merged` and `test_load_config_machine_absent_graceful` (lines ~164-200). For the FIVE non-machine tests, rewrite each call from `_config.load_config(wiki, wt_root)` to `_config.load_config(wt_root, wt_root)` (the new signature uses `repo_root` as the first arg; in the existing fixtures `wt_root` is the repo root, and `wiki` is a sibling dir created for the legacy fallback). For tests that intend to exercise the wiki fallback specifically (`test_load_config_shared_present`, `test_load_config_local_override_wins`, `test_load_config_wiki_config_absent`), the existing fixtures need to be adapted: arrange the test so the wiki dir sits as a sibling of the repo root (so `_paths.resolve_wiki_path(repo_root)` succeeds), OR monkeypatch `_paths.resolve_wiki_path` to return the fixture wiki dir. Each rewritten test must still pass under the new code path.

  **Delete the four machine-layer tests.** `test_load_config_machine_layer_present_merged`, `test_load_config_machine_absent_graceful`, `test_load_config_machine_overrides_wiki`, and `test_load_config_worktree_overrides_machine` all exercise behavior that has been removed (`_machine.load_layer` is no longer called by `load_config`). Delete all four tests in full -- including the comment block at line ~161 that introduces them ("Tests below patch Path.home..."). Leaving any of the four in place causes assertion failures at runtime since `_config.load_config` no longer merges the machine layer. Update the module-level docstring at the top of `test-config.py` to drop any reference to machine-layer behaviour.

  **Add these new test cases** (one function per case; descriptive names):

  - `test_three_layer_merge_plugin_repo_local` -- create three temp YAML files (a fake plugin template via monkeypatching `resolve_plugin_template_path` OR via setting `CLAUDE_PLUGIN_ROOT` to a `tmp_path` containing a `templates/mill-config.yaml`), a `mill-config.yaml` at the repo root, and a `config.local.yaml` at `<worktree>/.millhouse/`. Verify that for a key present in all three, the local value wins; for a key in only plugin and repo, the repo value wins; for a key only in plugin, the plugin value survives. Verify deep merge for nested dicts.
  - `test_machine_layer_ignored` -- monkeypatch `Path.home()` to point at a tmp dir containing `~/.millhouse/config.machine.yaml` with a distinctive value. Confirm the loaded config does NOT contain that value.
  - One test per `ENV_REGISTRY` entry (six tests): `test_env_override_<MILL_DISCUSSION_REVIEWER>` etc. Each uses `monkeypatch.setenv` to set the env var to a sentinel string, calls `load_config`, asserts the corresponding dotted-path key in the returned config equals the sentinel. Verify no other config keys are mutated (snapshot before/after, compare).
  - `test_env_override_empty_string_is_noop` -- set `MILL_PLAN_REVIEWER=""`. Confirm the config's `roles.plan-review.holistic.reviewer` is whatever the merged YAML produced (NOT overwritten with `""`).
  - `test_list_replace_semantics` -- plugin template has `verify.skip_known_broken: [a.py, b.py]`; local file has `verify.skip_known_broken: [c.py]`. Verify the loaded list is `[c.py]` (wholesale replace).
  - `test_unknown_key_warning_emitted` -- local file contains an unknown key `pipeline.autonomous_mode: true`. Capture stderr via `capsys` (pytest) or `unittest.mock.patch('sys.stderr', io.StringIO())`. Confirm load succeeds AND stderr contains the path `pipeline.autonomous_mode`.
  - `test_fallback_to_wiki_config_yaml` -- repo has NO `mill-config.yaml`; monkeypatch `_paths.resolve_wiki_path` to return a `tmp_path / "wiki"` dir; seed `<wiki>/config.yaml` with a distinctive value. Confirm the loaded config contains that value AND stderr emitted a fallback warning naming the wiki path.
  - `test_both_files_present_mill_wins` -- repo has `mill-config.yaml` with key `K=mill`; monkeypatch `_paths.resolve_wiki_path` and seed `<wiki>/config.yaml` with `K=wiki`. Confirm loaded config has `K=mill` AND stderr emitted a "stale wiki/config.yaml" warning.

  Note on `resolve_wiki_path` monkeypatching: tests that exercise either the legacy-wiki fallback or the both-files-present branch MUST monkeypatch `_paths.resolve_wiki_path` to return a controlled fixture dir (e.g. `tmp_path / "wiki"`), because a bare `tmp_path` is not a git repo and the bare helper raises `SystemExit`. Same applies to the rewritten `test_load_config_shared_present` / `test_load_config_local_override_wins` / `test_load_config_wiki_config_absent` fixtures above when they need the wiki to be discoverable.

  All tests use `tmp_path` (or equivalent) -- no real wiki, no real home dir, no real venv. Tests must run from `plugins/mill/unit_tests/` via the existing `run-all.py` runner. Do NOT introduce new test infrastructure.
- **Commit:** `test(config): cover overlay, env, validation, fallback`

### Card 15: Extend `test-review-common.py` for new overlay, env, validation, strict-missing

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** First read existing `test-review-common.py` to confirm the test framework. If existing tests in the file call `load_config(wiki_root, mill_dir)` with the OLD signature, rewrite each to use `(repo_root, mill_dir)` mirroring the card-14 rewrites; if existing tests rely on the now-removed `_machine.load_layer` path, delete them. Add cases parallel to card 14 covering: three-layer merge (`test_load_config_three_layer_merge`), env overrides (one consolidated test or six parallel tests -- match what was done in `test-config.py`), unknown-key warning, fallback to `wiki/config.yaml`, both-files-present. For fallback / both-files-present cases monkeypatch `_paths.resolve_wiki_path` to return a fixture wiki dir (same rule as card 14). PLUS two cases specific to `_review_common.load_config`:

  - `test_load_config_raises_when_no_source_present` -- no plugin template, no `mill-config.yaml`, no `wiki/config.yaml`. Confirm `ReviewError` is raised with a message naming the searched paths.
  - `test_legacy_review_block_warning` -- a `config.local.yaml` containing a `review:` top-level key triggers the existing stale-block warning (preserved from the old code).

  All other guidance from card 14 (fixtures, capsys, no real I/O) applies here too.
- **Commit:** `test(review-common): cover overlay, env, validation, strict-missing`

### Card 16: Rewrite `_reviewers.load(hub_dir)` with two-layer overlay

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/templates/mill-agents.yaml`
- **Edits:**
  - `plugins/mill/scripts/_reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Rewrite `_reviewers.load`. New signature: `load(hub_dir: Path) -> dict[str, dict]`. Body steps: (1) Resolve the plugin template via `resolve_plugin_template_path("mill-agents.yaml")` (import from `_config`). If the template exists, read it as `template_registry = yaml.safe_load(...) or {}`; else `template_registry = {}`. (2) Resolve local overlay at `local_path = hub_dir / ".millhouse" / "agents.local.yaml"`. If it exists, read as `local_registry = yaml.safe_load(...) or {}`. Else `local_registry = {}`. (3) Legacy-wiki fallback: if BOTH `template_registry` and `local_registry` are empty, attempt `_paths.resolve_wiki_path(hub_dir) / "agents.yaml"`, then `.../reviewers.yaml`. If either exists, load it AND print to stderr `[reviewers] using legacy wiki agents file at <path>; run mill-setup to migrate to plugin template + .millhouse/agents.local.yaml` (ASCII). If wiki resolution fails or neither file exists, raise `ReviewerError("Missing registry: no plugin template at <path>, no .millhouse/agents.local.yaml at <path>, no legacy wiki/agents.yaml or wiki/reviewers.yaml")`. (4) Deep-merge `local_registry` onto `template_registry` using `_config.deep_merge` (deep merge so per-agent `model:` overrides work without replacing the whole entry). Store the result as `raw`. (5) Per-agent unknown-key validation: for each agent in `raw`, if the agent name also exists in `template_registry`, call a new helper `_walk_unknown_agent_keys(raw[name], template_registry[name]) -> list[str]` (same shape as `_config.walk_unknown_keys` but ALWAYS treating each direct sub-dict as a flat key map -- no recursion needed since agent specs are one level deep). Emit one stderr line per unknown key in the form `[reviewers] unknown key in <agent_name>: <key> (in .millhouse/agents.local.yaml)`. Local-only agents (in `raw` but not in `template_registry`) are NOT flagged -- adding a new agent locally is allowed. (6) Run the existing validation block (lines 53-145 in the current file) on `raw`: duplicate detection via `yaml.compose` is no longer applicable to the merged dict; replace it with a direct check `len(raw) != len(set(raw.keys()))` is impossible since dicts dedupe -- the per-layer duplicate check should run on the input YAML files BEFORE merging. Move the existing `yaml.compose`-based duplicate-key check to run on the plugin template file AND on the local file SEPARATELY (before merge). Preserve every other validation (name regex, type enum, cluster cross-refs, cycle detection) on the merged registry. (7) Return `raw`. ASCII only in all warnings/errors. Update the module docstring at the top of `_reviewers.py` to reflect the new signature and overlay model.
- **Commit:** `refactor(reviewers): two-layer overlay with plugin template`

### Card 17: Migrate every `_reviewers.load` callsite to `hub_dir` signature

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement-holistic.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Re-grep `grep -rn '_reviewers.load(' plugins/mill/scripts/` AND `grep -rn 'reviewers.load(' plugins/mill/scripts/` (for any aliased imports) at the start to confirm the call list. Expected callsites:

  - `millpy-implement-holistic.py:87`, `millpy-implement.py:103`, `millpy-merge-in-subagent.py:94` -- `_reviewers.load(wiki_path)` -> `_reviewers.load(hub_dir)`. `hub_dir` is typically `git_root` (worktree root). If the script computes a separate hub path via `resolve_active_hub` or `resolve_hub_path`, use that; otherwise use `git_root`. Inspect each script's existing variable scope and pick the appropriate one.
  - `millpy-review-code.py:72`, `millpy-review-discussion.py:46`, `millpy-review-plan.py:82` -- `_reviewers.load(wiki_root)` -> `_reviewers.load(hub_dir)`. Same hub_dir resolution rule.
  - `_review_code.py:281`, `_review_discussion.py:76`, `_review_plan.py:319` -- DO NOT rename the `wiki_root` parameter on the surrounding `run()` signatures. `wiki_root` is also passed to `resolve_ref_paths`, `resolve_existing_paths`, and `load_task_title` in each backend (see `_review_code.py:245, 267, 297, 338`; `_review_discussion.py:98`; `_review_plan.py:135, 142, 203, 339, 417, 450, 457, 521`), where it must remain the wiki clone path for `wiki/`-prefixed ref resolution to work. Instead, inside each of the three backend `run()` bodies, add a single local assignment `hub_dir = project_root` (the existing `project_root` parameter IS the worktree root in the current call shape) and change ONLY the `_reviewers.load(wiki_root)` call to `_reviewers.load(hub_dir)`. Leave every other `wiki_root` reference unchanged. No upstream `run()` callers need updating for this card.

  For the millpy-* scripts touched above (where the call is in the script's own body, not a shared backend): if `wiki_path` / `wiki_root` was computed only to feed into `_reviewers.load` and isn't used elsewhere in the function, remove the unused assignment. Re-grep `_reviewers.load(` AND `reviewers.load(` at the end -- the only references MUST be the function definition (in `_reviewers.py`) and the updated callers.
- **Commit:** `refactor: migrate _reviewers.load callers to hub_dir signature`

### Card 18: Extend `test-reviewers.py` for two-layer overlay

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/templates/mill-agents.yaml`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Read existing `test-reviewers.py` to determine framework and fixture style. Add these cases:

  - `test_load_plugin_template_only` -- fixture `hub_dir` with no `.millhouse/agents.local.yaml`; plugin template (via monkeypatched `resolve_plugin_template_path` or `CLAUDE_PLUGIN_ROOT`) has 2 entries. Confirm `load(hub_dir)` returns those 2 entries.
  - `test_local_overlay_adds_new_agent` -- plugin template has entry `A`; local file has entry `B`. Confirm both present in the returned dict.
  - `test_local_overlay_overrides_model` -- plugin template has `A: {type: single, provider: anthropic, model: x}`; local has `A: {model: y}`. Confirm merged entry is `{type: single, provider: anthropic, model: y}` (deep merge; `type` and `provider` preserved from plugin layer; `model` overridden).
  - `test_unknown_key_warning_on_local_file` -- local file's entry `A` has an extra key `typo_key: foo` not in the plugin template's `A`. Capture stderr; confirm a warning naming the agent and the key is emitted.
  - `test_legacy_wiki_fallback_when_no_plugin_template` -- monkeypatch `resolve_plugin_template_path` to return a non-existent path; no `.millhouse/agents.local.yaml`; monkeypatch `_paths.resolve_wiki_path` to return a fixture wiki dir under `tmp_path / "wiki"` (so the legacy-fallback path resolves without needing a real git repo). Create the wiki dir and seed `<wiki>/agents.yaml` with 2 entries. Confirm `load(hub_dir)` returns those entries AND stderr emitted a legacy-fallback warning. Note: the `_paths.resolve_wiki_path` monkeypatch is required because the new `_reviewers.load(hub_dir)` body calls `resolve_wiki_path(hub_dir)` for the legacy branch, and a bare `tmp_path` is not a git repo -- without the monkeypatch the helper raises `SystemExit`.
  - `test_raises_when_nothing_found` -- no plugin template, no local, no wiki. Confirm `ReviewerError` raised with a message naming the searched paths.

  **Migration of existing tests.** Every existing test that calls `_reviewers.load(wiki)` must be updated -- the old signature accepted a wiki root whose `agents.yaml` was the sole source; the new signature accepts a hub dir and resolves sources via the overlay model. The existing file has twelve such tests (listed below by function name) plus one that currently writes directly to `wiki / "agents.yaml"` for a legacy-fallback case. Read the existing file first. The key insight: if `hub_dir / ".millhouse" / "agents.local.yaml"` is non-empty, the legacy-wiki fallback never triggers, so no monkeypatching of `_paths.resolve_wiki_path` is needed for those tests. The restructuring strategy per test group:

  **Group A -- happy-path and validation tests (11 tests):** `test_load_happy_path`, `test_load_raises_single_missing_provider`, `test_load_raises_cluster_missing_workers`, `test_load_raises_cluster_missing_handler`, `test_load_raises_cluster_workers_count_non_positive`, `test_load_raises_unknown_type`, `test_load_raises_invalid_name_uppercase`, `test_load_raises_invalid_name_dot`, `test_load_raises_duplicate_name`, `test_load_raises_cluster_use_nonexistent`, `test_load_raises_cluster_use_referencing_cluster`. For each: rename `wiki = Path(tmp) / "wiki"` to `hub_dir = Path(tmp) / "hub"`. Replace the call `write_to(wiki)` or `_write_yaml(wiki / "agents.yaml", ...)` with `_write_yaml(hub_dir / ".millhouse" / "agents.local.yaml", <same-yaml-content>)`. Change `_reviewers.load(wiki)` to `_reviewers.load(hub_dir)`. No monkeypatching needed -- the local file is non-empty, so the legacy-wiki fallback branch is never reached. The existing `write_to` helper from `_test_registry` writes `wiki / "agents.yaml"`; do not call it in these tests after the restructure. Instead call `_write_yaml` directly with the same YAML content that `write_to` uses.

  **Group B -- missing-file test (1 test):** `test_load_raises_on_missing_file`. The test creates `hub_dir = Path(tmp) / "hub"; hub_dir.mkdir()` with no agents file and expects `ReviewerError("Missing registry...")`. Under the new logic, when both template and local are empty, the function attempts `_paths.resolve_wiki_path(hub_dir)` for the legacy fallback -- which raises `SystemExit` for a bare tmp dir (not a git repo). The `SystemExit` must be caught by the legacy-fallback branch per Card 16's spec, and the function should then raise `ReviewerError`. To make the test hermetic, monkeypatch `_paths.resolve_wiki_path` to raise `SystemExit` explicitly: `with patch("_paths.resolve_wiki_path", side_effect=SystemExit): _reviewers.load(hub_dir)`. Assert `ReviewerError` with `"Missing registry"` in the message.

  **Group C -- legacy fallback test (1 test):** `test_load_falls_back_to_reviewers_yaml`. The existing test renames `wiki/agents.yaml` to `wiki/reviewers.yaml` and calls `_reviewers.load(wiki)`. Under the new signature this breaks in two ways: (1) `_reviewers.load(hub_dir)` no longer reads `hub_dir/reviewers.yaml` directly; (2) the legacy-wiki fallback calls `_paths.resolve_wiki_path(hub_dir)` which raises `SystemExit` on a bare tmp dir. Restructure: use `hub_dir = Path(tmp) / "hub"; hub_dir.mkdir()`; monkeypatch `_paths.resolve_wiki_path` to return `Path(tmp) / "wiki"`; write the minimal registry YAML to `Path(tmp) / "wiki" / "reviewers.yaml"`. Also monkeypatch `resolve_plugin_template_path` (imported from `_config` inside `_reviewers`) to return a non-existent path so that `template_registry = {}` and the legacy fallback triggers. Call `_reviewers.load(hub_dir)` and assert `"sonnetmax" in registry`. Alternatively, restructure the fixture entirely: rename the test to `test_load_local_overlay_used_when_present`, put the registry in `hub_dir / ".millhouse" / "agents.local.yaml"`, drop the `reviewers.yaml` rename, and verify the same round-trip behaviour. Either approach is acceptable; pick whichever is simpler given the surrounding test style.
- **Commit:** `test(reviewers): cover two-layer overlay`

## Batch Tests

The `verify:` runs the three extended unit-test files. Each test file exercises one of the three rewritten loaders in isolation plus the callsite migrations (the new signatures are imported by every callsite in batch). Integration coverage for the actual production callsites comes from the existing `run-all.py` aggregator after this batch finishes; the integration test for migration (`test-migration.py`) lives in batch 3 and tests filesystem mechanics, not loader semantics.
