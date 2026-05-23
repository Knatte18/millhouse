# Discussion: Migrate wiki task store to TinyDB

```yaml
task: Migrate wiki task store to TinyDB
slug: wiki-tinydb
status: discussing
parent: main
```

## Problem

`wiki/_store.py` is currently a plain in-memory dict mapping file paths to `(content, hash)` tuples. It has no concept of tasks — it is a generic content cache. This means the daemon has no structured understanding of what it is caching: tasks are opaque markdown blobs, and all task manipulation requires re-parsing markdown on every operation.

The goal is to replace this in-memory cache with TinyDB (a lightweight JSON document store), making tasks the first-class entity inside the daemon. `tasks.json` lives in the wiki repo and becomes the canonical task store. `Home.md` and `_Sidebar.md` become generated artifacts rendered from TinyDB after each mutation.

This task touches only the `wiki/` daemon module (`_store.py`, `_server.py`, and rendering logic). The old `_wiki.py` module and the ~11 `millpy-*.py` callers that use it are a completely separate system and are explicitly out of scope — they will be migrated in the separate `wiki-v3-adoption` task.

## Scope

**In:**
- Replace `wiki/_store.py` in-memory dict with a TinyDB-backed task store
- Add task data model: `id`, `slug`, `title`, `group`, `brief`, `body`, `status`
- Implement `render()`: generates `Home.md` and `_Sidebar.md` from TinyDB tasks
- Daemon commits `tasks.json` + `Home.md` + `_Sidebar.md` in one commit per write operation
- One-time migration: parse existing `Home.md` + `proposal-*.md` files into `tasks.json` (CC runs inline, no CLI script)
- Add `tinydb` to `pyproject.toml` dependencies
- Unit tests: `_store.py` CRUD, `render()` output format, migration logic
- Integration tests: daemon read/write cycle

**Out:**
- `wiki/_client.py` public API — unchanged (`read`, `write_commit_push` signatures stay)
- `wiki/_sync.py` — unchanged (git operations layer)
- `_wiki.py` (old module) and all `millpy-*.py` callers — not touched
- `_tasks_md.py` — not touched (stays as a parsing/rendering helper used by old callers)
- Sidebar format redesign — render `_Sidebar.md` identically to today
- New task CRUD operations on the daemon protocol — not in this task
- Group-aware filtering in spawn/claim — not in this task

## Decisions

### TinyDB as backing store

- Decision: Replace the in-memory `dict[str, tuple[str, str]]` in `_store.py` with a TinyDB `Table` of task documents.
- Rationale: TinyDB persists to `tasks.json` on every write without any additional infrastructure. It is already a project dependency target. The `Table` API (insert, update, search, all) maps directly to the task CRUD operations the daemon needs internally.
- Rejected: SQLite — heavier, requires a separate driver; Redis — daemon process; plain JSON with manual file I/O — reimplements what TinyDB provides.

### File-level API unchanged

- Decision: `wiki._client.read` and `wiki._client.write_commit_push` keep their existing signatures and semantics.
- Rationale: The daemon module is not yet adopted by any callers outside of tests. Keeping the API stable avoids a protocol version bump and keeps this task focused on the store layer.
- Rejected: New task CRUD API (`get_task`, `set_phase`, etc.) — correct long-term direction, but belongs in the wiki-v3-adoption task when callers are migrated.

### Home.md is a rendered artifact

- Decision: `Home.md` is rendered from TinyDB by `render()` after every write. The rendered format is approximately identical to today's format so that `_tasks_md.parse()` still works on it.
- Rejected: Keep `Home.md` as canonical and derive TinyDB from it on each pull — this inverts the data flow and negates the value of a structured store.

### Preamble dropped from rendered Home.md

- Decision: The rendered `Home.md` starts directly with the task sections (group headers and task entries). The existing `⚠ Wiki/config.yaml er delt resource` warning block and `---` separator are not reproduced.
- Rationale: That block is a manually-added operational note, not task data. It has no place in a generated artifact.
- Rejected: Storing the preamble as a free-text field in TinyDB — unnecessary complexity.

### `brief` and `body` are separate fields

- Decision: Each task document has two text fields: `brief` (the short summary shown in `Home.md` body, typically 1–2 sentences extracted from the first paragraph of the current Home.md entry) and `body` (the full background text, sourced from `proposal-*.md` if present, otherwise empty string).
- Rationale: Separating them allows `render()` to include only `brief` in `Home.md` while future views can expose `body`.
- Rejected: Single merged text field — loses the structural distinction the proposal requires.

### Daemon commits tasks.json + Home.md + _Sidebar.md per write

- Decision: After a successful `write_commit_push` operation, the daemon commits `tasks.json`, `Home.md`, and `_Sidebar.md` together in one commit. This is the daemon's responsibility.
- Rationale: Keeps git history coherent — tasks.json and rendered views are always in sync in the commit graph.
- Rejected: Committing tasks.json only at migration time — leaves tasks.json stale after subsequent writes.

### group field is render metadata only

- Decision: `group: str | None` (values: `"A"`, `"B"`, `"C"`, `"D"`, `"Z"`, or `None`) determines which section header a task appears under in the rendered `Home.md`. Spawn and claim ignore it.
- Rationale: The current Home.md uses hand-authored section headers per layer. Rendering from TinyDB needs to reproduce this structure. Spawn/claim don't need group-awareness.

### Migration done inline by CC, no CLI script

- Decision: CC reads the existing `Home.md` and all `proposal-*.md` files in the wiki repo, constructs task documents, writes `tasks.json`, and commits. No separate `millpy-wiki-migrate.py` CLI is produced.
- Rationale: This is a one-time operation and does not need to be repeatable or distributed. CC has enough context to run it correctly.

## Technical context

### Current wiki/ module structure

```
plugins/mill/scripts/wiki/
  __init__.py      — protocol constants and exception hierarchy
  _store.py        — in-memory cache: dict[str, tuple[str, str]] (path → content+hash)
  _server.py       — WikiServer(DaemonBase): handles OP_READ and OP_WRITE requests
  _client.py       — public API: read(), write_commit_push(), _ensure_daemon()
  _sync.py         — git layer: pull(), commit_push(), atomic_write(), path_guard()
```

### Store replacement

`_store.py` currently exposes: `set(rel_path, content)`, `get(rel_path) -> (content, hash) | None`, `invalidate(rel_path)`, `invalidate_all()`. The TinyDB-backed replacement needs to:

- Store tasks as JSON documents with the full data model
- Map from the existing file-cache interface to task CRUD internally (since the server still calls `store.get("Home.md")` etc.)
- Expose additional task-oriented methods used by the server's `render()` call: `all_tasks()`, `upsert_task(task_dict)`, `set_task_status(slug, status)`

The server's `_handle_read` currently calls `self._store.get(rel_path)`. After migration, reads of `"Home.md"` return rendered markdown from TinyDB; reads of `"tasks.json"` return the raw JSON. Reads of other paths fall through to disk as before.

### Server changes

`_handle_write` currently receives a `files` payload of `{rel_path: {new_content, base_hash}}`. After migration, when `"Home.md"` is in the payload: parse the incoming markdown into task updates → apply to TinyDB → render `Home.md` + `_Sidebar.md` → commit all three files (`Home.md`, `_Sidebar.md`, `tasks.json`) via `commit_push`.

`on_start` should trigger migration if `tasks.json` is absent: parse `Home.md` + `proposal-*.md` → write initial `tasks.json`.

### Data model

```python
{
  "id": int,          # auto-increment, never reused
  "slug": str,        # kebab-case, unique
  "title": str,       # human-readable title
  "group": str|None,  # "A"|"B"|"C"|"D"|"Z"|None
  "brief": str,       # 1-2 sentence summary (first paragraph of Home.md entry)
  "body": str,        # long background (from proposal-*.md, or "")
  "status": str|None  # None|"active"|"done"|"pr-pending"|"ready-to-merge"|"blocked"
}
```

`status` maps from `_tasks_md` phases: `None` → `None`, `"s"` → `None` (spawn-ready is a UI hint, not a stored status), `"active"` → `"active"`, `"ready-to-merge"` → `"ready-to-merge"`, `"pr-pending"` → `"pr-pending"`, `"done"` → `"done"`.

### render() output format

`render(tasks: list[dict]) -> tuple[str, str]` returns `(home_md, sidebar_md)`.

`Home.md` structure:
- `# Tasks\n\n`
- Tasks with `group=None` first (no section header)
- Then per-group sections in order A → B → C → D → Z, each preceded by `# Layer <X>\n\n` (existing label text from current Home.md is not stored — just the group letter drives the header)
- Each task entry: `## <title>\n[<slug>]` (or `[[<slug>]](<proposal-link>)` if `body` non-empty) + optional `[<status>]` + blank line + `brief` text

`_Sidebar.md`: identical rendering logic to today (list of task links grouped by section).

### TinyDB path

`tasks.json` lives at `<wiki_path>/tasks.json`. TinyDB opens it with `storage=JSONStorage` (default). The daemon holds one `TinyDB` instance for its lifetime; `_store.py` wraps it.

### pyproject.toml

Add `tinydb>=4.8` to `dependencies`.

### Migration logic (on_start)

1. Check if `<wiki_path>/tasks.json` exists.
2. If absent: read `Home.md`, parse with `_tasks_md.parse()`, read each `proposal-<slug>.md` if present.
3. For each parsed task: extract `brief` from first non-empty paragraph of body text; set `body` from proposal file; assign auto-increment `id`; map `phase` → `status`.
4. Insert all tasks into TinyDB.
5. Render `Home.md` + `_Sidebar.md` from TinyDB and write to disk.
6. Commit `tasks.json` + `Home.md` + `_Sidebar.md`.

## Testing

### Unit tests (`plugins/mill/unit_tests/`)

**`test-wiki-store.py`** — TinyDB store:
- `upsert_task` / `get_task` / `all_tasks` round-trip
- `invalidate(slug)` removes the entry
- `invalidate_all()` clears all tasks
- `content_hash()` is deterministic
- Store initialises from existing `tasks.json` on disk (tempfile fixture)

**`test-wiki-render.py`** — `render()`:
- Tasks with no group render before grouped tasks
- Groups appear in A→B→C→D→Z order
- Task with `body` non-empty gets `[[slug]](proposal-slug)` link form
- Task with `status="active"` renders as `[slug] [active]`
- Rendered `Home.md` parses cleanly with `_tasks_md.parse()` (verify slug/phase round-trip)
- Empty task list renders to `# Tasks\n`

**`test-wiki-migrate.py`** — migration logic:
- `brief` is extracted from first paragraph; subsequent paragraphs are ignored
- Proposal file content lands in `body`; absent proposal → `body=""`
- Phase `"s"` maps to `status=None`
- Tasks without group get `group=None`
- Auto-increment IDs are unique and sequential

### Integration tests (`plugins/mill/integration_tests/`)

**`test-wiki-daemon-tinydb.py`** — daemon with TinyDB store:
- Write Home.md via `wiki._client.write_commit_push` → tasks.json committed → re-read Home.md parses correctly
- Phase change round-trip: write Home.md with `[active]` → read back `[active]`
- Migration on first start: daemon starts with no tasks.json → tasks.json appears after `on_start`

## Q&A log

- **Q:** Does this task depend on wiki-v3-adoption? **A:** No — the two modules are independent. This task scopes only to the `wiki/` daemon module. Old `_wiki.py` callers are out of scope.
- **Q:** Does the daemon protocol change? **A:** No — `read`/`write_commit_push` file-level API is unchanged.
- **Q:** What happens to `_tasks_md.py`? **A:** Not touched in this task. It remains as-is for the old-module callers.
- **Q:** How is the initial tasks.json produced? **A:** CC runs the migration inline during implementation (no separate CLI).
- **Q:** Is `group` used for filtering in spawn/claim? **A:** No — render metadata only.
- **Q:** Does the rendered Home.md keep the preamble warning block? **A:** No — dropped. Rendered output starts at the task sections.
- **Q:** Are `brief` and `body` separate fields? **A:** Yes — `brief` from first Home.md paragraph, `body` from proposal file.
- **Q:** Does the daemon commit tasks.json on every write? **A:** Yes — daemon commits tasks.json + Home.md + _Sidebar.md per write.
- **Q:** Testing scope? **A:** Comprehensive — unit tests for store, render, migration; integration tests for daemon cycle.
