# Batch: millpy-spawn-v2-elimination

```yaml
task: "Finish V3 wiki adoption — complete batch 3 port and test sweep"
batch: millpy-spawn-v2-elimination
number: 3
cards: 1
verify: "PYTHONPATH= uv run --project plugins/mill python -c \"import sys, importlib.util; sys.path.insert(0, 'plugins/mill/scripts'); spec = importlib.util.spec_from_file_location('m', 'plugins/mill/scripts/millpy-spawn.py'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); print('ok')\""
depends-on: [2]
```

## Batch Scope

Port `plugins/mill/scripts/millpy-spawn.py` to V3 — drop the V2 imports, drop the legacy `wiki/config.yaml` fallback branch in `_load_config`, replace `_wiki.sync_pull` + `_tasks_md.parse(home_text)` with `wiki.list_tasks_brief(wiki_path)`, and propagate the new dict shape through every Task-attribute consumer in this file.

Depends on batch 2 because `millpy-spawn.py` calls `_spawn_core.multi_select_groom_then_claim`, which returns `dict` (not `_tasks_md.Task`) after batch 2 lands. The dict consumers in this file MUST be updated in lockstep, otherwise runtime `AttributeError` on `.slug`/`.title`/etc.

Single M-effort card. The diff is mechanical but spans the full file because consumers of the picker's return value are scattered.

Batch-local decisions (differ from `## Shared Decisions` in `00-overview.md`):

- **`wiki_path` is already in scope.** Every call site that previously fed `_wiki.sync_pull(wiki_path, ...)` or built `wiki_cfg = resolve_wiki_path(repo_root) / "config.yaml"` resolves `wiki_path` via `resolve_wiki_path(repo_root)`. Reuse the existing local; do not re-resolve.

## Cards

### Card 5: Port `millpy-spawn.py` to V3 wiki API

- **Effort:** M
- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Eliminate every V2 reference from `plugins/mill/scripts/millpy-spawn.py`. Apply the following changes; line numbers are from the current state on `hanf/wiki-v3-batch3-finish` HEAD.

  **Imports (lines 44, 46):**
  - Delete `import _tasks_md` (line 44).
  - Delete `import _wiki` (line 46).
  - Add `import wiki` in the absolute-imports block alongside `_junction`, `_setup`, `_spawn_core`, etc. (alphabetical position acceptable).

  **`_load_config` config-guard (function defined around lines 53-72; the wiki/config.yaml branch is at lines 66-72):**

  Drop the `wiki_cfg = resolve_wiki_path(repo_root) / "config.yaml"` branch and any reference to `wiki_cfg` in the guard. The guard now checks only `mill_cfg.exists()`. On missing, raise the existing `SystemExit` with a message that references only `mill-config.yaml` — no mention of `wiki/config.yaml`. Concretely, replace the existing block (the `try: wiki_cfg = ...; except SystemExit: wiki_cfg = None` ... `if not mill_cfg.exists() and (wiki_cfg is None or not wiki_cfg.exists()):` shape) with:

  ```python
  mill_cfg = repo_root / "mill-config.yaml"
  if not mill_cfg.exists():
      raise SystemExit(f"Missing config: {mill_cfg}")
  return _load_config_lenient(repo_root, worktree_root)
  ```

  Keep the function name, signature (`_load_config(repo_root, worktree_root)`), and the trailing `return _load_config_lenient(...)` call identical to the current code. Only the missing-config guard changes.

  **`_wiki.sync_pull` call (line 128):**

  Delete the line `_wiki.sync_pull(wiki_path, slug="mill-spawn")`. The V3 daemon lazy-refreshes inside every op; no explicit pull needed.

  **`_tasks_md.parse(home_text)` call (line 130):**

  Replace the V2 parse with V3 list. The exact pre-replacement shape is roughly:

  ```python
  home_text = (wiki_path / "Home.md").read_text(encoding="utf-8")
  tasks = _tasks_md.parse(home_text)
  ```

  Replace with:

  ```python
  tasks = wiki.list_tasks_brief(wiki_path)
  ```

  Delete the `home_text = (wiki_path / "Home.md").read_text(...)` assignment that fed it. If the local was referenced elsewhere in the function (other than `_tasks_md.parse`), leave the assignment; grep `home_text` to confirm.

  **`_spawn_core` return-shape propagation:**

  `millpy-spawn.py` calls `_spawn_core.pick_task_single`, `_spawn_core.multi_select_groom_then_claim`, and/or related pickers. Per batch 2 (card 4), these now return `dict` / `list[dict]` instead of `_tasks_md.Task`. Every site in `millpy-spawn.py` that consumes the return value and accesses attributes (`.slug`, `.title`, `.brief`, `.group`, `.status`, `.phase`, `.has_proposal`) MUST be updated to dict-key access (`picked["slug"]`, `picked["title"]`, etc.). Field-rename note: `phase` → `status`.

  Grep the file end-to-end for these access patterns AFTER all other edits:

  ```bash
  grep -nE "\b(t|task|entry|picked|chosen|cand)\.(slug|title|phase|has_proposal|heading_line_no|brief|group|status)\b" plugins/mill/scripts/millpy-spawn.py
  ```

  Zero matches required. Specifically, also check the `tasks` list iteration around the picker call site (line 130-180 region today) — that loop's iteration variable was `_tasks_md.Task`-typed and is now `dict`-typed.

  **`heading_line_no`:** if any error message references the now-dropped `heading_line_no` field, rewrite to be slug-only — see batch 2 / card 4's identical treatment.

  **`_load_config` callers' inner lookup:** the `_load_config_lenient` call already returns the deep-merged config; no other change needed.

  **Final verification (do inside the implementer's edit loop, before committing):**

  Run these greps; each MUST return zero matches:

  ```bash
  grep -nE "^import _(wiki|tasks_md|sidebar)|^from _(wiki|tasks_md|sidebar) " plugins/mill/scripts/millpy-spawn.py
  grep -nE "_(wiki|tasks_md|sidebar)\." plugins/mill/scripts/millpy-spawn.py
  grep -nE "wiki/config\.yaml" plugins/mill/scripts/millpy-spawn.py
  grep -nE "\.heading_line_no\b" plugins/mill/scripts/millpy-spawn.py
  ```

  Then run the verify gate:

  ```bash
  PYTHONPATH= uv run --project plugins/mill python -c "import sys, importlib.util; sys.path.insert(0, 'plugins/mill/scripts'); spec = importlib.util.spec_from_file_location('m', 'plugins/mill/scripts/millpy-spawn.py'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); print('ok')"
  ```

  Expected output: `ok` and exit code 0. If the import errors (most likely `ModuleNotFoundError: _tasks_md` or `ModuleNotFoundError: _wiki`), an import line was missed.

  Do NOT run `test-millpy-spawn.py` as the verify gate for this card. That test file has its own V2 references (line 970: `import _tasks_md as real_tasks_md`) inside one test method (`test_spawn_discovery_round_trip_subfolder`) which still fails until card 10 in batch 6. The smoke-import command above is the only reliable per-card gate.
- **Commit:** `refactor(millpy-spawn): port to wiki.list_tasks_brief; drop wiki/config.yaml fallback`

## Batch Tests

The batch verify is the import-smoke command above. `millpy-spawn.py` is the entry point of a CLI; the smoke-import proves it loads cleanly with the V3 wiki API and no V2 stubs. Behavioural tests live in `test-millpy-spawn.py`, but that file still has V2 fixture references at line 970 inside one test method — addressed by card 10 in batch 6. After batch 6 lands, `test-millpy-spawn.py` will go fully green.

Side-effect: any chain-failure test that imports through `millpy-spawn` (e.g. some indirect importers) also goes green after this batch. Spot-check via `run-all.py` but do not gate on it.
