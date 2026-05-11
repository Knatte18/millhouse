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

### Card 14: Verify `_setup.create_hub_links` and `_wiki.read_hardlinks` already tolerate missing `hardlinks:` block; tighten docstring

- **Context:**
  - `plugins/mill/scripts/_setup.py`
- **Edits:**
  - `plugins/mill/scripts/_wiki.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. **Verification first.** Read `_wiki.read_hardlinks` (around line 108) and the surrounding `_HARDLINK_DEFAULTS` constant. Today the code reads: `raw = cfg.get("hardlinks"); if not raw: return dict(_HARDLINK_DEFAULTS)`. `_HARDLINK_DEFAULTS` is `{}` (no hardlinks unless configured). So the function already returns `{}` when (a) the key is absent, (b) the value is `None` (yaml `hardlinks: null`), or (c) the value is an empty dict — all collapse via the falsy check. Read `_setup.create_hub_links` (the iteration is at approximately line 111: `for link_rel, target_template in hardlinks_cfg.items():`). With an empty dict input, the loop body does not execute and `created_hardlinks` stays empty — verified by inspection. **Conclusion:** the runtime code already handles the missing-block case correctly; no code change to `_wiki.py` runtime behavior or `_setup.py` is needed.
  2. **Docstring update.** Even though the absent-block behavior is correct, the docstring on `_wiki.read_hardlinks` should explicitly call it out so future callers know they must tolerate `{}`. Find the existing docstring (lines 108–117 area). The current docstring says: `Missing config file or missing 'hardlinks:' block returns an empty dict (no hardlinks configured).` Append a sentence: `Also returns an empty dict when the block is explicitly null (hardlinks: null), since yaml.safe_load yields None for an explicit-null and the falsy check collapses both cases. Callers (e.g. _setup.create_hub_links) must tolerate an empty result.` Place it as the last sentence of the docstring, before the closing triple quotes.
  3. Do NOT modify `_setup.create_hub_links` at all — its iteration is already correct.
  4. Do NOT modify any other functions in `_wiki.py`.
  5. The regression test in Card 15 backstops this card's "verification" — even though the docstring update is the only file change, Card 15 ensures the behavior cannot regress silently.
- **Commit:** `docs(_wiki): note read_hardlinks tolerates missing or null block (#235)`

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
