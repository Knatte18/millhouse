---
kind: plan-overview
task: Layer 02 — Review API
verify: N/A
dev-server: N/A
approved: true
started: 20260420-120000
batches: [foundation, reviewers, templates, backends, api-and-config, integration-tests]
root: plugins/mill
---

# Layer 02 — Review API

## Context

Implement the v2 review API per [discussion.md](../discussion.md). Three CLI
scripts (`mill-review-discussion.py`, `mill-review-plan.py`,
`mill-review-code.py`) produce review artefacts by orchestrating: template
rendering, file bulking, parallel per-batch dispatch (plan only), LLM
invocation via `claude -p`, verdict parsing, and review-file writing.

The discussion is the **canonical spec** for this work. `ref-formats.md`,
`00-overview.md`, and `layer-02-review.md` in `specs/` are partially
superseded by the discussion; resolve conflicts in favour of the discussion.

### Decision: 4-layer architecture

**Why:** Swappability at every layer. Backend could be email-based instead of
LLM-based; LLM could be Gemini instead of Claude; reviewer could be a cluster
instead of a single call. Each layer is replaceable without touching the
others.

**Alternatives rejected:**
- Single-file-per-review-type → no clear provider split, harder to swap LLMs.
- Config-only reviewer definition → complex reviewers (clusters, hybrids)
  outgrow config representation.

### Decision: bulk vs tool-use is a reviewer property, not a call parameter

**Why:** Moving `mode` out of the call signature simplifies the LLM-provider
interface (two distinct functions, no string parameter) and moves the
bulk-or-tool choice to where it belongs — inside the named reviewer
implementation. Backend reads `reviewer.MODE` to decide pre-bulking and
template variant.

**Alternatives rejected:**
- Mode threaded through every call: duplicates information in every layer.
- Review-type determines mode: can't support future combinations (e.g. Gemini
  tool-use discussion, Claude bulk discussion).

### Decision: backend always writes the review file

**Why:** Even in tool-use mode, the reviewer returns text and the backend
writes the file via `write_review_file()`. Keeps the 4-layer contract clean:
reviewer returns text, backend owns file I/O. Templates explicitly instruct
the LLM to *return* the review, not use Write.

**Alternatives rejected:** Claude-writes-file-via-Write (v1 pattern): couples
reviewer to file I/O, needs backend to read back what the LLM wrote, harder
to test.

## Shared Constraints

- **Flat script layout.** Every file goes under `plugins/mill/scripts/` at the
  root. No submodules, no `__init__.py`. Follow Layer 01's style (see
  `scripts/_render.py`, `scripts/mill-add.py`).
- **Print to stderr, not logging.** No `import logging`. Use
  `print(..., file=sys.stderr)` for progress/errors.
- **Bulk-only LLM interface exposes two functions:** `run_bulk(prompt_text, *, model, effort=None)` and `run_tool_use(prompt_text, *, model, effort=None)`. No `mode` parameter.
- **Reviewers declare `MODE`** as a module-level constant. Backend reads it
  before dispatching.
- **Uppercase tokens in templates.** `<TOKEN_NAME>` — `_render.py` only matches
  `[A-Z][A-Z0-9_]*`. `render_prompt()` auto-uppercases kwarg keys.
- **Config path placeholders use `<SLUG>`** (uppercase). Substituted via plain
  `str.replace` in `resolve_path()` — NOT `_render.render()` (that reads files).
- **Integration tests are local-dev only.** Real `claude -p` invocations. No
  stubs. CI integration deferred.
- **No pytest.** Integration tests are plain PowerShell / Python scripts that
  exit non-zero on failure.
- **Exit contract:** scripts exit `0` with JSON on stdout on success; exit `1`
  with empty stdout and human-readable stderr on failure.

## Shared Decisions

### Decision: ReviewError in `_review_common.py`, LLMError in `_llm_claude.py`

**Why:** Each exception lives where it is raised. Backend raises `ReviewError`
for config/slug/round errors; `_llm_claude.py` raises `LLMError` for timeout/
auth/subprocess failures. Backend imports `LLMError` from `_llm_claude` (a
lower-layer module) — the import direction is correct.

### Decision: parallelism via `ThreadPoolExecutor` from day one

**Why:** Plan review fans out per batch. 2–5 parallel subprocess calls is
typical scale; threading pool is idiomatic and simple. asyncio offers no
meaningful benefit at this scale and would force rewriting the rest.

### Decision: `task_title` field added to `.<slug>.slug.md` frontmatter

**Why:** Templates need a human-readable task title. The slug file is the
natural source (created by mill-spawn). Adding `task_title` to its YAML
frontmatter is a minimal spec extension. `load_task_title()` falls back to
the slug itself if the field is absent, so existing slug files still work.

### Decision: `run_tool_use` exposes `Read,Grep,Glob` instead of discussion's `Read,Grep,Write`

**Why:** Decision 24 (in discussion.md) states the backend always writes the
review file — the LLM returns review text, never calls Write on the output.
Exposing `Write` to the LLM would contradict that design. `Glob` is
substituted because file discovery is a natural part of the reviewer's
exploration in tool-use mode. Read-only tool surface area.

**Alternatives rejected:** Match the discussion literally (`Read,Grep,Write`):
conflicts with Decision 24.

### Decision: Code-review diff baseline via `git merge-base main HEAD`

**Why:** The discussion dropped `plan_start_hash` as a source of baseline.
`merge-base main HEAD` is a standard git convention for "what changed on
this branch," requires no plan frontmatter extension, and works with any
task-branch workflow. `cwd=project_root` is required on the subprocess
calls, as is an empty-diff guard for the "invoked on main" edge case.

## Batch Graph

```yaml
batches:
  foundation:
    depends-on: []
    summary: "_review_common.py + _llm_claude.py (pure helpers, no deps)."
  reviewers:
    depends-on: [foundation]
    summary: "Two reviewer strategies calling _llm_claude."
  templates:
    depends-on: []
    summary: "Five prompt templates + review-output schema. No Python deps."
  backends:
    depends-on: [foundation, reviewers, templates]
    summary: "Three review-type-specific backends."
  api-and-config:
    depends-on: [backends]
    summary: "Three API CLI scripts + wiki/config.yaml additions."
  integration-tests:
    depends-on: [api-and-config]
    summary: "One integration test per review type with real claude -p calls."
```

## All Files Touched

- scripts/_review_common.py
- scripts/_llm_claude.py
- scripts/_reviewer_sonnetmax.py
- scripts/_reviewer_sonnetmax_tool.py
- scripts/_review_discussion.py
- scripts/_review_plan.py
- scripts/_review_code.py
- scripts/mill-review-discussion.py
- scripts/mill-review-plan.py
- scripts/mill-review-code.py
- templates/review-discussion.md
- templates/review-plan-batch.md
- templates/review-plan-holistic.md
- templates/review-code-single.md
- templates/review-code-multi.md
- templates/review-output.schema.md
- integration_tests/test-review-discussion.ps1
- integration_tests/test-review-plan.ps1
- integration_tests/test-review-code.ps1
- integration_tests/fixtures/sample-discussion.md
- integration_tests/fixtures/sample-plan/00-overview.md
- integration_tests/fixtures/sample-plan/01-core.md
- integration_tests/fixtures/sample-code-diff.patch
