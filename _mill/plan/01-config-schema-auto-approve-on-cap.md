# Batch: config-schema-auto-approve-on-cap

```yaml
task: "Auto-approve on review-round cap"
batch: "config-schema-auto-approve-on-cap"
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
depends-on: []
```

## Batch Scope

Adds the new opt-in `auto_approve_on_cap` config key (default `false`) to the three review-role/scope blocks this task targets — `roles.plan-review.holistic`, `roles.code-review.batch`, `roles.code-review.holistic` — in both the plugin config template and this hub's own committed `mill-config.yaml`, keeping the two in sync per this repo's own `CLAUDE.md` ("mill-config.yaml hub file and plugin template must stay in sync — template seeds new hubs"). Adds a unit test confirming the new keys don't trigger `_config.py`'s unknown-key stderr warning. This batch has no batch-local decisions beyond the two Shared Decisions ("config key shape", "wiki-config-mutation skip-check bootstrap justification") it directly implements. External interface for batches 2-4: the exact key path `roles.<role>.<scope>.auto_approve_on_cap`, read via `cfg.get("roles", {}).get(<role>, {}).get(<scope>, {}).get("auto_approve_on_cap", False)`.

## Cards

### Card 1: Add `auto_approve_on_cap` to the plugin config template

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `roles:` section, add a new `auto_approve_on_cap: false` line to each of these three existing blocks, immediately after each block's own `min_rounds:` line (or, for `roles.code-review.batch`, immediately after its `min_rounds:` line — that block already has one): `roles.plan-review.holistic`, `roles.code-review.batch`, `roles.code-review.holistic`. Give each new line a short inline comment explaining its effect, e.g. `auto_approve_on_cap: false  # true: treat round-cap exhaustion with REQUEST_CHANGES still outstanding as an implicit approval instead of halting`. Do not add this key to `roles.plan-review.batch` or `roles.discussion-review.holistic` — both are out of scope for this task (see `_mill/discussion.md`'s "Which loops get the flag" Decision).
- **Commit:** `config: add auto_approve_on_cap key to plugin config template`

### Card 2: Add `auto_approve_on_cap: false` to this hub's own `mill-config.yaml`

- **Context:**
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `auto_approve_on_cap: false` to the same three blocks in this hub's own root `mill-config.yaml` — `roles.plan-review.holistic`, `roles.code-review.batch`, `roles.code-review.holistic` — at the same relative position (immediately after each block's `min_rounds:` line), matching Card 1's edit to the template so the hub config and the plugin template stay in sync (`CLAUDE.md` is mentioned, not read, for this repo's own "hub file and template must stay in sync" convention). This is the mid-flight `mill-config.yaml` mutation the overview's "`wiki-config-mutation` skip-check bootstrap justification" Shared Decision documents — an explicit-`false` key addition, identical to today's implicit-absent default, so no existing behavior changes as a result of this edit.
- **Commit:** `config: add auto_approve_on_cap key to hub mill-config.yaml`

### Card 3: Unit test — new keys don't trigger the unknown-key warning

- **Context:**
  - `plugins/mill/templates/mill-config.yaml`
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new test function `test_load_config_auto_approve_on_cap_keys_present`, modeled directly on the existing `test_load_config_rename_detect_pct_key_present` function in this same file (same fixture shape: resolve `real_template_path` via `Path(__file__).resolve().parent.parent / "templates" / "mill-config.yaml"`, assert it exists, create a temp `hub_root` with `_git_init(hub_root)`, patch `_config.resolve_plugin_template_path` to return `real_template_path`, capture `sys.stderr` via `patch("sys.stderr", new=io.StringIO())`, call `_config.load_config(hub_root, hub_root)`). Inside the patched-stderr block, assert all three of: `cfg.get("roles", {}).get("plan-review", {}).get("holistic", {}).get("auto_approve_on_cap") is False`, `cfg.get("roles", {}).get("code-review", {}).get("batch", {}).get("auto_approve_on_cap") is False`, and `cfg.get("roles", {}).get("code-review", {}).get("holistic", {}).get("auto_approve_on_cap") is False`. After the patched block, assert `"unknown key" not in stderr_output or "auto_approve_on_cap" not in stderr_output` is too weak — instead assert the precise substring is absent for each of the three paths: `"unknown key: roles.plan-review.holistic.auto_approve_on_cap" not in stderr_output`, `"unknown key: roles.code-review.batch.auto_approve_on_cap" not in stderr_output`, `"unknown key: roles.code-review.holistic.auto_approve_on_cap" not in stderr_output`. End with `print("PASS: roles.*.auto_approve_on_cap keys present (default False) and no unknown-key warning")`. Then add `test_load_config_auto_approve_on_cap_keys_present` to the `tests = [...]` list inside `main()` at the bottom of this file, immediately after the existing `test_load_config_done_gate_key_present` entry (mirroring where the analogous `rename_detect_pct`/`done_gate` tests already sit in that list).
- **Commit:** `test: add config-schema coverage for auto_approve_on_cap keys`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-config.py` directly (single-file scope; this batch's only edit under test is that file plus the two YAML files it reads). Card 3's new test is the acceptance check for cards 1-2: it loads the real template through `_config.load_config` and asserts both that the three new keys resolve to `False` and that loading them produces no `[config] unknown key: ...` stderr warning — the failure mode this whole batch exists to prevent.
