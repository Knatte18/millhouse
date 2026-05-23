# Discussion: Migrate wiki task store to TinyDB

```yaml
task: Migrate wiki task store to TinyDB
slug: wiki-tinydb
status: discussing
parent: main
```

## Problem

`wiki/_store.py` is an in-memory dict mapping file paths to `(content, hash)` tuples. It has no concept of tasks — it is a generic content cache that loses all state on daemon restart. Tasks are opaque markdown blobs; the daemon has no structured understanding of what it caches.

Replacing this with TinyDB makes tasks the first-class entity inside the daemon. `tasks.json` persists to the wiki repo and becomes the canonical task store. `Home.md` and `_Sidebar.md` are generated artifacts rendered from TinyDB after each mutation.

This task touches only the `wiki/` daemon module. The old `_wiki.py` module and all `millpy-*.py` callers are a completely separate system — they are out of scope and will be migrated in the separate `wiki-v3-adoption` task.

## Scope

**In:**
- Replace `wiki/_store.py` in-memory dict with a TinyDB-backed task store
- Task data model: `id`, `slug`, `title`, `group`, `brief`, `body`, `status`
- `render()` function: generates `Home.md`, `_Sidebar.md`, and `proposal-<slug>.md` detail files from TinyDB tasks
- `_server.py`: intercept Home.md writes to update TinyDB; re-render all files after every write; re-read Home.md from disk after pull to repopulate TinyDB
- Daemon commits `tasks.json` + `Home.md` + `_Sidebar.md` + any `proposal-*.md` files in one commit per write operation
- Add `tinydb` to `pyproject.toml` dependencies
- Unit tests: TinyDB CRUD, `render()` output format
- Integration tests: daemon read/write cycle

**Out:**
- `wiki/_client.py` public API — unchanged (`read`, `write_commit_push` signatures stay)
- `wiki/_sync.py` — unchanged
- `_wiki.py` (old module) and all `millpy-*.py` callers — not touched
- `_tasks_md.py` — not touched, not referenced, not a constraint
- Sidebar format redesign — render `_Sidebar.md` in the same style as today
- New task CRUD operations on the daemon protocol — not in this task
- Group-aware filtering in spawn/claim — not in this task
- Migration of existing Home.md data to tasks.json — not in this task (wiki-v3-adoption)

## Decisions

### TinyDB as backing store

- Decision: Replace `_store.py`'s `dict[str, tuple[str, str]]` with a TinyDB `Table` of task documents stored in `tasks.json`.
- Rationale: TinyDB persists to JSON on every write without additional infrastructure. The `Table` API (insert, update, search, all) covers all internal task operations the daemon needs.
- Rejected: SQLite — heavier; plain JSON with manual I/O — reimplements TinyDB; keeping the in-memory dict — loses state on restart.

### File-level API unchanged

- Decision: `wiki._client.read` and `wiki._client.write_commit_push` keep their existing signatures and semantics. The daemon protocol (JSON over TCP) is unchanged.
- Rationale: The daemon module has no external callers yet. Keeping the API stable avoids a protocol version bump and keeps this task focused on the store layer. Structural API changes belong in wiki-v3-adoption.
- Rejected: New task CRUD protocol (`get_task`, `set_phase`, etc.) — correct long-term direction but premature here.

### Home.md is a rendered artifact

- Decision: The daemon's `render()` generates `Home.md` from TinyDB. When a write comes in containing `Home.md`, the daemon parses the incoming markdown to extract task data, updates TinyDB, then re-renders `Home.md` + `_Sidebar.md` and commits all three files (`Home.md`, `_Sidebar.md`, `tasks.json`).
- Rationale: `tasks.json` must stay in sync with every write.
- Rejected: Storing raw file content in TinyDB — makes TinyDB a persistent dict with no task semantics.

### Preamble dropped from rendered Home.md

- Decision: The rendered `Home.md` starts directly with the task sections. The existing `⚠ Wiki/config.yaml er delt resource` warning block is not reproduced.
- Rationale: That block is a hand-authored operational note, not task data. It has no place in a generated artifact.

### `brief` and `body` are separate fields

- Decision: `brief` (1–2 sentence summary shown in `Home.md`) and `body` (long background) are distinct fields in the task document.
- Rationale: Allows `render()` to include only `brief` in `Home.md` while future views can expose `body`.

### `status="blocked"` renders without a phase marker

- Decision: `"blocked"` is a valid stored status in TinyDB, but `render()` emits no phase marker for it in `Home.md`. A blocked task appears as unclaimed in the rendered view.
- Rationale: `"blocked"` is not a Home.md display concept — it is internal daemon state. Emitting `[blocked]` in Home.md would be a format that nothing currently understands.

### group field is render metadata only

- Decision: `group: str | None` (values: `"A"`, `"B"`, `"C"`, `"D"`, `"Z"`, or `None`) determines which section header a task appears under in the rendered `Home.md`. Spawn and claim ignore it.

### Daemon commits tasks.json + Home.md + _Sidebar.md per write

- Decision: After every successful write operation, the daemon commits `tasks.json`, `Home.md`, `_Sidebar.md`, and all `proposal-<slug>.md` files returned by `render()`, together in one git commit.
- Rationale: Keeps the commit graph coherent — `tasks.json` and all rendered views are always in sync.

## Technical context

### Current wiki/ module structure

```
plugins/mill/scripts/wiki/
  __init__.py      -- protocol constants and exception hierarchy
  _store.py        -- in-memory cache: dict[str, tuple[str, str]] (path -> content+hash)
  _server.py       -- WikiServer(DaemonBase): handles OP_READ and OP_WRITE requests
  _client.py       -- public API: read(), write_commit_push(), _ensure_daemon()
  _sync.py         -- git layer: pull(), commit_push(), atomic_write(), path_guard()
```

### Store replacement

`_store.py` currently exposes: `set(rel_path, content)`, `get(rel_path) -> (content, hash) | None`, `invalidate(rel_path)`, `invalidate_all()`. The TinyDB replacement removes `invalidate_all()` and must:

- Store tasks as JSON documents with the full data model (see below)
- Expose task-oriented methods for the server: `all_tasks()`, `upsert_task(task_dict)`, `get_by_slug(slug)`, `content_hash(content) -> str`
- On `set("Home.md", content)`: parse incoming markdown to extract task structure, update TinyDB documents
- On `get("Home.md")`: render current TinyDB tasks to markdown and return `(rendered_content, hash)`; return `None` if TinyDB contains no tasks and has never been populated (uninitialized state, distinct from a genuinely empty task list)
- On `set`/`get` for non-Home.md paths: fall through to the existing file-content caching behaviour (path -> content dict, unchanged)
- `invalidate(rel_path)`: for non-Home.md paths, clears the path entry from the file-content dict as before; for `"Home.md"`, marks TinyDB as uninitialized so the next `get("Home.md")` returns `None` (cache miss)

**Post-pull repopulation:** `invalidate_all()` is gone. After a successful `pull()`, `_handle_read` explicitly reads `Home.md` from disk and calls `store.set("Home.md", disk_content)` to repopulate TinyDB. This replaces the old pattern of clearing the cache and relying on cache-miss reads.

**Write path sequence** — `_handle_write` executes in this order:
1. `pull()` — fetch latest from remote
2. Re-read `Home.md` from disk and call `store.set("Home.md", disk_content)` to sync TinyDB with the pulled state (same as post-pull repopulation in reads)
3. CAS check — compute current hash from `store.get("Home.md")` (or disk for non-Home.md files); compare against `base_hash` from client; reject on mismatch
4. `atomic_write` — write each client file to disk
5. `store.set("Home.md", new_content)` — update TinyDB from the written content
6. `render()` — generate `Home.md`, `_Sidebar.md`, `proposal-*.md` from TinyDB
7. Write rendered files to disk (overwriting the atomic_write result for `Home.md`)
8. `commit_push` — commit `tasks.json` + `Home.md` + `_Sidebar.md` + `proposal-*.md`

**upsert_task merge behaviour:** `upsert_task` merges the incoming dict with the existing TinyDB document — fields not present in the incoming data are preserved from the stored document. In particular, `body` (not recoverable from Home.md) is never overwritten with `""` on a Home.md write; the existing value is kept.

### Data model

```python
{
    "id": int,          # auto-increment, never reused
    "slug": str,        # kebab-case, unique
    "title": str,       # human-readable title
    "group": str|None,  # "A"|"B"|"C"|"D"|"Z"|None
    "brief": str,       # 1-2 sentence summary shown in Home.md body
    "body": str,        # long background (empty string if none)
    "status": str|None  # None|"active"|"done"|"pr-pending"|"ready-to-merge"|"blocked"
}
```

### Parsing incoming Home.md writes

When `_handle_write` receives a write of `Home.md`, the server must parse the markdown into task documents before updating TinyDB. This requires:

1. Walk raw markdown text line by line to detect `# Layer <letter>` section headers and attribute each task to its nearest preceding header (or `group=None` if none precedes it). Standard heading regex only matches `##` task headings; the `#` group headers require a separate scan.
2. For each `##` task heading: extract `slug`, `title`, `status` (from phase marker, if present).
3. Extract `brief` from the first non-empty paragraph of the task body (the text between the slug line and the next `##` heading). This is a raw text scan, not a structured parse call.
4. `body` is not recoverable from Home.md (it comes from proposal files which are out of scope here). On writes that come from the old-style Home.md, `body` is left empty.

### render() output format

`render(tasks: list[dict]) -> dict[str, str]` returns a mapping of `rel_path -> content` for all files the daemon should write and commit: `Home.md`, `_Sidebar.md`, and one `proposal-<slug>.md` per task with non-empty `body`.

`Home.md` structure:
- `# Tasks\n\n`
- Tasks with `group=None` listed first (no section header)
- Then groups in order A -> B -> C -> D -> Z, each preceded by `# Layer <X>\n\n`
- Each entry: `## <title>\n[<slug>]` + phase marker if `status` is one of `active`, `done`, `pr-pending`, `ready-to-merge` (blocked and None emit no marker) + blank line + `brief`

`_Sidebar.md`: navigation list in the same group order as `Home.md`. Tasks with `body != ""` get a wiki link to `proposal-<slug>.md`; tasks without body are listed as plaintext.

`proposal-<slug>.md`: one file per task where `body != ""`. Content is the `body` field verbatim. The daemon commits these files alongside `Home.md`, `_Sidebar.md`, and `tasks.json`.

### tasks.json location

`<wiki_path>/tasks.json` — TinyDB default JSONStorage. The daemon holds one `TinyDB` instance for its lifetime.

### pyproject.toml

Add `tinydb>=4.8` to `dependencies`.

## Testing

### Unit tests (`plugins/mill/unit_tests/`)

**`test-wiki-store.py`** — TinyDB store:
- `upsert_task` / `get_by_slug` / `all_tasks` round-trip
- `invalidate("Home.md")` marks TinyDB uninitialized; next `get("Home.md")` returns `None`
- `invalidate("other.md")` clears only the file-content entry for that path
- `content_hash()` is deterministic
- Store loads from existing `tasks.json` on disk (tempfile fixture)
- `set("Home.md", content)` parses incoming markdown and updates TinyDB documents
- `get("Home.md")` returns `None` before first `set` (uninitialized), then renders tasks after `set`

**`test-wiki-render.py`** -- render():
- Tasks with no group appear before grouped tasks
- Groups appear in A->B->C->D->Z order
- Status `"blocked"` and `None` both emit no phase marker
- Status `"active"` emits `[active]` marker
- Task with `body != ""` gets a wiki link in `_Sidebar.md` and a `proposal-<slug>.md` entry in the returned dict
- Task with `body == ""` is listed as plaintext in `_Sidebar.md`, no proposal file in output
- Empty task list: `Home.md` renders to `# Tasks\n`, no proposal files

### Integration tests (`plugins/mill/integration_tests/`)

**`test-wiki-daemon-tinydb.py`** -- daemon with TinyDB store:
- Write Home.md via `wiki._client.write_commit_push` -> `tasks.json` committed alongside `Home.md` and `_Sidebar.md`
- Phase marker round-trip: write Home.md with `[active]` -> read back `[active]`
- Daemon restart: TinyDB reloads from `tasks.json`; cached task state survives

## Q&A log

- **Q:** Does this task depend on wiki-v3-adoption? **A:** No. The two modules are independent. Old `_wiki.py` callers are out of scope.
- **Q:** Does the daemon protocol change? **A:** No -- `read`/`write_commit_push` file-level API is unchanged.
- **Q:** Does this task include migration of existing Home.md data? **A:** No. Migration is part of wiki-v3-adoption.
- **Q:** Is group used for filtering in spawn/claim? **A:** No -- render metadata only.
- **Q:** Does rendered Home.md keep the preamble warning block? **A:** No -- dropped. Rendered output starts at the task sections.
- **Q:** Are `brief` and `body` separate fields? **A:** Yes.
- **Q:** Does the daemon commit tasks.json on every write? **A:** Yes -- daemon commits tasks.json + Home.md + _Sidebar.md + proposal-*.md per write.
- **Q:** What happens with `"blocked"` status in the rendered view? **A:** No phase marker emitted -- blocked tasks appear as unclaimed in Home.md.
- **Q:** What are the detail documents named? **A:** `proposal-<slug>.md` -- same convention as before; body field content verbatim.
- **Q:** Does the sidebar link all tasks? **A:** Tasks with non-empty body get a wiki link to their proposal file; tasks without body are plaintext.
- **Q:** Does `invalidate_all()` exist in the new store? **A:** No -- removed. After pull, server explicitly re-reads Home.md from disk and calls `store.set("Home.md", content)` to repopulate TinyDB.
