# Plan: mill-vscode/mill-spawn leak CLAUDE_CODE_CHILD_SESSION into spawned VS Code windows

```yaml
task: "mill-vscode/mill-spawn leak CLAUDE_CODE_CHILD_SESSION into spawned VS Code windows"
slug: mill-vscode-spawn-session-leak
approved: false
started: "20260728-165804"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: scrub-session-env
    file: 01-scrub-session-env.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-subprocess-util.py test-millpy-vscode.py test-millpy-terminal.py
```

## Shared Decisions

### Decision: allowlist, not prefix match

- **Decision:** `scrub_env()` strips exactly the 3 named session-marker vars —
  `CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_ENTRYPOINT` — via
  an explicit set/frozenset membership check, never a `CLAUDE_CODE_` prefix match.
- **Rationale:** `discussion.md`'s `Decisions > scrub-scope` (superseded once, in review
  round 2): a blanket prefix strip would also drop `CLAUDE_CODE_USE_BEDROCK` /
  `CLAUDE_CODE_USE_VERTEX`, which are persistent user-set backend-routing config, not
  session markers. Stripping those would silently break Bedrock/Vertex routing for
  every spawned session — worse than the bug being fixed.
- **Applies to:** all batches.

### Decision: `scrub_env()` signature and location

- **Decision:** `scrub_env(env: dict[str, str] | None = None) -> dict[str, str]` lives
  in `plugins/mill/scripts/_subprocess_util.py`, as a plain function alongside `run()`
  and `popen_detached()` — not a change to either of their signatures or defaults. When
  `env` is `None`, the function reads `os.environ` internally; callers that need to
  inject a fake env for testing pass it explicitly through `env`.
- **Rationale:** `discussion.md`'s `Decisions > helper-location`. `_subprocess_util.py`
  is already the shared home for subprocess-launch concerns in this codebase. The `env`
  parameter exists purely to give unit tests an isolated seam — production call sites
  always call `scrub_env()` with zero arguments.
- **Applies to:** all batches.

### Decision: build via dict comprehension, not mutate-in-place

- **Decision:** `scrub_env()`'s body is a single dict comprehension over the source
  env's `.items()`, filtering out keys in a module-level allowlist constant (e.g.
  `_SCRUBBED_ENV_KEYS`), not `dict.copy()` + `pop()`/`del`.
- **Rationale:** `discussion.md`'s `Decisions > env-copy-semantics`. Simplest correct
  form; absence of any allowlisted key is a no-op, not an error.
- **Applies to:** all batches.

### Decision: `_subprocess_util.run()`/`popen_detached()` untouched

- **Decision:** This task adds `scrub_env()` to `_subprocess_util.py` but makes no
  change to `run()` or `popen_detached()` — neither their signatures, defaults, nor
  internal env handling. The four fixed call sites continue to call `subprocess.run()`
  directly (bypassing `_subprocess_util.run()`), now passing `env=scrub_env()`.
- **Rationale:** All four in-scope call sites are interactive launchers explicitly
  commented as needing to keep their own console and NOT route through
  `_subprocess_util.run()` (`millpy-vscode.py:274`, `millpy-terminal.py:117`/`:120`).
  `discussion.md`'s `Scope > Out` confirms this explicitly.
- **Applies to:** batch `scrub-session-env`.

## All Files Touched

- `plugins/mill/scripts/_subprocess_util.py`
- `plugins/mill/scripts/millpy-vscode.py`
- `plugins/mill/scripts/millpy-terminal.py`
- `plugins/mill/unit_tests/test-subprocess-util.py`
- `plugins/mill/unit_tests/test-millpy-vscode.py`
- `plugins/mill/unit_tests/test-millpy-terminal.py`
