# Plan: 63 (A) — Reviewer tool-sandbox: git snapshot guard + fix --allowedTools

```yaml
task: '63 (A) — Reviewer tool-sandbox: git snapshot guard + fix --allowedTools'
slug: review-sandbox-guard
approved: true
started: '20260517-111503'
parent: main
root: ""
verify: python plugins/mill/unit_tests/run-all.py
```

## Batch Index

```yaml
batches:
  - number: 1
    name: guard-helper
    file: 01-guard-helper.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-review-guard.py
  - number: 2
    name: wire-guard-backends
    file: 02-wire-guard-backends.md
    depends-on: [1]
    verify: python plugins/mill/unit_tests/test-review-plan-flow.py && python plugins/mill/unit_tests/test-review-code-flow.py && python plugins/mill/unit_tests/test-review-discussion-flow.py
  - number: 3
    name: fix-allowed-tools-argv
    file: 03-fix-allowed-tools-argv.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-llm-claude.py
  - number: 4
    name: template-identity-header
    file: 04-template-identity-header.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: ASCII-only log strings

- **Decision:** All `print()` and `_log()` output strings introduced or modified by this task use ASCII only. Em-dash (`—`) becomes ` -- `; right-arrow (`->`) becomes ` -> `. Docstrings, comments, and markdown file content are exempt (only stdout/stderr-bound strings are restricted).
- **Rationale:** Windows cp1252 terminals crash on non-ASCII stdout/stderr (per CLAUDE.md hard rule).
- **Applies to:** all batches

### Decision: ReviewerOverstepError subclasses ReviewError

- **Decision:** `ReviewerOverstepError(ReviewError)` — subclass, not sibling. Lives in `_review_common.py` alongside `ReviewError`.
- **Rationale:** Existing API-layer catches at `millpy-review-*.py` use `except ReviewError`; subclassing preserves that behaviour while letting callers `isinstance` for discrimination when needed.
- **Applies to:** batch 1 (declaration), batch 2 (catch-and-rethrow flow)

### Decision: `git -C <project_root>` pattern, never cd

- **Decision:** All git invocations from the guard helper and any new code use the `git -C <project_root>` form (or equivalent `subprocess.run(..., cwd=project_root)`). No `os.chdir`, no `cd <path> && git ...`.
- **Rationale:** Wiki-access convention (CLAUDE.md `## Wiki access`); cwd mutations are forbidden across the codebase.
- **Applies to:** batch 1, batch 2

### Decision: `_subprocess_util.run` for subprocess invocations

- **Decision:** The guard helper invokes `git rev-parse HEAD` and `git status --porcelain` via `_subprocess_util.run(argv, cwd=project_root)`, not raw `subprocess.run`.
- **Rationale:** `_subprocess_util.run` injects `PYTHONIOENCODING=utf-8`, captures decoded UTF-8 text, emits spawn/exit breadcrumbs on stderr. Matches the convention used by `_wiki.py` and `_llm_claude.py`.
- **Applies to:** batch 1

### Decision: Real-tempfile git repo in unit tests

- **Decision:** `test-review-guard.py` uses `tempfile.TemporaryDirectory()` + `subprocess.run(["git", "init"], ...)` per test case. No mocking of `subprocess.run` for the guard test surface.
- **Rationale:** A pure-mock test would not catch a porcelain-format parsing bug or a git CLI behaviour change. The fixture is cheap and matches the existing flow-test pattern in `test-review-plan-flow.py`.
- **Applies to:** batch 1

### Decision: Snapshot guard expected_paths uses substring match on normalized forward-slash paths

- **Decision:** `worktree_snapshot_guard(project_root, *, expected_paths=None)`. Each entry in `expected_paths` is a string (config-supplied, e.g. `"_mill/reviews/"`). Porcelain comparison normalizes each entry's path field by replacing `\` with `/`; a porcelain line is filtered when its normalized path field contains any expected_paths entry as a substring. HEAD-SHA comparison is NEVER filtered — any HEAD change raises.
- **Rationale:** Substring + forward-slash normalization survives both POSIX and Windows porcelain output; survives optional trailing slashes in config; precise enough to allow `_mill/reviews/*.md` writes while rejecting any other mutation.
- **Applies to:** batch 1 (helper implementation), batch 2 (call sites pass `cfg["paths"]["reviews_dir"]`)

### Decision: Single guard window per backend run()

- **Decision:** Each of the three review backends wraps the body of `run()` in exactly one `with worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]]):` block. The block covers parallel `ThreadPoolExecutor` fan-out in `_review_plan`, holistic calls, and NEED_CONTEXT resume retries.
- **Rationale:** "Did this review pass mutate state?" is the question, not "which sub-call?". A single window is race-safe in the parallel fan-out and trivial to reason about.
- **Applies to:** batch 2

### Decision: `_build_argv` derives `--disallowedTools` from `allowed_tools`

- **Decision:** `_build_argv` tokenises `allowed_tools` on comma+whitespace and checks set intersection with `{"Edit","Write","Bash","NotebookEdit"}`. When the intersection is empty (bulk `""` and tool-use `"Read,Grep,Glob"`), append `["--disallowedTools","Edit,Write,Bash,NotebookEdit"]`. When non-empty (implementer `"Read,Edit,Write,Bash,Grep,Glob,Skill"`), skip the disallow flag. `--allowedTools <value>` is emitted only when `allowed_tools` is non-empty. No signature change to `_invoke` or to `run_bulk`/`run_tool_use`/`run_implementer`.
- **Rationale:** Keeps the change isolated to one function; self-classifies all three call shapes; no need to thread a new parameter through the call chain.
- **Applies to:** batch 3

### Decision: Identity header verbatim, prepended to template

- **Decision:** Prepend the exact text block from `_mill/discussion.md` § Decisions → `template-identity-header` as the new first paragraph of each of the five review templates, separated from the existing first sentence by a blank line. No new template token, no `render_prompt` change.
- **Rationale:** Smallest change; templates are rarely edited; abstraction is premature for one paragraph.
- **Applies to:** batch 4

## All Files Touched

- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/templates/review-code-batch.md`
- `plugins/mill/templates/review-code-holistic.md`
- `plugins/mill/templates/review-discussion.md`
- `plugins/mill/templates/review-plan-batch.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/unit_tests/test-llm-claude.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-guard.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
