# Discussion: 65 (A) — Config-load og mill-go helse-sjekk etter config-migrasjon

```yaml
task: 65 (A) — Config-load og mill-go helse-sjekk etter config-migrasjon
slug: mill-config-load-fixes
status: discussing
parent: main
```

## Problem

After the config-move-to-hub migration, every mill script emits a spurious
`[config] unknown key: hub_relative_path` warning on startup. This key is
written by mill-setup to `.millhouse/config.local.yaml` and is consumed by
`load_config` in both `_config.py` and `_review_common.py`, but is not in
the template schema — so `warn_unknown_keys` incorrectly flags it. Similarly,
`pipeline.autonomous_mode` is consumed by mill-go, mill-plan, and mill-autofix
but is missing from the `mill-config.yaml` template, causing the same warning.

A separate crash occurs in `_review_common.load_config` (and `_config.load_config`)
when `mill-config.yaml` contains a bare `roles:` key (valid YAML, parsed as
`None`). `_deep_merge` in both modules passes `None` through as the overlay value,
clobbering the template's nested `roles:` dict. Downstream code then crashes with
`AttributeError: 'NoneType' object has no attribute 'items'` inside
`validate_role_refs` and similar callers.

`resolve_plugin_template_path` silently returns a non-existent path when
`CLAUDE_PLUGIN_ROOT` is stale or invalid. Callers check `path.exists()` and fall
back to `cfg = {}` when it is False, but then downstream code accesses nested keys
like `cfg["roles"]["discussion-review"]["holistic"]["reviewer"]` and gets `KeyError`
far from the actual cause. A fallback-with-warning is needed.

Finally, the mill-go SKILL.md Step 3 still documents the old
`_review_common.load_config(wiki_path, Path(".millhouse"))` call. After the
migration `mill-config.yaml` lives at the hub root, not the wiki, so passing
`wiki_path` as `repo_root` means hub-specific config overrides are silently ignored.

## Scope

**In:**
- `plugins/mill/scripts/_config.py` — fix `warn_unknown_keys` to not flag `hub_relative_path` (strip before validation); fix `deep_merge` to not clobber dict with `None`; fix `resolve_plugin_template_path` to fall back to source-tree when CLAUDE_PLUGIN_ROOT path doesn't exist.
- `plugins/mill/templates/mill-config.yaml` — add `pipeline.autonomous_mode: false` to the pipeline section.
- `plugins/mill/scripts/_review_common.py` — fix `_deep_merge` to not clobber dict with `None` (same bug, separate copy); `load_config` does not need `hub_relative_path` stripping since it doesn't consume it.
- `plugins/mill/skills/mill-go/SKILL.md` — update Step 3 to use `_paths.resolve_git_root()` as the first arg to `load_config`, and fix the inline description to reference `mill-config.yaml` instead of `wiki/config.yaml`.
- `plugins/mill/unit_tests/test-config.py` — add tests for: `deep_merge(None overlay on dict base)`, `resolve_plugin_template_path` stale-CLAUDE_PLUGIN_ROOT fallback, `load_config` bare-`roles:` no-crash.
- `plugins/mill/unit_tests/test-review-common.py` — add tests for `_deep_merge(None overlay on dict base)` and `load_config` bare-`roles:` no-crash.

**Out:**
- The strict-missing semantics of `_review_common.load_config` (pre-existing test failure from `test-review-common.py` "missing config -> ReviewError" — that is in task 64 / issue #332 scope).
- `test-llm-claude.py`, `test-review-code-flow.py`, `test-review-discussion-flow.py` — pre-existing failures, not in scope.
- mill-go Step 3's `_review_common.load_config` is only updated in the SKILL.md (the Python scripts `millpy-review-*.py` already call `load_config(hub_dir, mill_dir)` correctly — only the SKILL.md is wrong).
- No changes to `_paths.py` or other helpers.
- No changes to the wiki or worktree junction setup.

## Decisions

### hub_relative_path: strip pre-validation, don't add to template

- Decision: In `_config.load_config`, strip `hub_relative_path` from `cfg` before calling `warn_unknown_keys`. Do not add it to the template schema.
- Rationale: `hub_relative_path` is gitignored, per-machine, consumed by the loader itself (not passed through as a config value to callers). Adding it to the shared template would mislead operators. Stripping it pre-validation is the minimal change. In `_review_common.load_config`, `hub_relative_path` is not merged into cfg (the local layer is merged via `_deep_merge(cfg, local_cfg)` without stripping) — we need to strip it there too, or filter it from the `warn_unknown_keys` call.
- Rejected: Adding `hub_relative_path: "."` to the template — misleads operators into thinking it's a shareable config value when it's gitignored local state.

### pipeline.autonomous_mode: add to template

- Decision: Add `autonomous_mode: false` to the `pipeline:` section of `plugins/mill/templates/mill-config.yaml`.
- Rationale: It is consumed by mill-go and mill-plan SKILL.md files and is a real config key that users set in `config.local.yaml`. The template omits it, causing the unknown-key warning.
- Rejected: Stripping `pipeline.autonomous_mode` pre-validation alongside `hub_relative_path` — unlike `hub_relative_path`, `autonomous_mode` is a valid shared config key that belongs in the template schema.

### deep_merge None-overlay: no-op for dict base only

- Decision: In both `_config.deep_merge` and `_review_common._deep_merge`, add a guard: if the overlay value is `None` and the base value is a dict, skip the override (keep the base dict). If the base value is a scalar, allow `None` to override (this is the `reviewer: null` use case).
- Rationale: YAML bare keys (`roles:`) parse as `None`. The intent is "inherit from defaults", not "set to None". But `reviewer: null` (reviewer disabled) is a legitimate use case and must continue to work.
- Rejected: Treating `None` overlay as no-op unconditionally — would break `reviewer: null` semantics.

### resolve_plugin_template_path: fallback with warning

- Decision: After resolving the CLAUDE_PLUGIN_ROOT-based path, check if it exists. If it doesn't, emit a stderr warning and return the source-tree path instead. The source-tree path is always returned as the final fallback regardless.
- Rationale: A stale CLAUDE_PLUGIN_ROOT causes template loading to silently fail, producing a misleading `KeyError` deep in the call chain. A warning at resolution time is actionable.
- Rejected: Raising an exception when CLAUDE_PLUGIN_ROOT path doesn't exist — too aggressive; the source-tree fallback should allow scripts to keep working.

### mill-go SKILL.md Step 3: use hub_root not wiki_path

- Decision: Update the SKILL.md Step 3 to call `_review_common.load_config(_paths.resolve_git_root(), Path(".millhouse"))` and update the prose description to reference `mill-config.yaml` at the hub root (not `wiki/config.yaml`).
- Rationale: `_review_common.load_config(repo_root, mill_dir)` uses `repo_root` to look for `mill-config.yaml`. Passing `wiki_path` means the script always falls back to wiki/config.yaml or template defaults, silently ignoring hub-specific overrides.
- Rejected: Using `Path(".")` (cwd) as the first arg — fragile if cwd changes; `_paths.resolve_git_root()` is the correct canonical resolution.

### hub_relative_path stripping: where to strip

- Decision: Strip `hub_relative_path` from the merged `cfg` dict before calling `warn_unknown_keys` in `_config.load_config`. In `_review_common.load_config`, strip it from `local_cfg` before merging (since it's only in the local layer), OR alternatively strip from `cfg` before the `warn_unknown_keys` call. The cleanest is to strip from the cfg copy passed to `warn_unknown_keys` in both functions.
- Rationale: We don't want to strip it from the returned cfg (callers may need it), but we do want to suppress the warning. Create a temporary copy for the unknown-key check that excludes `hub_relative_path`.
- Rejected: Keeping `hub_relative_path` in the returned cfg unchanged and only suppressing the warning — this is exactly what we want. No caller currently uses `cfg["hub_relative_path"]` post-load, but removing it from the returned value would be a silent behavior change.

## Technical context

### Files to change

- `plugins/mill/scripts/_config.py` — `deep_merge`, `resolve_plugin_template_path`, `load_config` (warn_unknown_keys call site)
- `plugins/mill/scripts/_review_common.py` — `_deep_merge`, `load_config` (warn_unknown_keys call site)
- `plugins/mill/templates/mill-config.yaml` — add `autonomous_mode: false` to `pipeline:` section
- `plugins/mill/skills/mill-go/SKILL.md` — Step 3 text and function call
- `plugins/mill/unit_tests/test-config.py` — new tests
- `plugins/mill/unit_tests/test-review-common.py` — new tests

### Key locations

- `_config.deep_merge` at [plugins/mill/scripts/_config.py:240](plugins/mill/scripts/_config.py#L240) — the `else: out[key] = val` branch is where `None` clobbers the dict.
- `_config.resolve_plugin_template_path` at [plugins/mill/scripts/_config.py:126](plugins/mill/scripts/_config.py#L126) — no existence check before returning.
- `_config.load_config` warn call at [plugins/mill/scripts/_config.py:212](plugins/mill/scripts/_config.py#L212) — passes full `cfg` (which includes `hub_relative_path`) to `warn_unknown_keys`.
- `_review_common._deep_merge` at [plugins/mill/scripts/_review_common.py:1168](plugins/mill/scripts/_review_common.py#L1168) — same `None`-clobber bug.
- `_review_common.load_config` warn call at [plugins/mill/scripts/_review_common.py:1261](plugins/mill/scripts/_review_common.py#L1261) — passes full `cfg` (includes `hub_relative_path` from local layer).
- `mill-config.yaml` pipeline section at [plugins/mill/templates/mill-config.yaml:108](plugins/mill/templates/mill-config.yaml#L108) — `auto_merge` and `auto_report` but no `autonomous_mode`.
- mill-go SKILL.md Step 3 at [plugins/mill/skills/mill-go/SKILL.md:54](plugins/mill/skills/mill-go/SKILL.md#L54) — wrong `wiki_path` arg.

### Codebase conventions

- Both `_config.deep_merge` and `_review_common._deep_merge` are private duplicates. The same fix must be applied to both (they are not shared). `_config.deep_merge` is the public API; `_review_common._deep_merge` is a private local copy.
- `warn_unknown_keys` takes `(actual, template, source_label)`. To suppress `hub_relative_path`, strip it from a copy before the call: `check_cfg = {k: v for k, v in cfg.items() if k != 'hub_relative_path'}; warn_unknown_keys(check_cfg, template_cfg, source_label)`. Do NOT modify the returned `cfg`.
- `resolve_plugin_template_path` is called from both `_config.load_config` and `_review_common.load_config` (imported). The fix to `_config.resolve_plugin_template_path` propagates to both callers automatically.
- All print/log strings use ASCII only (CLAUDE.md rule). No em-dash, no arrows.

### Pre-existing failures (do not fix)

The 4 pre-existing test failures (`test-llm-claude.py`, `test-review-code-flow.py`, `test-review-common.py` "missing config -> ReviewError", `test-review-discussion-flow.py`) are scope of task 64. Do not fix them here. The "missing config -> ReviewError" failure is caused by CLAUDE_PLUGIN_ROOT pointing to the dev tree (template always exists), which changes the strict-missing semantics. That is a separate known issue.

## Testing

### test-config.py (new tests)

Add to the existing test file (at the end of the deep_merge section and load_config section):

1. **`test_deep_merge_none_overlay_preserves_base_dict`** — `deep_merge({"roles": {"k": "v"}}, {"roles": None})` must return `{"roles": {"k": "v"}}` (None does not clobber dict).
2. **`test_deep_merge_none_overlay_allowed_for_scalar`** — `deep_merge({"reviewer": "foo"}, {"reviewer": None})` must return `{"reviewer": None}` (None is allowed to override scalar).
3. **`test_resolve_plugin_template_path_stale_root_fallback`** — Set `CLAUDE_PLUGIN_ROOT` to a non-existent path; call `resolve_plugin_template_path("mill-config.yaml")`; result must be the source-tree path; stderr must contain a warning.
4. **`test_load_config_bare_roles_no_crash`** — Write a `mill-config.yaml` with just `roles:\n` (bare key); call `load_config`; must not crash; `cfg.get("roles")` must be a dict (from template layer, since `None` overlay is skipped).

### test-review-common.py (new tests)

1. **`test_deep_merge_none_overlay_preserves_dict`** — same as above for `_review_common._deep_merge`.
2. **`test_load_config_bare_roles_no_crash`** — Write a `mill-config.yaml` with `roles:\n`; call `_review_common.load_config`; must not crash; `cfg.get("roles")` must be a dict.

### Existing tests that must still pass

- All existing tests in `test-config.py` (30 tests, all currently passing).
- All existing tests in `test-review-common.py` except the 1 pre-existing failure.

## Q&A log

- **Q:** Strip `hub_relative_path` from returned cfg or only from the warn_unknown_keys input? **A:** [auto-pick] Only strip from the warn call copy; keep it in returned cfg. **Why:** No caller currently uses `cfg["hub_relative_path"]` but removing it could silently break something; the minimum change is to suppress the warning only.
- **Q:** Fix both `_config.deep_merge` and `_review_common._deep_merge`? **A:** [auto-pick] Yes, both. **Why:** They are independent copies with the same bug; fixing only one would leave the other broken.
- **Q:** Update mill-go SKILL.md Step 3 text description or only the function call? **A:** [auto-pick] Both — update the prose description to reference mill-config.yaml and fix the function call to use hub_root. **Why:** A prose description that still says "wiki/config.yaml" will mislead future readers even after the call is fixed.
- **Q:** Does `_review_common.load_config` also need `hub_relative_path` stripping? **A:** [auto-pick] Yes — `local_cfg` in `_review_common.load_config` is merged into `cfg` via `_deep_merge(cfg, local_cfg)`, so `hub_relative_path` ends up in cfg and triggers the warning there too. Strip it from the cfg copy before the `warn_unknown_keys` call, same as in `_config.load_config`.
