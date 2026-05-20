# Mill V3 — Architecture proposal

Strawman for a module-based rewrite. Each module is a standalone unit with a strict API, its own performance characteristics, and no hard dependency on other modules.

## Motivation

Mill V2 grew organically. `millpy` is a flat collection of scripts and helpers with blurry boundaries. Consequences:
- Performance fixes require touching many files
- Swapping a backend (LLM provider, git library) touches the same files
- Testing requires the full environment
- Python startup cost (~215ms) + subprocess git calls (~150ms each) paid on every invocation

---

## Proposed modules

### 1. Wiki

Standalone document store for task state. All mutations go through this module — no direct file writes to the wiki clone elsewhere.

Responsibilities:
- Read/write Home.md, proposal files, sidebar
- Mutex / wiki lock
- Layers: A (read), B (write + commit), C (push)
- Internal cache with **event-based invalidation** — cache is valid until `write_commit_push` or `sync_pull` is called. No TTL. The module knows when data is stale because all mutations go through it.

API shape (language-agnostic over stdin/stdout JSON, or Python import):
```
wiki.read(path) -> str
wiki.write_commit_push(files, message) -> sha
wiki.sync_pull() -> None
wiki.lock() / wiki.unlock()
```

### 2. LLM caller

Provider-agnostic subprocess module. Starts a process, sends a prompt, gets a response. The backend (Claude via psmux, Claude API, Ollama, Gemini, ...) is an implementation detail hidden behind the protocol.

Protocol: JSON over stdin/stdout.

```json
// Commands (orchestrator → worker)
{"cmd": "prompt",  "text": "...", "model": "haiku", "tools": [...], "session_id": "abc"}
{"cmd": "resume",  "session_id": "abc", "input": "..."}
{"cmd": "kill",    "session_id": "abc"}

// Responses (worker → orchestrator)
{"status": "success",   "response": "...", "session_id": "abc"}
{"status": "escalate",  "question": "...", "context": "...", "session_id": "abc"}
{"status": "stuck",     "reason": "...",   "session_id": "abc"}
```

Key design decisions:
- **One-shot process**: starts, handles all tool-call loops internally, exits with result. Orchestrator uses `run_in_background` and gets a notification on exit — no polling.
- **Tool use is internal**: LLM → tool call → dispatch → result → LLM loop happens inside the module. Caller never sees it.
- **Escalation (yield)**: worker can pause mid-task and send `status: escalate` to orchestrator. Orchestrator (which has broader context — full plan DAG, other batch states) responds with guidance. Worker continues. This enables cheap Haiku workers with an Opus "brain" that activates only when needed.
- **Timeout / GC**: worker exits if idle for N seconds (configurable, default 600s) AND not waiting for orchestrator. If waiting for orchestrator, checks parent PID liveness instead of timer. Orchestrator sends its own PID at startup so the check is direct, not dependent on process hierarchy.

Supported providers (backends):
- `claude-psmux` — Claude Code running in a psmux pane
- `claude-api` — Direct Anthropic API
- `ollama` — Local Ollama instance
- `gemini` — Google Gemini API

### 3. Worktree lifecycle

Manages git worktrees end-to-end.

Responsibilities:
- Create worktree (branch, directory, junctions)
- List active worktrees (replaces `git worktree list` subprocess — candidate for pygit2)
- Remove worktree safely (strip junctions before rmdir)
- Branch operations

Internal cache of worktree list, invalidated on create/remove.

### 4. Task state

Read/write of `_mill/status.md` and plan files.

Responsibilities:
- Phase transitions (`planned` → `implementing` → `reviewing` → ...)
- Batch state (pending / running / approved / blocked)
- Plan DAG parsing and topological sort
- Status snapshots

All state mutations go through this module so it can maintain an in-process cache.

### 5. Review pipeline

Template rendering and verdict parsing. Decoupled from the LLM layer — takes a rendered prompt string, returns a structured verdict.

Responsibilities:
- Render review prompt from template + tokens + file content
- Parse verdict from fenced yaml block (`APPROVE` / `REQUEST_CHANGES` / `NEED_CONTEXT`)
- Bulk/tool-use mode selection per reviewer strategy

No knowledge of how the LLM is called — that is module 2's job.

### 6. Codeguide

Already a separate plugin. Needs decoupling from mill's config loading — should resolve its own config independently without importing mill helpers.

---

## Cross-cutting principles

**Cache invalidation by event, not TTL.** A time-based cache is unreliable for developer tools. Each module knows exactly when its data changes because all mutations go through it. No stale reads.

**pygit2 over subprocess git.** `git worktree list` and similar calls cost ~150ms on Windows (subprocess + Defender scanning). pygit2 (libgit2 C bindings) runs in-process. Full worktree API available since pygit2 1.x. Ships as Windows wheels on PyPI.

**psmux is general infrastructure.** Not Claude-specific. Any process that benefits from a warm, persistent terminal session can use it. The LLM-caller module uses psmux as one of several possible backends.

**Lazy-start daemon.** A thin shim checks if the daemon is running; starts it on first use. Orchestrator pays startup cost once per session. All subsequent calls are socket/pipe latency only.

**Opus orchestrator + cheap workers.** Happy path: Opus is idle, Haiku (or Ollama) workers run batches. Stuck path: worker escalates with local context, Opus responds with guidance from its broader plan view. Cost is proportional to problems, not batches.

---

## Relation to V2

V2 is functional. V3 is not a rewrite-from-scratch in the sense of throwing away logic — the review templates, the plan DAG format, the wiki schema are all worth keeping. The rewrite is the module boundaries and the LLM-caller protocol.

A sensible migration: define module APIs (interfaces) first, port one module at a time, keep V2 as fallback until all modules are ported.
