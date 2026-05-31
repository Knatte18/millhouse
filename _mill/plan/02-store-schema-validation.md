# Batch: Store Schema and Validation

```yaml
task: Replace manual layer letters with depends_on + isolated flags
batch: Store Schema and Validation
number: 2
cards: 7
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-store.py
depends-on: []
```

## Batch Scope

Rewrite `wiki/_store.py` to adopt the new task schema (`depends_on`, `isolated`, `deferred` replacing `group`), add a private `_validate_write` helper that enforces all DAG invariants, wire it into every write path, update `list_tasks_brief` to return the raw new fields (no derived `layer`), and add `set_deps` and `migrate_group_to_deps` methods. This batch is independent of batch 1 — `_store.py` raises plain `ValueError` and does not import from `wiki/__init__`.

TDD order: write Card 4 (tests) first; implement Cards 5–10 to make them pass.

## Cards

### Card 4: Write test-wiki-store.py additions (TDD)

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-store.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add the following test cases to `test-wiki-store.py` (write before implementing Cards 5–10; run verify to confirm they fail, then implement to make them pass). **Also update existing test 9** (the `list_tasks_brief` key-set assertion): replace the expected set `{"id", "slug", "title", "group", "brief", "status", "has_proposal"}` with `{"id", "slug", "title", "depends_on", "isolated", "deferred", "brief", "status", "has_proposal"}`; test 9 is the in-place replacement, do not add a separate new case. New test cases: (a) **New-field defaults**: `upsert_task` with no extra fields creates a record with `depends_on == []`, `isolated == False`, `deferred == False`, no `group` key. (b) **Validation — dangling dep**: `upsert_task({"slug": "a", "depends_on": ["nonexistent"]})` raises `ValueError`; store is unchanged. (c) **Validation — cycle**: create tasks A and B; `upsert_task({"slug": "B", "depends_on": ["A"]})` succeeds; `upsert_task({"slug": "A", "depends_on": ["B"]})` raises `ValueError` with a message that mentions both slugs. (d) **Validation — target-isolated**: insert `{"slug": "iso", "isolated": True}`; `upsert_task({"slug": "x", "depends_on": ["iso"]})` raises `ValueError`. (e) **Validation — target-deferred**: insert `{"slug": "def", "deferred": True}`; `upsert_task({"slug": "x", "depends_on": ["def"]})` raises `ValueError`. (f) **Validation — reverse-isolate**: insert tasks A and B with B depending on A; `upsert_task({"slug": "A", "isolated": True})` raises `ValueError` naming B. (g) **Validation — reverse-defer**: insert tasks A (not deferred) and B (not deferred) with B depending on A; `upsert_task({"slug": "A", "deferred": True})` raises `ValueError` naming B. (h) **Validation — type errors**: `depends_on` not a list raises `ValueError`; `isolated` not a bool raises `ValueError`; `deferred` not a bool raises `ValueError`; stray `group` key in upsert raises `ValueError`. (i) **No mutation on invalid input**: insert two tasks; attempt an invalid upsert (dangling dep); assert both original tasks still exist. (j) **set_deps happy path**: insert tasks A and B; call `store.set_deps("A", ["B"])`; re-read A and assert `depends_on == ["B"]`. (k) **set_deps validation**: call `set_deps("A", ["nonexistent"])` raises `ValueError`; store unchanged. (l) **Batch projection — intra-batch dep succeeds**: `upsert_tasks_batch([{"slug": "X"}, {"slug": "Y", "depends_on": ["X"]}])` succeeds (Y depends on X, both new in same call). (m) **Batch projection — internal cycle rejected**: `upsert_tasks_batch([{"slug": "P", "depends_on": ["Q"]}, {"slug": "Q", "depends_on": ["P"]}])` raises `ValueError`; neither P nor Q is written. (n) **migrate_group_to_deps — Z becomes isolated**: use `store._db.insert({"id": 0, "slug": "z-task", "title": "", "group": "Z", "brief": "", "body": "", "status": None})` directly to bypass `upsert_task` validation (which rejects `group` keys after Card 7); call `migrate_group_to_deps()`; re-read and assert `isolated == True`, `depends_on == []`, `deferred == False`, `"group"` key absent, `id` and `slug` preserved. (o) **migrate_group_to_deps — non-Z becomes not-isolated**: use `store._db.insert({"id": 0, "slug": "a-task", "title": "", "group": "A", "brief": "", "body": "", "status": None})` directly; migrate; assert `isolated == False`. (p) **migrate_group_to_deps — idempotent**: insert a record with `group` directly via `_db.insert`; run migration twice; assert records unchanged after second run. (q) **migrate_group_to_deps — preserves doc_id and id**: insert a record with `group` via `_db.insert`, note the `doc_id` and `id`; after migration, assert both are unchanged.
- **Commit:** `test(store): comprehensive test-wiki-store additions for new schema and validation`

### Card 5: Replace group defaults with new schema fields in all write methods

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/_store.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `Store.upsert_task`, `Store.upsert_tasks_batch`, and `Store.merge_tasks`, replace the `"group": None` key in the `new_task` default dict with `"depends_on": [], "isolated": False, "deferred": False`. The `id`, `slug`, `brief`, `body`, `status` defaults remain. Any incoming task payload that contains a `group` key will later be rejected by `_validate_write` (Card 6).
- **Commit:** `feat(store): replace group default with depends_on/isolated/deferred`

### Card 6: Add _validate_write private method

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/_store.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `Store._validate_write(self, tasks_snapshot: list[dict], incoming: dict) -> None`. `tasks_snapshot` is the projected full task set (store state after any removals, merged with all incoming records for the current operation). `incoming` is the single record being validated. Raise `ValueError` with an ASCII error string on any of these conditions: (a) **type**: `depends_on` is not a `list` where every element is a `str`; `isolated` or `deferred` is not a `bool`; a `"group"` key is present in `incoming`. (b) **dangling**: any slug in `incoming["depends_on"]` does not appear in the slug set of `tasks_snapshot`. (c) **cycle**: adding `incoming` would form a cycle; detect by DFS from each dep slug using `tasks_snapshot` after merging `incoming`; include the cycle path in the error string (ASCII, slugs joined with ` -> `). (d) **target-not-schedulable**: any slug in `incoming["depends_on"]` refers to a task in `tasks_snapshot` whose `isolated` or `deferred` is `True`. (e) **reverse-isolate**: `incoming.get("isolated") is True` and some other task in `tasks_snapshot` has the incoming slug in its `depends_on`; error names the dependent slugs. (f) **reverse-defer**: `incoming.get("deferred") is True` and some other *non-deferred* task in `tasks_snapshot` depends on the incoming slug; error names the dependent slugs. All field reads use `.get()` with defaults (`depends_on` → `[]`, `isolated` → `False`, `deferred` → `False`).
- **Commit:** `feat(store): add _validate_write with DAG invariant checks`

### Card 7: Wire _validate_write into all write paths

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/_store.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Call `self._validate_write(snapshot, incoming)` before any mutation in each write path. (a) **`upsert_task`**: snapshot = `self._db.all()` merged with `[task]` (replace any existing record with the same slug). Validate before any DB write. (b) **`upsert_tasks_batch`**: build the full projected snapshot first (current store records merged with all incoming records, by slug); then validate each incoming record against that snapshot. On any failure raise immediately; nothing is written. (c) **`merge_tasks`**: build projected snapshot = `[t for t in self._db.all() if t['slug'] not in set(remove_slugs)]` merged with `upsert`, WITHOUT any prior DB mutation. Validate against this snapshot. On success, perform removals then insert. The existing `ValueError` guard on empty `upsert["slug"]` stays; the new validation runs after it.
- **Commit:** `feat(store): wire _validate_write into upsert_task, upsert_tasks_batch, merge_tasks`

### Card 8: Update list_tasks_brief to return raw new fields

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/_store.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `Store.list_tasks_brief`, replace the returned dict shape from `{id, slug, title, group, brief, status, has_proposal}` to `{id, slug, title, depends_on, isolated, deferred, brief, status, has_proposal}`. Use `doc.get("depends_on", [])`, `doc.get("isolated", False)`, `doc.get("deferred", False)`. Drop `group`. Do not add `layer` here; the server enriches that (batch 4, Card 19).
- **Commit:** `feat(store): list_tasks_brief returns raw depends_on/isolated/deferred (drops group)`

### Card 9: Add Store.set_deps

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/_store.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `Store.set_deps(self, slug: str, depends_on: list[str]) -> None`. Look up the task by slug; if not found, raise `ValueError(f"task not found: {slug!r}")`. Build `incoming = {**existing_task_dict, "depends_on": depends_on}`. Build snapshot = `self._db.all()` with the updated record merged in (the updated record replaces the existing one). Call `self._validate_write(snapshot, incoming)`. On success, call `self._db.update({"depends_on": depends_on}, Query().slug == slug)`.
- **Commit:** `feat(store): add Store.set_deps`

### Card 10: Add Store.migrate_group_to_deps

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/_store.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `Store.migrate_group_to_deps(self) -> None`. Iterate over all records in the store. For records that have a `"group"` key: (a) call `self._db.update(tinydb.operations.delete("group"), doc_ids=[doc.doc_id])` to drop the key while preserving `doc_id` and `id`; (b) call `self._db.update({"depends_on": [], "isolated": doc.get("group") == "Z", "deferred": False}, doc_ids=[doc.doc_id])`. Records already lacking `"group"` are skipped (idempotent). The `id` field is never recomputed; `doc_id` is never changed. Import `tinydb.operations` at the top of the file.
- **Commit:** `feat(store): add Store.migrate_group_to_deps`

## Batch Tests

`test-wiki-store.py` covers all new behavior: schema defaults, validation rules, list_tasks_brief key set, set_deps, migrate_group_to_deps. The test file uses `tempfile.mkdtemp()` / `_safe_rmtree` fixtures and no daemon or git; all tests are in-process and fast.
