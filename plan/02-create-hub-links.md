# Batch: create-hub-links

```yaml
task: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split
batch: create-hub-links
cards: 5
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [foundation]
```

## Batch Scope

This batch ships the unified junction/hardlink creation path and wires it into `mill-spawn` and `mill-claim`. Net effect: every newly-spawned worktree gets `.millhouse/wiki`, `.others`, `.active`, AND `tasks.md` (the previously-skipped hardlink) — all from one helper, with a token-scope filter so the same helper works for the main worktree (no slug, skips slug-bearing entries) and for child worktrees (slug present, all entries created). `wiki/config.yaml` is updated atomically with the spawn/claim wiring (see Shared Decision: wiki/config.yaml change atomicity) so a fresh clone reading the new config produces the new junction targets immediately. Working state still lives in `wiki/active/<slug>/` after this batch — moving state onto the worktree is batch 03's job. The external interface this batch produces is `_setup.create_hub_links(target_root, wiki_path, tokens)`, which batches 03 and 04 use unchanged. Local decision diverging from shared: this batch writes wiki/config.yaml `junctions:` block but NOT `paths:` block (paths block is moved in batch 03 alongside the worktree-relative review-template wiring).

## Cards

### Card 6: `_setup.create_hub_links` shared helper

- **Reads:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_active.py`
  - `wiki/active/container-restructure/discussion.md`
- **Modifies:** none
- **Creates:**
  - `plugins/mill/scripts/_setup.py`
  - `plugins/mill/unit_tests/test-setup-hub-links.py`
- **Requirements:** New module `_setup.py` exposing `create_hub_links(target_root: Path, wiki_path: Path, tokens: dict[str, str]) -> dict[str, list[Path]]`. The helper iterates BOTH `_wiki.read_junctions(wiki_path)` AND `_wiki.read_hardlinks(wiki_path)` (the missing-hardlink bug fix is folded here). For every entry it scans the target template for `<TOKEN>` references using a regex, intersects with the supplied `tokens` dict, and silently SKIPS the entry if any required token is absent — this is the token-scope filter from discussion.md `## Decisions → junctions-block-semantic` that lets the same helper handle main worktree (no `<SLUG>`) and child worktrees (`<SLUG>` present). For each surviving junction entry: resolve the template via `_junction.resolve_target`, ensure the target directory exists when the template carries `<SLUG>` (per existing mill-spawn behaviour), then call `_junction.create(target, link_path)`. For each surviving hardlink entry: resolve target template the same way. If `link_path` does not exist (first-run case), skip the inode check and proceed directly to `Path.hardlink_to`. Otherwise check inode equality with `Path.stat().st_ino` — skip on match (idempotent), back up to `<link>.bak` and remove on inode mismatch, then create via `Path.hardlink_to`. Return a dict `{"junctions": [created_paths...], "hardlinks": [created_paths...]}` for caller-side logging. Cross-volume hardlink failure surfaces with a clear ValueError naming the source/target paths (matches existing mill-setup phase 4.5 behaviour). `_junction.resolve_target`'s strict ValueError on unknown tokens is preserved — filtering happens BEFORE the call, so unknown tokens still raise. New test file `test-setup-hub-links.py` covers, using `tempfile.TemporaryDirectory()` and real disk operations (no mocks): token-scope filter (no `<SLUG>` skips `.active`); mixed slug+non-slug entries; hardlink inode skip; hardlink inode-mismatch backup-and-recreate; both empty config blocks return empty lists; cross-volume hardlink raises with a clear message. Synthesise `wiki/config.yaml` for the test from a YAML dict. Additionally, the file owns real-disk integration assertions for Card 8's flow (these were originally proposed for `test-millpy-spawn.py` but live here because that file is mock-based): synthesise a fixture worktree alongside a fixture wiki + portals dir + slug, run `create_hub_links` against the fixture worktree, then assert (a) `.others` junction inside the fixture worktree exists and resolves to the fixture portals dir; (b) `.active` junction inside the fixture worktree exists and resolves to the fixture `portals/<slug>` (which itself was prepared as a junction → fixture worktree); (c) `tasks.md` hardlink exists at the fixture worktree root and shares an inode with the fixture `wiki/Home.md`; (d) `.millhouse/wiki` junction exists and resolves to the fixture wiki path. The fixture sequence (mkdir portals → create portals/<slug> junction → call create_hub_links) mirrors the live flow specified in Card 8.
- **Commit:** `feat(setup): add _setup.create_hub_links helper with token-scope filter`

### Card 7: `_spawn_core.recreate_active_junction` signature + target change

- **Reads:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/unit_tests/test-spawn-core.py`
- **Modifies:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/unit_tests/test-spawn-core.py`
- **Creates:** none
- **Requirements:** Change the function signature from `recreate_active_junction(wiki_path, slug, mill_dir)` to `recreate_active_junction(slug, mill_dir, container_path)`. The new target is `container_path / "portals" / slug` (matches `<CONTAINER_PATH>/portals/<SLUG>/` from the new junctions block). Behaviour preserved: ensure target dir exists, idempotently remove existing junction at `mill_dir.parent / ".active"`, call `_junction.create`. Update the docstring; in particular, REWRITE the line that says "mill-spawn does NOT call this helper" to "mill-spawn does NOT call this helper directly — it routes through `_setup.create_hub_links` which iterates the full `junctions:` block including `.active`." Keep the comment (the operator-facing fact is still useful documentation); just update its rationale. Update tests in `test-spawn-core.py` to reflect the new signature and new target shape. Note: the `wiki_path` parameter is removed entirely; callers (mill-claim) supply `container_path` via `_paths.resolve_container_path(git_root)` (the helper added in Card 4) — NOT `_paths.resolve_main_worktree_root(git_root).parent`. The latter expression returns `<container>/wts/` in container-form, landing the portal entry under `<container>/wts/portals/<slug>` instead of `<container>/portals/<slug>`. Card 9's portal-creation step uses the same helper, and Card 7's docstring/test setup must reference the same expression to avoid two cards instructing different derivations.
- **Commit:** `refactor(spawn-core): retarget .active to portals/<slug>; drop wiki_path arg`

### Card 8: `millpy-spawn.py` use `_setup.create_hub_links` + portal entry

- **Reads:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/_setup.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Requirements:** Replace the manual junction-creation loop (currently lines ~194–207) with `_setup.create_hub_links(worktree_path, wiki_path, tokens)` — but the call ORDER matters (see below). Update `_build_tokens` to compute `CONTAINER_PATH` correctly: change `"CONTAINER_PATH": str(git_root.parent)` to `"CONTAINER_PATH": str(_paths.resolve_container_path(git_root))` (using the new helper from Card 4). After migration `git_root.parent` is `<container>/wts/` (wrong); the helper returns `<container>/` (right) for both container-form and prefix-form. Tokens dict already has `<HUB_PATH>`, `<CWD_PATH>`, `<WIKI_PATH>`, `<REPO>`, `<SLUG>` plus the corrected `<CONTAINER_PATH>` — all required tokens present so every junction in `wiki/config.yaml` is created (including the new `.others` and the retargeted `.active`). Order of operations in mill-spawn (CRITICAL — Windows `mklink /J` fails when the target directory does not exist, and `_setup.create_hub_links` will try to create `.others → <CONTAINER_PATH>/portals/` AND `.active → <CONTAINER_PATH>/portals/<SLUG>/`): (1) `container_path = _paths.resolve_container_path(git_root)`; create `container_path / "portals"` directory with `Path.mkdir(parents=True, exist_ok=True)`. (2) Create the portal entry: `_junction.create(target=worktree_path, link_path=container_path / "portals" / slug)`. The link_path is fresh (newly-spawned worktree's portal entry didn't exist before this run); target is the just-created child worktree. After this step, both `<container>/portals/` and `<container>/portals/<slug>` exist (the latter as a junction → worktree). (3) Now call `_setup.create_hub_links(worktree_path, wiki_path, tokens)`. The `.others` target (`<CONTAINER_PATH>/portals/`) already exists, the `.active` target (`<CONTAINER_PATH>/portals/<SLUG>/`) already exists as a junction (`mkdir(exist_ok=True)` inside `create_hub_links` is a no-op when the path is a junction), and `.millhouse/wiki` works as before. Drop the now-unused `_junction` import if `_junction.create` is no longer called directly elsewhere in this script (keep it if still used — likely yes for the portal entry call above). Status writing (`_spawn_core.write_initial_status`) stays unchanged in this batch — moving it to the worktree is batch 03's job. Tests in `test-millpy-spawn.py`: this file is mock-based (it patches `Path.exists`, `Path.mkdir`, `_junction`, `_wiki.read_junctions`); extend it ONLY with call-order verification — assert `_setup.create_hub_links` is called AFTER the portal `_junction.create` and after the `mkdir` of `<container>/portals/`. After this card, `millpy-spawn.py` imports `_setup` at module level; the `_run_main_with_mocks` stub map MUST add a `_setup` entry (with `create_hub_links` mocked to return an empty `{"junctions": [], "hardlinks": []}` dict by default) so the import-time mock satisfies the new dependency. Similarly, the `_paths` mock in the stub map MUST expose `resolve_container_path` returning a concrete `Path` from the test fixture so the call-order assertions can compare against a real value. Real-disk assertions (portal entry resolves to the new worktree path, `tasks.md` hardlink inode matches `wiki/Home.md`, `.others` and `.active` junctions exist) live in `test-setup-hub-links.py` (Card 6) where the fixture uses real `tempfile.TemporaryDirectory()` and exercises the real filesystem; add those assertions to Card 6's test list, not here.
- **Commit:** `feat(spawn): unify junction/hardlink creation through _setup.create_hub_links + portal`

### Card 9: `millpy-claim.py` portal creation + `recreate_active_junction` callsite

- **Reads:**
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
- **Creates:** none
- **Requirements:** Update the `_spawn_core.recreate_active_junction(...)` callsite (currently `wiki_path, slug, mill_dir`) to the new signature `(slug, mill_dir, container_path)`. Compute `container_path` via the new `_paths.resolve_container_path(git_root)` helper from Card 4 — NOT `git_root.parent` and NOT `resolve_main_worktree_root(git_root).parent` (both return `<container>/wts/` after migration, which would land the portal entry under `<container>/wts/portals/<slug>` instead of `<container>/portals/<slug>`). Order of operations (CRITICAL — must be BEFORE `recreate_active_junction`, not after): (1) Ensure `container_path / "portals"` exists via `Path.mkdir(parents=True, exist_ok=True)`. (2) Idempotent portal-entry handling: if `<container>/portals/<slug>` does not exist, `_junction.create(target=<current worktree main_root>, link_path=container_path / "portals" / slug)`. If it already exists AND `Path.resolve()` (or equivalent) confirms it points at the current main_root, skip. If it exists but points elsewhere, `_junction.remove` then `_junction.create`. (3) ONLY THEN call `recreate_active_junction(slug, mill_dir, container_path)`. The "BEFORE" order is required because `recreate_active_junction` does `target.mkdir(parents=True, exist_ok=True)` on `container_path / "portals" / slug` before creating `.active`; if portal-entry creation runs AFTER, that mkdir creates a real directory at `portals/<slug>`, then the portal-entry step's existence check finds a directory and the "exists but points elsewhere" branch tries `_junction.remove`, which raises `ValueError("not a junction or symlink — refusing to remove")`. The operation becomes unrecoverable without manual cleanup. Use `_junction.create`/`_junction.remove` for the operations; do NOT introduce a new helper for "idempotent junction" — inline the three-state check. The current main_root for in-place mill-claim equals `_paths.resolve_main_worktree_root(git_root)`. Extend `test-millpy-claim.py` to verify (a) portal entry creation lands under `container_path / "portals"`, NOT under `git_root.parent / "portals"` — assert the call uses `_paths.resolve_container_path`'s output; (b) idempotent re-claim (re-running claim on the same slug doesn't error and is a no-op); (c) the new `recreate_active_junction` call signature; (d) call ORDER (portal entry created before `recreate_active_junction`). The `_make_stub_map` (or equivalent) in this test file MUST add `resolve_container_path` to the `_paths` mock, returning a concrete `Path` from the test fixture (e.g. `tempfile.TemporaryDirectory()`-based container path) so `container_path / "portals"` produces a real Path object that the call-order assertions can compare against — without this, the expression would yield a `MagicMock` and the comparisons would fail spuriously.
- **Commit:** `feat(claim): add portal entry creation; update recreate_active_junction sig`

### Card 10: `wiki/config.yaml` `junctions:` block update

- **Reads:**
  - `wiki/config.yaml`
  - `wiki/active/container-restructure/discussion.md`
- **Modifies:**
  - `wiki/config.yaml`
- **Creates:** none
- **Requirements:** Update the `junctions:` block to the final shape from discussion.md `## Technical context → wiki/config.yaml changes`. Specifically: keep `.millhouse/wiki: <WIKI_PATH>` unchanged; add `.others: <CONTAINER_PATH>/portals/`; change `.active` from `<WIKI_PATH>/active/<SLUG>/` to `<CONTAINER_PATH>/portals/<SLUG>/`. Other config blocks (`repo:`, `spawn:`, `paths:`, `llm:`, `implementers:`, `pipeline:`, `review:`, `notify:`, `groom:`, `hardlinks:`) are NOT touched in this card — `paths:` moves in batch 03 (Card 14). Update the header comment on the `junctions:` section to mention `.others` and the portal-based `.active` target. Commit goes to the wiki repo (separate from the source-repo commits in batches 01–05). Use `_wiki.write_commit_push` from a Python invocation; do NOT manually edit and `git add` since the wiki commit conventions live in that helper. Commit message must mention that the new `.others` and retargeted `.active` are consumed by `_setup.create_hub_links` from the same task.
- **Commit:** `chore(wiki-config): add .others junction; retarget .active to portals/<SLUG>/`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` — every test passes including the new `test-setup-hub-links.py` and the extended `test-millpy-spawn.py`/`test-millpy-claim.py`. Manual smoke-check is appropriate here but not required for the gate: spawn a throwaway worktree against the live wiki/config.yaml and verify the portal entry, `.others`, and `tasks.md` hardlink all materialise. The card writes the wiki/config.yaml change in the same batch as the consumers, so a re-spawn between Card 8 and Card 10 would produce a worktree without `.others` (consistent with the old config still in place) — implementer is expected to land the cards in numerical order to avoid this transient state.
