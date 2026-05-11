# Batch: integrate-and-document

```yaml
task: 45 (A) — Machine-level config layer
batch: integrate-and-document
number: 2
cards: 6
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

Wires the machine-config layer (from batch 1) into the two production `load_config` helpers, adds cross-layer test cases in `test-config.py`, ships the operator-facing template + header documentation, and adds the read-only Phase 4.95 to `mill-setup`. The deliverable is a fully functional machine-config layer: editing `~/.millhouse/config.machine.yaml` actually changes the merged cfg dict every mill helper sees. After this batch lands, all 18 `load_config` call sites benefit transparently — no per-caller code changes anywhere outside `_config.py` and `_review_common.py`. Batch-local decisions: none beyond Shared Decisions in `00-overview.md`.

## Cards

### Card 3: Wire machine layer into `_config.load_config`

- **Context:**
  - `plugins/mill/scripts/_machine.py`
  - `plugins/mill/unit_tests/test-config.py`
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Modify `plugins/mill/scripts/_config.py` to read the machine config layer between the wiki layer and the worktree-stub layer.
  - Add `import _machine` to the module's import block, alongside the existing `import yaml`.
  - In the `load_config(wiki_path, worktree_root)` function body, after the existing `if shared_path.exists(): cfg = yaml.safe_load(...) or {}` block, insert a new line: `cfg = deep_merge(cfg, _machine.load_layer())`. This must be placed BEFORE `stub_path = worktree_root / ".millhouse" / "config.local.yaml"`. The machine layer applies after wiki, before worktree stub + real.
  - Update the module-level docstring: in the `Exports` block, rewrite the `load_config(...)` description from "Load `wiki/config.yaml` deep-merged with `.millhouse/config.local.yaml`" to "Load `wiki/config.yaml` deep-merged with `~/.millhouse/config.machine.yaml` and `.millhouse/config.local.yaml`. Machine layer (read via `_machine.load_layer`) lands between wiki and worktree layers; later layers win on key conflicts."
  - Update the `load_config` function docstring: add a sentence to the existing one-paragraph body explaining that the machine layer at `~/.millhouse/config.machine.yaml` is read between the wiki and worktree-stub layers via `_machine.load_layer()`. Missing machine file → `_machine.load_layer` returns `{}` and the merge is a no-op. Update `Returns:` to: "Merged configuration dict (may be empty). Merge order, lowest to highest precedence: wiki → machine → worktree-stub → worktree-real."
  - Do NOT change the function signature.
  - Do NOT change `deep_merge` or `set_local_wiki_overrides`.
- **Commit:** `feat(config): merge machine-level config layer into load_config`

### Card 4: Wire machine layer into `_review_common.load_config`

- **Context:**
  - `plugins/mill/scripts/_machine.py`
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Modify `plugins/mill/scripts/_review_common.py`'s `load_config(wiki_root, mill_dir)` function to read the machine layer between the wiki layer and the worktree-local layer.
  - Add `import _machine` to the existing top-of-file import block.
  - In `load_config` (around lines 942–972), after the line `cfg = yaml.safe_load(fh) or {}` (which reads the wiki shared config) and before the line `local_path = mill_dir / "config.local.yaml"`, insert: `cfg = _deep_merge(cfg, _machine.load_layer())`. Use the existing private `_deep_merge` (defined at module top) — do NOT import `deep_merge` from `_config`.
  - Update the function docstring: replace "Load `config.yaml` from `wiki_root`, optionally merging `config.local.yaml`." with "Load `config.yaml` from `wiki_root`, deep-merged with `~/.millhouse/config.machine.yaml` (via `_machine.load_layer`) and optionally with `mill_dir/config.local.yaml`." Add a second sentence: "Merge order, lowest to highest precedence: wiki → machine → worktree-local."
  - Leave the strict semantics intact — `ReviewError` is still raised when `shared_path` does not exist.
  - Leave the existing `stale 'review:' keys` warning intact — only the worktree-local layer triggers it; the machine layer does NOT get the stale-keys warning even if it contains a `review:` key (the warning fires only when reading `mill_dir/config.local.yaml`).
- **Commit:** `feat(review): merge machine-level config layer into _review_common.load_config`

### Card 5: Add machine-layer cases to `test-config.py`

- **Context:**
  - `plugins/mill/scripts/_machine.py`
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add four new test functions to `plugins/mill/unit_tests/test-config.py` covering machine-layer merge behaviour. Each test patches `Path.home` to a `tempfile.TemporaryDirectory()` via `unittest.mock.patch.object(Path, "home", return_value=Path(tmp_home))` used as a `with` context manager. Add `from unittest.mock import patch` to the file's import block.
  - `test_load_config_machine_layer_present_merged()` — set up: `wiki/config.yaml` contains `spawn:\n  branch_prefix: feat\n`, `<tmp_home>/.millhouse/config.machine.yaml` contains `roles:\n  discussion-review:\n    holistic:\n      reviewer: cluster-gemini\n`. Inside `with patch.object(Path, "home", return_value=Path(tmp_home)):` call `_config.load_config(wiki, wt_root)`. Assert `cfg["spawn"]["branch_prefix"] == "feat"` AND `cfg["roles"]["discussion-review"]["holistic"]["reviewer"] == "cluster-gemini"`.
  - `test_load_config_machine_absent_graceful()` — set up: `wiki/config.yaml` contains `spawn:\n  branch_prefix: feat\n`. Create `<tmp_home>` but NO `<tmp_home>/.millhouse/`. No worktree-local file. Inside the patch context, call `_config.load_config(wiki, wt_root)`. Assert the result equals `{"spawn": {"branch_prefix": "feat"}}`. No exception raised.
  - `test_load_config_machine_overrides_wiki()` — set up: `wiki/config.yaml` contains `spawn:\n  branch_prefix: shared\n`, `<tmp_home>/.millhouse/config.machine.yaml` contains `spawn:\n  branch_prefix: machine\n`. No worktree-local file. Inside the patch context, call `_config.load_config(wiki, wt_root)`. Assert `cfg["spawn"]["branch_prefix"] == "machine"`.
  - `test_load_config_worktree_overrides_machine()` — set up: `wiki/config.yaml` contains `spawn:\n  branch_prefix: shared\n`, `<tmp_home>/.millhouse/config.machine.yaml` contains `spawn:\n  branch_prefix: machine\n`, `<wt_root>/.millhouse/config.local.yaml` contains `spawn:\n  branch_prefix: worktree\n`. Inside the patch context, call `_config.load_config(wiki, wt_root)`. Assert `cfg["spawn"]["branch_prefix"] == "worktree"`.
  - Register all four functions in the `tests = [...]` list in `main()` (append after the existing six `test_load_config_*` entries, before the `test_deep_merge_*` entries). Existing tests stay unchanged — they don't patch `Path.home`, so they use the real one; their tempdir setups don't create `~/.millhouse/config.machine.yaml` so the new layer's merge is a no-op for them. **Caveat:** if the developer running tests has a real `~/.millhouse/config.machine.yaml`, the existing tests will pick up its keys via the new merge step. The existing tests' assertions check only keys they themselves seeded, so this should not cause failures in practice; document this caveat in a comment above the new test block: `# Tests below patch Path.home; pre-existing tests use the real home dir but their assertions only check seeded keys, so machine-config presence is benign.`
- **Commit:** `test(config): cover machine-layer merge cases`

### Card 6: Add `templates/config.machine.yaml` operator template

- **Context:**
  - `plugins/mill/templates/config.local.yaml`
- **Edits:** none
- **Creates:**
  - `plugins/mill/templates/config.machine.yaml`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/templates/config.machine.yaml`. The file is a commented-out template the operator copies (manually) to `~/.millhouse/config.machine.yaml`. Layout:
  - Top comment header block (every line prefixed `#`) covering:
    - File location: `~/.millhouse/config.machine.yaml` (i.e., `$HOME/.millhouse/`, outside every git repo — automatically untracked, no gitignore needed).
    - Scope: one file per machine; all worktrees on this machine read it.
    - Merge order: `wiki/config.yaml` (shared, lowest precedence) → THIS FILE (machine) → `<worktree>/.millhouse/config.local.yaml` (worktree, highest precedence).
    - Typical uses: machine-specific reviewer mode (e.g. `cluster-gemini` on a GPU-rich box, `sonnet` elsewhere), per-machine notification settings.
    - mill-setup behaviour: probes for this file and reports status during `Phase 4.95`. NEVER creates the file. Copy this template by hand: `cp plugins/mill/templates/config.machine.yaml ~/.millhouse/config.machine.yaml`.
    - Secrets do NOT belong here — use `.env` at the repo root.
  - Blank line, then commented-out example keys (all lines prefixed `#` so the file is effectively empty when copied verbatim — operator uncomments what they want):
    - `roles:` block with `discussion-review.holistic.reviewer`, `plan-review.holistic.reviewer`, `code-review.batch.reviewer` examples — three lines each showing how to override a single reviewer.
    - `notifications:` block with `toast: true` as the only example.
  - Do NOT include `hub_relative_path` (per the Decision in `discussion.md`: worktree-shape, not machine-shape — silently ignored at the machine layer).
  - Do NOT include a `wiki:` block (per the Decision in `discussion.md`: persisted automatically by `mill-setup`, not hand-edited at machine scope).
- **Commit:** `chore(templates): add config.machine.yaml template`

### Card 7: Document the three layers in `templates/config.local.yaml` header

- **Context:**
  - `plugins/mill/templates/config.machine.yaml`
- **Edits:**
  - `plugins/mill/templates/config.local.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Insert a header comment block into `plugins/mill/templates/config.local.yaml` describing the three-layer merge order.
  - Insert location: after the existing line 6 (`# local values win on any conflict.`) and before the existing blank line that precedes the "Secrets DO NOT belong here" paragraph.
  - Inserted content (each line prefixed `#`, blank `#` line as separator):
    ```
    #
    # Merge layers (lowest -> highest precedence):
    #   1. wiki/config.yaml                  - shared, git-tracked in the wiki
    #   2. ~/.millhouse/config.machine.yaml  - per-machine, untracked (lives outside every repo)
    #   3. THIS FILE                         - per-worktree, gitignored
    #
    # Keys that should be the same across all worktrees on this machine belong in
    # ~/.millhouse/config.machine.yaml, not here. Template at
    # plugins/mill/templates/config.machine.yaml.
    ```
  - Use plain ASCII `->` (not the Unicode arrow) so cp1252 consoles render it cleanly.
  - Do NOT renumber, reword, or remove any existing lines — only insert the new block.
- **Commit:** `docs(templates): describe three config layers in config.local.yaml header`

### Card 8: Add Phase 4.95 to `mill-setup/SKILL.md` and update Phase 8

- **Context:**
  - `plugins/mill/scripts/_machine.py`
  - `plugins/mill/templates/config.machine.yaml`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Modify `plugins/mill/skills/mill-setup/SKILL.md` to teach the skill about the machine layer.
  - Insert a new section `### Phase 4.95 — Probe machine-level config (read-only)` between the existing `### Phase 4.9 — Seed hub_relative_path in config.local.yaml` and `### Phase 5 — Seed .millhouse/config.local.yaml`. The new section contains:
    1. One-sentence intro: "Read-only check that `~/.millhouse/config.machine.yaml` is present and parseable. Never creates, prompts, or halts."
    2. A code-fenced `bash` block exercising `_machine.probe()`:
       ```bash
       PYTHONPATH="$CLAUDE_PLUGIN_ROOT/scripts" uv run --project "$CLAUDE_PLUGIN_ROOT" python -c "
       import _machine
       status, detail = _machine.probe()
       path = _machine.machine_config_path()
       if status == _machine.MISSING:
           print(f'{path}: not present (optional - copy plugins/mill/templates/config.machine.yaml here to set machine-wide overrides)')
       elif status == _machine.PRESENT:
           keys = sorted(detail.keys()) if isinstance(detail, dict) else []
           summary = ', '.join(keys) if keys else '(empty)'
           print(f'{path}: loaded ({len(keys)} top-level keys: {summary})')
       else:
           print(f'{path}: present but parse failed ({detail}); fix or remove the file')
       "
       ```
    3. Note paragraph: "MALFORMED status is reported but does NOT halt the phase — the operator is responsible for fixing the file; subsequent mill commands will still hit the YAML parse error when they load config, so this phase is purely an early warning."
  - In `### Phase 8 — Verify + report`:
    - Add one bullet to the verify-list (insert after the existing `\`hub_relative_path:\` is set in \`.millhouse/config.local.yaml\`` bullet): "Machine-level config at `~/.millhouse/config.machine.yaml` (if present) parses as valid YAML — verify via `_machine.probe()` returning `MISSING` or `PRESENT`, not `MALFORMED`."
    - In the success-summary print block (the fenced code-block beginning with `mill-setup complete.`), add a new line after the existing `  hub_relative_path: <hub_subpath>` line: `  Machine config:    <path-or-"(none)">`. Document the format in the surrounding prose: when probe returns `MISSING`, print `(none)`; on `PRESENT`, print the absolute path; on `MALFORMED`, print `<path> (MALFORMED — fix manually)`.
  - Do NOT modify the "Layout assumed", "How to invoke the helpers", "Error conditions", or "Idempotency" sections — Phase 4.95 is purely additive and the file `~/.millhouse/config.machine.yaml` is outside every layout assumption (lives in `$HOME`, not in container or worktree).
- **Commit:** `docs(mill-setup): add Phase 4.95 machine-config probe and Phase 8 verify`

## Batch Tests

Run `python plugins/mill/unit_tests/run-all.py` from the worktree root. Expected: every existing test passes (including the unchanged six `test_load_config_*` and three `test_deep_merge_*` and six `set_local_wiki_overrides` tests in `test-config.py`); the four new `test_load_config_*` entries in `test-config.py` pass; the four `test-machine.py` entries pass. Total tests increase by 4 (test-config.py) + 4 (test-machine.py) = 8 new entries on top of the existing suite. Exit code 0.

No new template-rendering tests are needed — `config.machine.yaml` and the updated `config.local.yaml` are operator-facing comment files, never rendered by `_render.render`. The mill-setup `Phase 4.95` invocation is verified by manual run-through (the SKILL.md change is documentation, not runnable code), tracked under the discussion's "Manual smoke test" section.
