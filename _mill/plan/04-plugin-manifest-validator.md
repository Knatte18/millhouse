# Batch: plugin-manifest-validator

```yaml
task: 'Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch'
batch: plugin-manifest-validator
number: 4
cards: 4
verify: null
depends-on: []
```

## Batch Scope

Add a new `_plan_validate.py` check (`plugin-manifest-context-missing`) that fails a batch touching a file under `plugins/mill/agents/` (via `Creates:`, `Edits:`, or `Deletes:`) when `plugins/mill/.claude-plugin/plugin.json` is not present in that batch's `Context:` or `Edits:` — closing the bulk-mode-reviewer reachability gap #714 identified (a bulk-mode reviewer cannot fetch `plugin.json` on its own if it isn't in the bulked context). Add the corresponding `mill-plan/SKILL.md` Step 1.5 fix-table row so mill-plan's autonomous validator-fix loop has defined behavior the first time this check fires. Independent of Batch 1/2 (`_review_plan.py` counting fix) and Batch 3 (templates) — no shared files, no ordering dependency.

## Cards

_One `### Card N` per card, numbered globally across all batches._

### Card 17: `_plan_validate.py` — add `_parse_context_only()` helper

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new module-level function `_parse_context_only(batch_path: Path) -> set[str]` immediately after `_parse_deletes_only()` (before the `# move-format check` section comment). Implement it with the identical single-line/multi-line parsing logic as `_parse_edits_only()`/`_parse_creates_only()`/`_parse_deletes_only()` (same `_RE_REFS_HEADER`/`_RE_REFS_SUB` regex usage, same backtick-token extraction, same `none`-filtering), restricted to `- **Context:**` headers (i.e. `m.group(1) == "Context"` in the `_RE_REFS_HEADER.match(lines[i])` check, mirroring how `_parse_edits_only` checks `m.group(1) == "Edits"`). Give it the same docstring shape as its three siblings: "Extract raw path tokens from a batch file's Context: lines only. ... Filters `none` (case-insensitive) per the existing convention."
- **Commit:** `feat(plan-validate): add _parse_context_only helper`

### Card 18: `_plan_validate.py` — add `_check_plugin_manifest_context_missing()` and wire into `run()`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add two new module-level constants immediately above the new check function: `_AGENTS_DIR_PREFIX = "plugins/mill/agents/"` and `_PLUGIN_MANIFEST_PATH = "plugins/mill/.claude-plugin/plugin.json"`. Add a new function `_check_plugin_manifest_context_missing(batch_files: list[Path]) -> list[dict]`, placed immediately after `_check_wiki_config_mutation()` (before the `# Check 8 — all-files-touched-mismatch` section comment). For each `batch_path` in `batch_files`: compute `touched = _parse_creates_only(batch_path) | _parse_edits_only(batch_path) | _parse_deletes_only(batch_path)`; if no path in `touched` starts with `_AGENTS_DIR_PREFIX`, skip this batch (`continue`); otherwise compute `context = _parse_context_only(batch_path)` (the `_parse_context_only` helper added in Card 17) and `edits = _parse_edits_only(batch_path)`; if `_PLUGIN_MANIFEST_PATH` is in neither `context` nor `edits`, append one error dict shaped like `_check_wiki_config_mutation()`'s existing error dicts: `{"check": "plugin-manifest-context-missing", "batch": batch_path.stem, "card": None, "path": _PLUGIN_MANIFEST_PATH, "message": f"batch touches a file under '{_AGENTS_DIR_PREFIX}' but '{_PLUGIN_MANIFEST_PATH}' is not in Context: or Edits:"}`. Wire the new check into `run()` by adding `errors.extend(_check_plugin_manifest_context_missing(batch_files))` immediately after the existing `errors.extend(_check_wiki_config_mutation(batch_files))` line (before `errors.extend(_check_all_files_touched_mismatch(overview_path, batch_files))`). Update the module docstring's "Checks performed (check keys)" list (near the top of the file) and `run()`'s own docstring (the "Checks 1, 2, 3, 4, 5, 6, 8 from issue #10, plus wiki-config-mutation, ..." sentence) to each add a one-line mention of `plugin-manifest-context-missing`, matching the existing entries' phrasing style.
- **Commit:** `feat(plan-validate): add plugin-manifest-context-missing check`

### Card 19: `mill-plan/SKILL.md` — add Step 1.5 fix-table row

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the Step 1.5 fix table (the `| check | mechanical fix |` table), insert a new row immediately after the `all-files-touched-mismatch` row and before the `verify-not-isolated` row:

  `| plugin-manifest-context-missing | Add \`plugins/mill/.claude-plugin/plugin.json\` to the offending batch's \`Context:\` list (unless the batch's own \`Edits:\` already includes it, in which case the check should not have fired — re-verify the check's \`Creates:\`/\`Edits:\`/\`Deletes:\` prefix match before editing the plan). |`

  Match the table's existing column-alignment style (pipe-delimited, no strict width enforcement needed beyond what a markdown table renderer requires).
- **Commit:** `docs(mill-plan): add plugin-manifest-context-missing fix-table row`

### Card 20: `test-plan-validate.py` — add tests for `plugin-manifest-context-missing`

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add 5 new test functions, following the exact structure of `test_wiki_config_mutation_clean()`/`test_wiki_config_mutation_modifies()` (build a plan fixture via `_make_overview()` + `_make_batch_file()` + `_write_plan()`, call `_plan_validate.run(plan_dir, project_root)`, filter `result` for `e["check"] == "plugin-manifest-context-missing"`, assert count and — when an error is expected — assert `e["batch"]`, `e["card"] is None`, and `e["path"] == "plugins/mill/.claude-plugin/plugin.json"`):
  1. `test_plugin_manifest_context_missing_creates_dirty() -> int` — one batch with `creates=["plugins/mill/agents/new-agent.md"]`, `context=None`, `edits=None` → assert exactly 1 error.
  2. `test_plugin_manifest_context_missing_creates_with_context_clean() -> int` — same batch but `context=["plugins/mill/.claude-plugin/plugin.json"]` → assert exactly 0 errors.
  3. `test_plugin_manifest_context_missing_creates_with_edits_clean() -> int` — same batch but `edits=["plugins/mill/.claude-plugin/plugin.json"]` (plugin.json in `Edits:` instead of `Context:` — the primary expected case, registering a new agent) → assert exactly 0 errors.
  4. `test_plugin_manifest_context_missing_deletes_dirty() -> int` — one batch with `deletes=["plugins/mill/agents/old-agent.md"]`, `context=None`, `edits=None` (the symmetric removal case) → assert exactly 1 error.
  5. `test_plugin_manifest_context_missing_unrelated_batch_clean() -> int` — one batch touching only unrelated paths (e.g. `edits=["plugins/mill/scripts/_review_plan.py"]`, `context=None`) with `plugins/mill/.claude-plugin/plugin.json` absent from every field → assert exactly 0 errors (the batch never touches `plugins/mill/agents/`, so the check must not fire regardless of Context:/Edits: contents).

  Each test wraps its body in `with tempfile.TemporaryDirectory() as tmpdir: ... try: ... assert ...; print(f"PASS {test-name}"); return 0 ... except AssertionError as exc: print(f"FAIL {test-name}: {exc}", file=sys.stderr); return 1`, identical to the existing `test_wiki_config_mutation_*` functions. Add a `# plugin-manifest-context-missing check` comment followed by all 5 new function names to the `tests` list inside `main()`, inserted immediately after `test_wiki_config_mutation_modifies_and_creates,` and before the `# skip_checks filtering (Card 7 / #188)` comment.
- **Commit:** `test(plan-validate): cover plugin-manifest-context-missing check`

## Batch Tests

`verify:` runs `test-plan-validate.py`, which now covers all 5 cases of the new `plugin-manifest-context-missing` check (dirty via `Creates:`, clean via `Context:`, clean via `Edits:`, dirty via `Deletes:` (symmetric), clean when the batch never touches `plugins/mill/agents/`) alongside the full pre-existing check suite in this file.
