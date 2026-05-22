# Discussion: V3 wiki module with daemon and in-process cache

```yaml
task: V3 wiki module with daemon and in-process cache
slug: v3-wiki-module
status: discussing
parent: main
```

## Problem

V2 wiki access is scattered. The `_wiki.py` helpers, ad-hoc `git -C <wiki_path>`
calls, and `wiki_lock` usage are spread across ~12 caller files (25 call sites).
Multiple worktree sessions can race on concurrent writes to the shared wiki
clone, and there is no in-process cache — every read hits disk.

This task builds the **first module of the V3 architecture rewrite**: a
standalone, mill-agnostic wiki document store fronted by a persistent daemon
process. Why now: it is explicitly the first V3 module, and the planned
autonomous orchestrator (task 30) will run many parallel unattended worktrees,
where serialized writes, pull-deduplication, and a warm cross-process cache pay
off. The daemon is foundational infrastructure for that direction. The operator
has accepted that the near-term benefit over a plain library is thin and is
building the full daemon deliberately — as V3 groundwork and as a learning
exercise.

## Scope

**In:**

- New `plugins/mill/scripts/wiki/` Python subpackage: `_client.py`, `_server.py`,
  `_store.py`, `_sync.py`.
- New flat `plugins/mill/scripts/_daemon.py` — a generic, mill-agnostic daemon base.
- Update CLAUDE.md's "flat Python (no submodules)" line to record the `wiki/`
  subpackage as the deliberate exception.
- Unit tests for the pure pieces + one integration test.

**Out:**

- Porting any of the ~12 V2 callers onto the V3 module. Zero callers ported —
  this task is purely additive and changes no production code path.
- V2 `_wiki.py` is **not** modified or deleted. It keeps `wiki_lock`,
  `sync_pull`, `write_commit_push`, `clone_or_init`, `health_check`,
  `read_junctions`, `read_hardlinks`. It remains the live implementation until a
  later task ports callers.
- The V3 module does **not** cover `clone_or_init` (runs before any wiki/daemon
  exists), the config-source `health_check`, or the junction/hardlink readers —
  those are config concerns, not document-store ops.
- Home.md / proposal / sidebar parsing and rendering — stays client-side
  (`_tasks_md.py`, `_sidebar.py`). The module stores raw file content only.
- No `mill-config.yaml` schema changes. The module is parameterized by its
  caller, not driven by mill config.

## Decisions

### build-full-daemon

- Decision: Build the full daemon + socket IPC now, as designed — not a plain
  library.
- Rationale: It is the deliberate foundation for the V3 autonomous orchestrator
  (task 30, many parallel unattended worktrees). The socket + fixed JSON
  protocol also make the server an independently-lifecycle'd process (crash /
  respawn / upgrade without callers noticing) — something a library cannot give.
  Operator accepts the thin near-term payoff.
- Rejected: A plain library (direct `git -C`, a file-lock for cross-process
  serialization, lazy-pull via `.git/FETCH_HEAD` mtime). It would achieve
  consolidation and serialization with far less machinery, and the `read` /
  `write_commit_push` API is identical so a daemon could be slotted under it
  later. Rejected in favor of building the V3 substrate now.

### layout-and-mill-independence

- Decision: The module is a `wiki/` subpackage (`_client.py`, `_server.py`,
  `_store.py`, `_sync.py`), with the generic `_daemon.py` flat in `scripts/`.
  The module is **fully mill-agnostic**: zero imports of any mill helper
  (`_paths`, `_marker`, `_config`, `_wiki`, `_tasks_md`, `_subprocess_util`,
  ...). Standard library only. It is **parameterized** — the wiki-clone path,
  idle timeout, and refresh interval are passed in by the caller; the module
  never reads `mill-config.yaml` and never resolves the wiki location itself.
- Rationale: A standalone document store with a socket interface should not
  couple to the system that happens to use it first. Parameterization keeps it
  reusable and testable in isolation.
- Rejected: Flat prefixed file names (`_wiki_client.py`, ...) to honor the
  existing CLAUDE.md "flat Python" rule — the operator chose to move away from
  the flat convention for V3 modules. `_daemon.py` stays flat because it is
  generic infrastructure any future V3 module can reuse; placing it inside
  `wiki/` would make it wiki-private.

### ipc-localhost-tcp-json

- Decision: IPC is a localhost TCP socket (`127.0.0.1`, OS-assigned ephemeral
  port) carrying JSON. Each request uses **one fresh connection**: the client
  connects, sends one JSON request, the server sends the JSON response and
  **closes the connection**; the client reads to EOF — close-after-response is
  the message framing, so no length-prefix logic is needed. A random auth token
  (see state file) guards against other local processes connecting.
- Rationale: Pure stdlib (`socket`), cross-platform, no new dependency. One
  connection per request keeps clients fully independent and framing trivial.
- Rejected: Windows named pipes (needs `pywin32` — a new dependency). AF_UNIX
  sockets (stdlib on Win10+, but less battle-tested on Windows Python than TCP).

### single-threaded-daemon-queue

- Decision: The daemon is **single-threaded**. It loops: `accept()` one
  connection -> handle it fully (read request, do the work, send response,
  close) -> `accept()` the next. The OS listen backlog **is** the request
  queue; serialization is automatic. No mutex, no worker threads. The listening
  socket carries a timeout so `accept()` wakes periodically — that same tick is
  the idle-exit check (exit after N seconds with no traffic; default 600s,
  parameterized) and the lazy-refresh check.
- Rationale: The whole point of one daemon is one serialization point. A single
  thread makes races structurally impossible. Wiki writes are infrequent and
  cache reads are fast, so a slow `git push` briefly blocking other clients is
  acceptable.
- Rejected: Thread-per-connection — would reintroduce the need for an internal
  mutex and lose the simplicity of "the queue handles it."

### transparent-lazy-start

- Decision: The `_client.py` library **auto-ensures** the daemon. Every
  `read` / `write_commit_push` call first runs the ensure logic: read
  `.wiki-daemon.json`, try to connect; on failure (no daemon / dead / stale)
  spawn `_server.py`, wait until it is up, then proceed. A connection error
  mid-request triggers one re-ensure + retry, then raises. `connect` (the
  stable socket boundary) and `spawn` are **separated**: `_spawn_server()` is
  one isolated function — the single implementation-specific seam (LSP model:
  the protocol is universal, the "command to start the server" is isolated).
  Today it does a detached `subprocess.Popen` on `wiki/_server.py`; swapping
  the server later changes only this function (or makes it a no-op when the
  server is managed externally).
- Rationale: Callers never think about daemon lifecycle — they just call
  `read()`. The daemon may idle-exit freely; the next call respawns it
  transparently. Ensure-when-up is cheap (a sub-millisecond local connect).
- Rejected: Requiring callers to call `health_check()` explicitly before use —
  more ceremony, easy to forget. `health_check()` is kept as an *optional*
  public function (explicit pre-warm, test lifecycle control), not required.

### daemon-base-four-seams

- Decision: `_daemon.py` is a generic, mill-agnostic base exposing exactly four
  seams, each of which the wiki daemon itself needs (no speculative hooks):
  (1) a `handle_request(msg: dict) -> dict` callback the module supplies — the
  base owns the accept loop, JSON framing, and token auth; (2) daemon identity
  (name + how to derive the state-file path); (3) `idle_timeout`; (4)
  `on_start()` / `on_stop()` lifecycle callbacks.
- Rationale: A genuinely generic base, reusable by future V3 modules, without
  designing for requirements that do not exist yet.
- Rejected: Folding the daemon machinery into `_server.py` (contradicts the
  drawn layout, no reuse). A fully speculative framework with extra extension
  points (YAGNI).

### state-file-and-log

- Decision: The daemon writes `<wiki>/.wiki-daemon.json` and
  `<wiki>/.wiki-daemon.log` inside the wiki clone. Both are added to the wiki
  repo's `.gitignore` — the daemon ensures these entries exist on startup
  (idempotent; if it adds them, it commits and pushes that one-time `.gitignore`
  housekeeping change). State file fields: `protocol_version`, `pid`, `host`,
  `port`, `token`, `started_at` (ISO-8601 UTC). It is written **once** at
  startup, **atomically** (temp file + rename), and removed on clean idle-exit.
  The log uses `logging.handlers.RotatingFileHandler` with a small cap
  (~1 MB x 2 backups, ~3 MB total ceiling) and is truncated on each daemon
  startup. Log lines are ASCII-only.
- Rationale: Co-locating daemon artifacts with the resource they guard; the
  clone path is the daemon's natural identity (one daemon per clone). A bounded
  log keeps a long-lived background process from filling the disk.
- Rejected: A `wiki_path` field in the state file — redundant, the file is
  self-locating inside the clone. A machine-local location (`~/.millhouse/`) —
  splits artifacts across two places and `~/.millhouse/` is a mill concept,
  denting mill-independence. `stderr`-only logging — a crashed background daemon
  would leave nothing to inspect.

### spawn-race-and-staleness

- Decision: Two daemons writing the same clone would corrupt it, so spawn must
  resolve to exactly one. On startup the daemon **`O_EXCL`-creates** the state
  file *before serving*; the loser exits immediately. A stale state file (dead
  daemon — detected via connection-refused, or dead `pid` via `os.kill(pid, 0)`
  with the Windows-tolerant handling used in `_bg.py`) is cleared first, then
  `O_EXCL` retried. A `protocol_version` mismatch (old daemon survived a module
  upgrade) means the client kills the old daemon by `pid`, waits for it to die,
  then spawns a fresh one.
- Rationale: Exactly-one-daemon-per-clone is the core invariant. `O_EXCL` is an
  atomic OS primitive; the loser cannot also serve.
- Rejected: A separate spawn-lock file (extra lock, extra wait path).

### cache-raw-content

- Decision: `_store.py` is an in-process cache keyed by relative path, holding
  **raw file content** plus its content hash. It does **not** parse Home.md /
  proposals / sidebar — parsing stays client-side (`_tasks_md`, `_sidebar`).
  The cache is unbounded (the whole wiki is small markdown, well under 1 MB)
  and has **no TTL**. It is invalidated on every local write (event-based — the
  daemon knows of every mutation because all mutations go through it) and on
  every remote pull. Repopulated lazily on the next read.
- Rationale: Raw-content keeps `read()` a true drop-in for V2 file reads and
  avoids serializing parsed objects over the wire. Event-based local
  invalidation is exact and needs no TTL.
- Rejected: `_store.py` parsing Home.md and exposing typed accessors
  (`tasks()`) — couples the store to the Home.md schema and serializes
  dataclasses over IPC.

### remote-freshness-lazy-refresh

- Decision: Git cannot push-notify, so the daemon polls the remote on a **lazy
  refresh interval** (default ~10s, parameterized). `read`: if the last remote
  pull was more than the interval ago, the daemon does `git pull --ff-only`
  (invalidating the cache) before serving; otherwise it serves the cache
  instantly. `write_commit_push`: **always** pulls (`git pull --ff-only`)
  before its CAS check, so writes — the correctness-critical path — are always
  remote-fresh and CAS catches cross-machine races too.
- Rationale: A library cannot dedupe pulls across short-lived caller processes;
  the daemon can. Most reads stay instant cache hits; one read per interval
  pays the pull. Writes are rare enough to always pull.
- Rejected: Pull on every read (the cache's freshness value disappears — a pull
  costs ~100-400 ms, the cache only saves microseconds of OS-cached disk I/O).
  Never auto-pulling (reads go arbitrarily stale).

### write-commit-push-cas

- Decision: `write_commit_push` is **content-based** — the daemon owns the
  clone, so the client sends new file *content*, not paths. To close the
  read-modify-write lost-update gap, it uses **optimistic CAS**: `read` returns
  content + a content hash; `write_commit_push` sends back, per file, the
  base-hash its edit was based on; the daemon (after its pre-write pull) checks
  each file still matches that hash. Any mismatch -> the whole write is rejected
  with a `CONFLICT` response; the client re-reads the now-current file,
  recomputes its edit, and retries (bounded retries, then raises). The V2
  behaviors are preserved: `git add` -> nothing-staged means success (idempotent
  re-runs) -> `git commit` -> `git push` with **one rebase-retry** on
  non-fast-forward (`git pull --rebase`; `rebase --abort` + raise on a genuine
  conflict). After any rebase that pulls remote content, the cache is
  invalidated. The daemon always fully commits, so the working tree is never
  left dirty between requests.
- Rationale: The single-request queue makes each request atomic but does not
  make a read-modify-write across two requests atomic; CAS closes that without
  an explicit lock API or per-client daemon state. The rebase-retry is
  orthogonal — it handles another *machine* pushing, which CAS does not cover.
- Rejected: An explicit `lock()`/`unlock()` API (per-client daemon state,
  disconnect handling). Blind overwrite with no protection (silent data loss in
  concurrent mill-spawn / mill-merge runs).

### api-surface

- Decision: The client API is `read(...)`, `write_commit_push(...)`, and an
  optional `health_check() -> bool`. The daemon's fixed JSON protocol carries
  only `read` and `write_commit_push`; lifecycle (spawn, terminate, health
  probe) is out-of-band, not JSON request ops. There is **no** `sync_pull` (the
  daemon owns freshness internally) and **no** `lock`/`unlock` (CAS replaces
  them). The module defines its own mill-free exception classes (e.g. conflict,
  not-found, push-failed, protocol-error) — it does not reuse V2's
  `WikiPushError`.
- Rationale: Callers should never have to think about syncing or locking.
- Rejected: Exposing `sync_pull` (operator explicitly rejected it). Full V2
  parity including `clone_or_init` / config-`health_check` / junction readers
  (they do not belong behind a document-store daemon).

### safety-details

- Decision: (1) Path-traversal guard — `read` / `write` paths must be relative
  and stay inside the clone; reject `..`, absolute paths, anything escaping.
  (2) Atomic file writes — the daemon writes new content to a temp file +
  rename before `git add`, so a crash mid-write cannot corrupt Home.md.
  (3) Error propagation — JSON responses are `{"ok": true, ...}` or
  `{"ok": false, "error_type": "...", "error": "<message>"}`; the client maps
  `error_type` to the matching module exception and raises it. (4) All file
  content and socket payloads are UTF-8 (Home.md contains non-ASCII); daemon
  log/stdout stays ASCII-only per the cp1252 constraint.
- Rationale: Standard hardening for a network-facing, long-lived process.
- Rejected: n/a.

## Technical context

- **V2 `_wiki.py`** (`plugins/mill/scripts/_wiki.py`) — the behaviors V3
  `_sync.py` must mirror: `write_commit_push` does `git add` ->
  `git diff --cached --quiet` (return-code 1 = changes, 0 = nothing to commit =
  success) -> `git commit` -> `git push`, with one rebase-retry on a
  non-fast-forward / rejected push (`git pull --rebase`, then `rebase --abort` +
  raise on genuine conflict). `sync_pull` is `git pull --ff-only`. V2 stays
  fully intact; V3 is a parallel, unused-by-production addition.
- **`_tasks_md.py`** (`plugins/mill/scripts/_tasks_md.py`) — owns Home.md
  parsing/rendering. Stays the client-side parser; the wiki module never
  imports it.
- **`_subprocess_util.popen_detached`** (`plugins/mill/scripts/_subprocess_util.py`,
  ~line 276) — mill's detached-spawn pattern: on Windows a two-stage
  `cmd /c start "" /B /MIN` launch plus `CREATE_NO_WINDOW |
  CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB` to escape the parent
  Job Object; on POSIX `start_new_session=True`. The wiki module **cannot
  import this** (mill-agnostic) — `_client.py` must reimplement an equivalent
  stdlib-only detached spawn so `_server.py` survives the launching CC session.
- **`_bg.py`** (`plugins/mill/scripts/_bg.py`) — liveness-probe pattern: parse
  a PID, `os.kill(pid, 0)` with `ProcessLookupError` / `PermissionError`
  handling and an mtime-staleness fallback for Windows `os.kill` quirks. The
  daemon stale-detection should follow the same shape.
- **`integration_tests/test-wiki-concurrency.py`** — the model for the V3
  integration test: it builds a bare repo + working clone, launches concurrent
  subprocesses, and asserts serialization + lock cleanup. The V3 version
  launches the real client + daemon over a real socket.
- **Test harness** — unit tests live in `plugins/mill/unit_tests/`
  (`test-<name>.py`, run via `run-all.py`; in-memory / tempfile fixtures, no
  real git or LLM). Integration tests live in `plugins/mill/integration_tests/`
  (real git, scratch under `.scratch/`), not part of `run-all.py`.
- **Import convention** — operational scripts run with
  `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"`. Under that path a `wiki/`
  subpackage imports as `import wiki._client` / `from wiki import _server`, and
  flat `_daemon.py` imports as `import _daemon`. The `wiki/` package needs an
  `__init__.py`.
- **CLAUDE.md** currently states `scripts/` is "flat Python (no submodules)" —
  this task updates that line to record the `wiki/` subpackage exception.

## Constraints

- No `CONSTRAINTS.md` exists at the hub root; no `_codeguide/` in this worktree.
- The wiki module must import **zero** mill helpers — standard library only.
  It therefore cannot reuse `_subprocess_util`, `_paths`, `_config`, etc., and
  must carry its own small detached-spawn helper.
- The wiki clone is a **shared git repo** — pushes are immediately live on every
  machine. `.wiki-daemon.json` and `.wiki-daemon.log` must be gitignored so they
  are never committed/pushed.
- Windows-primary environment (Windows 11). Detached-spawn and PID-liveness code
  must work on Windows. Socket code targets `127.0.0.1` TCP for portability.
- All file content and socket payloads are UTF-8 (Home.md contains Norwegian
  text). Daemon log and any stdout must be **ASCII-only** — Windows cp1252
  crashes on non-ASCII stdout (`->` not an arrow, `--` not an em dash).
- This task is purely additive: it must not modify V2 `_wiki.py` or any of its
  ~12 callers, and must not change `mill-config.yaml`.

## Testing

Unit tests (`plugins/mill/unit_tests/`, in-memory / tempfile, no real socket or
process):

- **`_store.py` cache** — get / set / invalidate, content-hash computation,
  event-based invalidation on a local write. **TDD candidate.**
- **JSON protocol** — request and response envelope encode/decode, the
  `{"ok": false, "error_type": ...}` error envelope, token field, CAS
  base-hash fields. **TDD candidate.**
- **`_sync.py` git operations** — against a tempfile git repo (bare remote +
  clone): commit, push, nothing-to-commit-is-success, non-fast-forward
  rebase-retry, `git pull --ff-only`, pull-before-write, atomic write
  (temp + rename), path-traversal rejection.
- **`_daemon.py`** — state-file atomic write/read, stale-detection logic,
  `O_EXCL` spawn-race claim, idle-timeout computation, `.gitignore`
  idempotent maintenance. Pure logic tested without real sockets where possible.
- **CAS** — base-hash match -> write proceeds; mismatch -> `CONFLICT`.

Integration test (`plugins/mill/integration_tests/`, real git + real sockets,
modeled on `test-wiki-concurrency.py`):

- One end-to-end test: spawn the daemon via `_client`, run two concurrent
  client processes each doing a read-modify-write on Home.md; assert CAS forces
  one to retry and **both edits survive**; assert the daemon idle-exits; assert
  the state file is cleaned up.

Scenarios that must be covered somewhere: cache hit / miss; local-write
invalidation; lazy-refresh interval boundary; CAS conflict + client retry;
non-fast-forward push rebase-retry; daemon lazy-spawn on first call;
transparent respawn after idle-exit; stale state-file detection; spawn race
(two clients spawn, exactly one daemon survives); token rejection;
path-traversal rejection; read of a non-existent file.

## Q&A log

- **Q:** Build the daemon now, or a plain library (deferring the daemon)? **A:** Build the full daemon now — accepted as deliberate V3 foundation and a learning exercise, despite a thin near-term payoff. (The prior answer arrived truncated as "an"; reconfirmed.)
- **Q:** Should the wiki module depend on mill at all? **A:** No — fully mill-agnostic, stdlib-only, parameterized (wiki path / idle timeout / refresh interval passed in).
- **Q:** Keep V2's `.mill-lock` file? **A:** No — a single daemon serializes everything; no filesystem lock, and nothing named "mill" in the module.
- **Q:** Should callers call `sync_pull`? **A:** No — dropped from the API; the daemon owns remote freshness internally via the lazy refresh interval.
- **Q:** How does a read-modify-write spanning two requests stay safe? **A:** Optimistic CAS inside `write_commit_push` — not an explicit `lock()`/`unlock()` API.
- **Q:** Pull from the remote on every read? **A:** No — lazy refresh interval for reads; always pull before a write.
- **Q:** Thread-per-connection in the daemon? **A:** No — single thread; the OS listen backlog is the queue.
- **Q:** Keep the `wiki_path` field in `.wiki-daemon.json`? **A:** No — redundant; the file is self-locating inside the wiki clone.
- **Q:** If the server can be swapped behind the socket protocol, how is it spawned? **A:** Separate `connect` from `spawn`; `spawn` is one isolated, implementation-specific launcher function (LSP model) — you isolate spawning, you do not generalize it.
- **Q:** Where does the daemon log go, and can it grow unbounded? **A:** `<wiki>/.wiki-daemon.log`, gitignored, size-bounded via `RotatingFileHandler` (~3 MB ceiling), truncated on startup.
- **Q:** Does V3 cover `clone_or_init` / config-`health_check` / junction readers? **A:** No — they stay in V2 `_wiki.py`; they are not document-store ops and `clone_or_init` runs before any daemon exists.
