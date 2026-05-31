# Batch: Render compute_layers and Helpers

```yaml
task: Replace manual layer letters with depends_on + isolated flags
batch: Render compute_layers and Helpers
number: 3
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-render.py
depends-on: []
```

## Batch Scope

Rewrite `wiki/_render.py` to replace `group`-based bucketing with a `compute_layers` helper that derives letter assignments from the DAG, add `extended_title` and `render_order` helpers, and update `render()` to emit the new Home.md format (Someday section, Depends-on lines, no Unspecified section, corrected letter suffix behavior). This batch is fully independent — `_render.py` imports nothing from `wiki/__init__` or `wiki/_store`.

TDD order: write Card 11 (tests) first; implement Cards 12–14 to make them pass.

## Cards

### Card 11: Write test-wiki-render.py additions (TDD)

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-render.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add the following test cases to `test-wiki-render.py` (write before implementing Cards 12–14): (a) **Topo levels A/B/C**: three tasks where C depends on B depends on A; assert compute_layers returns A="A", B="B", C="C". (b) **Done-dep promotion**: task A (done) and task B with `depends_on: ["A"]`; assert B gets "A" (not "B") because A is filtered from effective deps. (c) **Isolated → Z**: task with `isolated: True` gets "Z". (d) **Deferred → __deferred__**: task with `deferred: True` gets "__deferred__". (e) **Precedence done>deferred>isolated>topo**: task with `status=="done"` AND `deferred==True` gets "__done__". Task with `deferred==True` AND `isolated==True` gets "__deferred__". (f) **A..Y cap overflow raises**: chain of 26 tasks each depending on the previous; assert compute_layers raises `ValueError`. (g) **Cycle raises**: two tasks each depending on the other; assert compute_layers raises `ValueError` with both slugs in the message. (h) **Dangling dep tolerated by compute_layers**: task with `depends_on: ["missing"]`; assert compute_layers returns "A" (treats missing target as done). (i) **render() dangling dep display**: task with `depends_on: ["missing"]` produces a `Depends on:` line containing `#???: missing (missing)`. (j) **Render order A..Z→Someday→Done**: build tasks covering letter, deferred, done; assert their section headers appear in that order in Home.md. (k) **# Unspecified not emitted**: render tasks with no group field; assert `# Unspecified` is absent from Home.md. (l) **Depends-on line shows numbers**: task B with `depends_on: ["A"]`; assert Home.md contains a line matching `Depends on: #` with A's id number. (m) **Depends-on line omitted when empty**: task with `depends_on: []`; assert no `Depends on:` line in Home.md. (n) **All-deps-done: Depends-on line still shown**: task B with `depends_on: ["A"]`, A has `status=="done"`; B is in layer A (promoted) but its Depends-on line still shows A's number. (o) **Done/deferred no letter suffix**: done task heading has no `[A]` or `[Z]` bracket; deferred task heading has no bracket. Active/isolated tasks have `[letter]` bracket. (p) **extended_title isolation**: call `extended_title` directly on a task dict with `layer="B"`; assert return is `"Title [B]"`. Call on a done task; assert no suffix. Call on a deferred task; assert no suffix. (q) **render_order isolation**: tasks with layers A, Z, deferred, done; assert render_order returns them in that canonical order. (r) **Byte-identical double-render**: call `render(tasks)` twice with identical input; assert both calls return equal dicts. Update the following existing test cases to use the new task schema: **Test 2** ("alphabetic group order then None last"): replace `group: "A"/"B"/"C"/None` task dicts with `depends_on`-based dicts that produce A/B/C topo levels (e.g., C depends on B depends on A); drop the `ungrouped` task (no-deps task is now layer A); update assertions to check `# Layer A` then `# Layer B` then `# Layer C` in order; remove the old "None last" part. **Test 3** ("empty groups are skipped"): replace `group`-based dicts; new premise — create two tasks: X (no deps → layer A) and Y (`depends_on: ["X"]` → layer B); assert `# Layer A` and `# Layer B` both appear; assert `# Layer C` does NOT appear (only layers with tasks are emitted). This replaces the old `assert b_pos == -1` with `assert c_pos == -1` to verify empty-section skipping. **Test 4** ("accept any letter A-Z"): replace `group: "M"` / `group: "Q"` with long dep chains producing M-level (13 hops) and Q-level (17 hops) tasks to verify any letter works; replace `group: "Z"` with `isolated: True`; update assertions to check `# Layer M`, `# Layer Q`, `# Layer Z`. **Test 8** ("proposal file generated for non-empty body"): the task has no deps (layer A), so its sidebar entry becomes `"- [**#000:** Has Proposal [A]](proposal-with-body.md)"` — update the existing sidebar assertion to include the `[A]` suffix. **Test 12** ("byte-identical double render"): replace `group: "B"`, `group: "A"` with `depends_on`-based tasks; keep the byte-identity assertion unchanged. **Test 13** ("done tasks bucketed under # Done after Unspecified"): replace `group: "A"` with `depends_on: []`, `group: "Z"` with `isolated: True`, `group: None` with `depends_on: []`; remove the `assert unspecified != -1` assertion and the `assert layer_a < unspecified < done_header` ordering check; add assertion that `# Unspecified` is absent; add assertion that `# Layer A` appears before `# Done`; keep the assertion that done tasks are under `# Done`.
- **Commit:** `test(render): comprehensive test-wiki-render additions for compute_layers and new format`

### Card 12: Add compute_layers

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/_render.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `compute_layers(tasks: list[dict]) -> dict[str, str]` at the top of `_render.py`. The function maps each task's slug to its bucket label. All field reads use `.get()` with defaults (`depends_on` → `[]`, `isolated` → `False`, `deferred` → `False`, `status` → `None`). Bucket assignment precedence (evaluated in order, first match wins): (1) `status == "done"` → `"__done__"`; (2) `deferred == True` → `"__deferred__"`; (3) `isolated == True` → `"Z"`; (4) topo level: `effective_deps = [d for d in depends_on if the task d exists in the task map AND its computed bucket is not "__done__"]`. A task with no effective deps → level 0 → `"A"`. A task with effective deps → level = `1 + max(level of each effective dep)`. Map level to letter: 0→A, 1→B, ..., 24→Y. If any topo task computes to level 25 or higher, raise `ValueError("layer depth exceeds A..Y cap")`. Cycle detection: before computing topo, verify the effective-dep subgraph is acyclic using DFS with three-color marking (white/gray/black); if a back edge is found, raise `ValueError("cycle detected: <path>")` where `<path>` is the slug chain joined with ` -> ` (ASCII). A slug in `depends_on` that does not exist in the task map is treated as if the target is done (i.e., filtered from effective_deps) so `compute_layers` is tolerant of dangling edges (the dangling display is handled in `render()`). Topo computation is done via a recursive or iterative topological level scan over only the non-done, non-deferred, non-isolated tasks.
- **Commit:** `feat(render): add compute_layers with topo algorithm, cycle/cap detection`

### Card 13: Add extended_title and render_order

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/_render.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `extended_title(task: dict) -> str`. Returns the task's display title with a layer suffix for active/isolated tasks and no suffix for deferred/done tasks. Algorithm: `title = task.get("title", "")`. If `task.get("status") == "done"` or `task.get("deferred", False)`, return `title` (no suffix). Otherwise read `layer = task.get("layer")` — the pre-computed layer key that `_server._handle_list_tasks_brief` merges in (see batch 4, Card 19). If `layer` is set and not `"__deferred__"` and not `"__done__"`, return `f"{title} [{layer}]"`. Otherwise return `title`. Add `render_order(tasks: list[dict]) -> list[dict]`. Calls `compute_layers(tasks)` and sorts the tasks list by canonical bucket order: `"A"` < `"B"` < ... < `"Y"` < `"Z"` < `"__deferred__"` < `"__done__"`. Within each bucket, sort by `task.get("id", 0)` ascending. Returns a new sorted list.
- **Commit:** `feat(render): add extended_title and render_order helpers`

### Card 14: Rewrite render() using new helpers

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/_render.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Rewrite `render(tasks: list[dict]) -> dict[str, str]`. Call `compute_layers(tasks)` to get the bucket map. Build `id_map = {t["slug"]: t.get("id") for t in tasks}` for slug→id resolution in Depends-on lines. Bucket order: letter buckets `A..Z` (sorted), then `__deferred__`, then `__done__`. Within each bucket, sort tasks by `id` ascending. For each bucket, emit the section header: `"# Layer X"` for letter buckets, `"# Someday"` for `__deferred__`, `"# Done"` for `__done__`. Drop the `# Unspecified` branch entirely — `compute_layers` assigns every active task to a letter, so there is no null-group bucket. For each task, format the title heading as follows: tasks in letter buckets include `[bucket]` suffix in the heading (e.g., `**#007:** My Task [A]`); tasks in `__deferred__` and `__done__` have NO bracket suffix (the section header is the classifier). The `[slug](proposal-...)` line and `[status]` marker format is unchanged. After the `[slug]` line, if `task.get("depends_on", [])` is non-empty (raw stored list, NOT done-filtered), emit a `Depends on: #NNN, #MMM` line where each slug is translated to `#<id:03d>` using `id_map`, or `#???: <slug> (missing)` if not found. This line appears directly under the slug line, before the brief. The brief block is unchanged. Keep the `status == "s"` drop-to-None normalization. Keep the proposal file generation and sidebar generation logic unchanged in structure (bucket sections map to sidebar groups). Keep the byte-identical double-render property: calling `render(tasks)` twice with the same input must produce identical output.
- **Commit:** `feat(render): rewrite render() with compute_layers, Someday section, Depends-on lines`

## Batch Tests

`test-wiki-render.py` covers the full new render pipeline: compute_layers algorithm, render_order, extended_title, and the updated render() output format. All tests use pure in-memory task dicts — no TinyDB, no git.
