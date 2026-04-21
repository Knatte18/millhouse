# _llm_claude session_id support

```yaml
type: script-extension
layer: 02/03 (extends Layer-02 provider; needed by Layer-03 builder)
status: partially discussed — key decisions captured, not ready for full-write
order: 01 — implement BEFORE mill-spawn / mill-start / mill-plan / mill-go, so builder can depend on it.
```

**For the thread that will do the full-write:** these notes are *starting points*, not a finished spec. Grill Henrik on edge cases before writing. Key open areas are listed in *Open design points*.

## Purpose

Extend `_llm_claude.py` with explicit `session_id` support so long-running agents (especially the mill-go per-batch implementer) can **reuse a warm Claude session** across multiple turns — implement → receive review → fix → re-verify — without re-loading plan and codebase context on every turn. Token savings are the point.

## Why this matters

The builder flow we converged on (see `mill-go-skill`):
1. Implementer-Sonnet session `S1` implements a batch + runs `verify:`. Returns `(commit_sha, session_id=S1)`.
2. Builder runs code-review (separate thread). On `REQUEST_CHANGES`, Builder **resumes** `S1` with a new user message pointing at the review file and asking it to apply `mill-receiving-review`.
3. `S1` still has the batch context — reads plan once, files once, and responds with fixes.

Without session-reuse: every fix round spawns a cold Sonnet that re-reads the plan, re-reads all touched files, re-builds its understanding — then edits a few lines. Token sloss.

`claude -p` already supports `--session-id <uuid>` (new session with explicit id) and `--resume <id>` (continue an existing session). Henrik has used this before and confirms it works.

## Decisions

- **Add `session_id` param to existing `run_bulk` / `run_tool_use`**. Optional; default `None` means "ephemeral one-shot, current behaviour preserved".
- **Return type becomes `(output: str, session_id: str)`** (tuple). Even ephemeral calls return the server-assigned id so callers can opt-in to reuse later if they change their mind.
- **Two session lifecycles**:
  - `session_id=None` and no `resume=` — one-shot. CLI invoked without `--session-id` / `--resume`. Current path. Existing reviewer modules do not change.
  - `session_id="<uuid-or-None>", resume=True` — continue an earlier session. CLI invoked with `--resume <id>`. Requires the id to refer to a still-accessible session (claude keeps state on disk).
  - `session_id="<fresh-uuid>", resume=False` — new session with caller-chosen id. CLI invoked with `--session-id <id>`. Useful when the caller wants a predictable id for later resumption.
- **Token-allowance for implementer mode**: add `run_implementer(prompt, session_id, resume, ...)` that passes `--allowedTools Read,Edit,Write,Bash,Grep,Glob` (or similar — final list decided during mill-go spec). This is distinct from `run_tool_use` which only permits Read/Grep/Glob.
- **Session persistence (caller-side)**: `_llm_claude` does NOT persist session_ids. The builder persists them in `status.md` (e.g. `batches[].implementer_session:` field) so resuming survives a builder crash/restart.

## API proposal

```python
# _llm_claude.py (additions)

def run_bulk(
    prompt_text: str,
    *,
    model: str,
    effort: str = "default",
    session_id: str | None = None,
    resume: bool = False,
) -> tuple[str, str]:
    """Return (output, session_id). session_id is either the caller-provided id,
    a freshly generated one, or the id returned by claude CLI when resuming."""


def run_tool_use(
    prompt_text: str,
    *,
    model: str,
    effort: str = "default",
    session_id: str | None = None,
    resume: bool = False,
) -> tuple[str, str]:
    """Same as run_bulk but allows Read/Grep/Glob."""


def run_implementer(
    prompt_text: str,
    *,
    model: str,
    effort: str = "default",
    session_id: str | None = None,
    resume: bool = False,
    cwd: Path | None = None,
) -> tuple[str, str]:
    """For mill-go's implementer. Allows Read, Edit, Write, Bash, Grep, Glob.
    cwd defaults to the worktree root; Bash runs inherit that cwd."""
```

## Backend

**Extend:**
- `_llm_claude.py` — new params, new `run_implementer`, tuple return type.

**Reused:**
- `_subprocess_util.py` — unchanged.

## Callers to update (none block this spec; they change later)

- **Reviewer modules** (`_reviewer_sonnetmax.py`, `_reviewer_sonnetmax_tool.py`) — migrate to the new tuple return type. Since reviews are one-shot, they can ignore the returned session_id.
- **mill-go** (future) — sole primary consumer of `run_implementer`. Stores session_id in batch state.

## Out of scope

- No session-id-persistence in `_llm_claude` itself. Caller's job.
- No session-id-validation across restarts. If claude CLI cannot resume (state gone), the call fails; builder handles by spawning a fresh session.
- No cross-model session-sharing. Sessions are bound to the model that created them; resuming with a different model is a CLI error we surface as-is.

## Open design points

- **Session-state location on disk**: does `claude -p` keep sessions indefinitely or expire them? If there is an expiry, builder needs a fallback (fresh session) without erroring out.
- **Tool-list for implementer**: exactly which tools. Minimum: Read, Edit, Write, Bash, Grep, Glob. Add TodoWrite? Add NotebookEdit? Not WebFetch / WebSearch by default.
- **UUID generation**: `_llm_claude` generates one internally when `session_id=None, resume=False`? Or caller always supplies? Simplest: caller supplies via `uuid.uuid4().hex`, library just passes through.
- **Error surface**: what error shape does `_llm_claude` emit if `--resume` fails (stale session)? Distinct exception so builder can fall back gracefully.
- **Integration with existing `LLMError`**: reuse `LLMError`, add a subclass `LLMSessionError` for the fallback case.
- **Logging**: stderr prefix for session events (`[llm] session=<id> start/resume/complete`). Useful for diagnosing stuck builders.
- **Test strategy**: a local-dev integration test invokes `run_implementer` with a tiny prompt, then resumes, verifies context carries over. Costs a couple of cents per run.
