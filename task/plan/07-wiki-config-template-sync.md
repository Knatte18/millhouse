# Batch: wiki-config-template-sync

```yaml
task: 44 (A) — Bug-fix batch 4
batch: wiki-config-template-sync
number: 7
cards: 3
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-setup-hub-links.py
depends-on: []
```

## Batch Scope

`plugins/mill/templates/wiki-config.yaml` ships with old conventions that bite new hubs created via mill-setup (#235). User-specified scope: remove the `hardlinks:` block (we use `.wiki/Home.md` direct navigation), change the junction key `.millhouse/wiki` to `.wiki` (matching production), drop "Layer 02/03/04" subheading relics from comments, ensure `_setup.create_hub_links` and `_wiki.read_hardlinks` handle absence gracefully, and add a regression test for graceful absence. The CLAUDE.md template-mirror rule was added in Batch 1.

## Cards

### Card 13: Edit `plugins/mill/templates/wiki-config.yaml`

- **Context:**
  - `C:/Code/millhouse/wiki/config.yaml`
- **Edits:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Remove the entire `hardlinks:` block (currently around lines 44–52) AND the preceding comment header `# Hardlinks` plus its dashed divider line. Production no longer needs the hardlinks block for new hubs (the `.wiki/Home.md` junction provides the same navigation). If a hub WANTS hardlinks, they can add the block manually.
  2. Change the junctions block: `.millhouse/wiki: <WIKI_PATH>` → `.wiki: <WIKI_PATH>`. Keep the `.active: <WIKI_PATH>/active/<SLUG>/` line unchanged. Update the comment about per-worktree/hub-scope above the block if it mentions the old junction name.
  3. Remove "Layer 02", "Layer 03", "Layer 04" prefixes from the section-divider comments. Rewrite each affected divider so it reads as plain section title — e.g. `# Layer 02: file-path templates (relative to wiki root, <SLUG> substituted)` → `# File-path templates (relative to active worktree root)`; `# Layer 03: mill-go pipeline` → `# mill-go pipeline`; `# Layer 02: reviewer roles` → `# Reviewer roles`. Match production wiki/config.yaml's section-title style (production no longer uses "Layer NN" prefixes — verify by reading the production file before editing).
  4. Do NOT change the `roles:` schema, the `paths:` template, the `llm:` timeouts, the `pipeline:` keys, `notify:`, `groom:`, `merge:`, or `spawn:`. Only the three changes above. Keep all current comments that document field semantics.
  5. After editing, verify by hand-diff that the only structural changes are the three listed. Comment-only edits are acceptable for clarification, but the YAML structure (key paths) is unchanged except for the hardlinks deletion and the junction-key rename.
- **Commit:** `fix(template): sync wiki-config.yaml to production conventions (#235)`

### Card 14: Make `_setup.create_hub_links` and `_wiki.read_hardlinks` tolerate missing `hardlinks:` block

- **Context:**
  - `plugins/mill/scripts/_setup.py`
- **Edits:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_setup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Read `_wiki.read_hardlinks` (around line 108). If it currently does `cfg["hardlinks"]` (raising `KeyError` on absence) or returns a non-empty default on absence, change it to: read the `hardlinks:` value from the parsed config via `cfg.get("hardlinks", {}) or {}` (the `or {}` covers the explicit `hardlinks: null` case which `yaml.safe_load` returns as `None`). Returns `dict[str, str]` — empty dict when the block is absent or null.
  2. Read `_setup.create_hub_links`. The function iterates `hardlinks_cfg.items()` (line 111 in current code) — confirm that with an empty dict input, the loop body does NOT execute and the return value is `{"junctions": [...], "hardlinks": []}` (the `created_hardlinks` list stays empty). If `_setup` already handles this case (the loop just skips), no edit needed; if it dereferences before iterating, fix the dereference.
  3. Add (or expand) a docstring sentence on `read_hardlinks` describing the absence behavior: `Returns an empty dict when the wiki/config.yaml has no hardlinks: block, or when the block is explicitly null (hardlinks: null). Callers must tolerate empty results.`
  4. Do NOT add a runtime warning or breadcrumb — absent hardlinks is a valid configuration.
  5. Re-check by reading the helper signature: if `_wiki.read_hardlinks` is also used elsewhere (grep across `plugins/mill/scripts/`), ensure no caller assumes a non-empty result.
- **Commit:** `fix(_wiki,_setup): tolerate missing hardlinks block (#235)`

### Card 15: Regression test for graceful absence in `test-setup-hub-links.py`

- **Context:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_setup.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-setup-hub-links.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add one test function `test_create_hub_links_handles_missing_hardlinks_block`:
  1. Build a tmp_path with a `wiki/` dir.
  2. Write `wiki/config.yaml` with a `junctions:` block (one entry, e.g. `.wiki: <WIKI_PATH>`) and NO `hardlinks:` block.
  3. Build a target_root dir.
  4. Call `_setup.create_hub_links(target_root, wiki_path, tokens)` (or whichever signature the function exposes — match the existing tests in the file).
  5. Assert the return value's `hardlinks` key holds an empty list, and `junctions` is a one-entry list.
  6. Assert no exception was raised.
  Add a second test if the file already covers `hardlinks: null` (explicit null) separately — `test_create_hub_links_handles_null_hardlinks_block`: same as above but the config yaml has `hardlinks: null` literally. Assertion is identical.
- **Commit:** `test(_setup): cover create_hub_links with missing hardlinks block`

## Batch Tests

`verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-setup-hub-links.py`. The new tests above must pass; all pre-existing tests must continue to pass.
