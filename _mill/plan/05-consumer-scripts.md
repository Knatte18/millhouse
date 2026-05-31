# Batch: Consumer Scripts

```yaml
task: Replace manual layer letters with depends_on + isolated flags
batch: Consumer Scripts
number: 5
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-spawn-core.py test-millpy-spawn.py
depends-on: [4]
```

## Batch Scope

Create the `millpy-wiki-migrate-deps.py` runner and update the three consumer scripts (`_spawn_core.py`, `millpy-status.py`, `millpy-inspect.py`) to route task lists through `render_order` and format titles via `extended_title`, so every operator-facing task list matches Home.md ordering and titles. Update the existing spawn and status test fixtures from the old `group`-based schema to the new schema.

## Cards

### Card 22: Create millpy-wiki-migrate-deps.py runner

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-wiki-migrate-deps.py`
- **Deletes:** none
- **Requirements:** Create a thin CLI script. Resolve `git_root` via `_paths.resolve_git_root()`. Resolve `wiki_path` via `_paths.resolve_wiki_path(git_root)`. Call `wiki.migrate_deps(wiki_path)` (where `wiki` is `wiki._client`). Print `"Migration complete."` to stdout. Exit 0 on success. The script must be idempotent (running it twice is safe because `Store.migrate_group_to_deps` is idempotent). No argument parsing required. Add the standard `if __name__ == "__main__": sys.exit(main())` entry point.
- **Commit:** `feat: add millpy-wiki-migrate-deps.py runner`

### Card 23: _spawn_core.py: use render_order and extended_title in pickers

- **Context:**
  - `plugins/mill/scripts/wiki/_render.py`
- **Edits:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Import `extended_title` and `render_order` from `wiki._render` at the top of `_spawn_core.py`. In `pick_task_single`: apply `render_order(unmarked)` before passing to `_prompt_numbered` (replace `_prompt_numbered(unmarked)` with `_prompt_numbered(render_order(unmarked))`). In `pick_task_single_or_multi`: apply the same `render_order` wrap to the `unmarked` list before passing to `_prompt_numbered_multi`. In `_prompt_numbered`: replace `t["title"]` with `extended_title(t)` in the `print(f"  {i}) ...")` line. In `_prompt_numbered_multi`: same replacement. These changes ensure the interactive picker presents tasks in the same layer order as Home.md and with the same title format (including `[A]`/`[Z]` suffixes). `compute_layers` is called with `.get()` defaults so existing test fixtures that lack the new fields continue to work (missing fields default to `[]`/`False`/`False`).
- **Commit:** `feat(spawn): use render_order and extended_title in interactive pickers`

### Card 24: millpy-status.py: use extended_title for title display

- **Context:**
  - `plugins/mill/scripts/wiki/_render.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-status.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_build_rows`, add a `layer` field to each row: when `slug in home_tasks`, set `layer = home_tasks[slug].get("layer")`, otherwise `layer = None`. Add `"layer": layer` to each `rows.append({...})` dict. In `_render_table`, update the TITLE column to show the layer suffix: replace the plain `title` cell value with `f"{title} [{layer}]"` when `layer` is set and `layer` is not `"__deferred__"` and `layer` is not `"__done__"`. When `layer` is `None`, `"__deferred__"`, or `"__done__"`, show the plain `title`. Add `"layer"` as a valid `--sort` choice: `parser.add_argument("--sort", choices=["slug", "phase", "layer"], default="slug")`. When `sort_by == "layer"`, sort rows by `render_order` key order: define a helper `_layer_sort_key(row)` that maps `layer` to a tuple `(bucket_index, row["id"])` using the canonical order `A < B < ... < Y < Z < __deferred__ < __done__ < None`.
- **Commit:** `feat(status): display layer suffix in TITLE column, add --sort layer option`

### Card 25: millpy-inspect.py: add home_layer to output

- **Context:**
  - `plugins/mill/scripts/wiki/_render.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-inspect.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_collect`, build `home_layer_map = {t["slug"]: t.get("layer") for t in home_tasks_list}` alongside the existing `home_marker_map`. Add `"home_layer": home_layer_map.get(slug)` to each `records.append(...)` dict. In `_render_markdown`, add a `home_layer: <value>` line immediately after the `home_marker:` line, only when `rec.get("home_layer")` is set. In `_render_json`, include `"home_layer": rec["home_layer"]` in the per-slug output dict.
- **Commit:** `feat(inspect): include home_layer in task output`

### Card 26: Update test fixtures and add new consumer tests

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/wiki/_render.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
  - `plugins/mill/unit_tests/test-spawn-core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-millpy-spawn.py`: update `_make_fake_task` to remove `"group": None` and add `"depends_on": [], "isolated": False, "deferred": False, "layer": "A"`. Scan the rest of the file for any `t["group"]` or `task["group"]` references and replace with the new fields. In `test-spawn-core.py`: the existing tests use `parse_home_md` to create task dicts; those tests continue working as-is because `compute_layers` defaults missing fields. Add two new test cases: (a) **Picker order matches render_order**: create three tasks with layers A, B, Z (by setting `depends_on` and `isolated` appropriately); inject them via stdin mock into `pick_task_single`; assert that `_prompt_numbered` was called with the tasks in A→B→Z order (verify by capturing stderr output using `io.StringIO` and checking the printed order). (b) **Picker title uses extended_title**: create a task with `layer="B"` and `title="Fix bug"`; inject via stdin mock; assert stderr output contains `"Fix bug [B]"`.
- **Commit:** `test(spawn): update fixtures to new schema, add render_order/extended_title picker tests`

## Batch Tests

`test-spawn-core.py` covers `pick_task_single`/`pick_task_single_or_multi` behavior with updated fixtures and two new tests verifying render_order sorting and extended_title display in the picker. `test-millpy-spawn.py` verifies the spawn entry-point integration with the updated `_make_fake_task` fixture. The consumer changes to `millpy-status.py` and `millpy-inspect.py` have no dedicated unit test file; their correctness is verified by visual inspection of the `--sort layer` output and the `home_layer` field in inspect output. If a `test-millpy-status.py` or `test-millpy-inspect.py` is added later, it should assert the layer suffix format.
