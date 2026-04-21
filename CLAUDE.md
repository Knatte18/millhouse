# CLAUDE.md — mill-v2 project conventions

```yaml
repo: millhouse (v2 rewrite)
scope: this file is read on session start; keep it short
```

## Project shape

This is `mill-v2` — a plugin-based task/review/orchestration system for Claude Code. Layer 01 (bootstrap: `mill-setup`/`mill-add`/`mill-list`) and Layer 02 (review API: `mill-review-discussion`/`-plan`/`-code`) are implemented. Layers 03 (orchestration) and 04 (extras) are not started.

Canonical status: `specs/roadmap/README.md`.

Wiki repo (separate, at `c:/Code/millhouse/wiki/`) owns task state and shared config.

## Review terminology

These terms are used throughout the review subsystem and in any design discussion about mill.

| Term | Meaning |
|---|---|
| **Frontend** | The orchestrator — the caller (e.g. a `mill-go` session in Claude Code). |
| **API** | The three review CLI scripts: `mill-review-discussion.py`, `mill-review-plan.py`, `mill-review-code.py`. |
| **Backend** | Everything behind the API — templates, bulking, file-writing, reviewer dispatch, verdict parsing, ReviewResult assembly. Lives in `_review_*.py` + `_review_common.py`. |
| **Reviewer** | A named strategy module (simple LLM, cluster, round-switching hybrid). Declares a module-level `MODE` constant (`"bulk"` or `"tool-use"`) and exposes `run(prompt_text) -> str`. File pattern: `_reviewer_<name>.py`. |
| **LLM-provider** | Thin wrapper around a specific model. Exposes one function per mode (e.g. `_llm_claude.run_bulk`, `_llm_claude.run_tool_use`). No review semantics — just "send text, get text". |
| **prompt_text** | The fully-rendered prompt string passed to the LLM. Built by the backend from a template + tokens + bulked file content. |

Claude is **not** a backend — Claude is an LLM. The backend could in principle be an email-to-human reviewer; the API contract does not change.

## Review severity vocabulary

| Review type | Severity | Verdict |
|---|---|---|
| `discussion` | `GAP` / `NOTE` | `APPROVE` / `GAPS_FOUND` |
| `plan`       | `BLOCKING` / `NIT` | `APPROVE` / `REQUEST_CHANGES` |
| `code`       | `BLOCKING` / `NIT` | `APPROVE` / `REQUEST_CHANGES` |

A discussion gap is missing information; a plan/code block is a must-fix defect. Different semantics → different vocabulary (matches v1 convention).

## Repo layout pointers

- `plugins/mill/scripts/` — flat Python (no submodules); `mill-*.py` CLI scripts + `_*.py` helpers.
- `plugins/mill/templates/` — review-prompt templates + `review-output.schema.md`.
- `plugins/mill/skills/` — `SKILL.md`-per-skill; indexed at repo-root `SKILLS.md`.
- `plugins/mill/integration_tests/` — local-dev Python tests that invoke real `claude`. Use `.millhouse/scratch/` for fixtures.
- `specs/roadmap/README.md` — canonical status tracker.
- `specs/_legacy/` — pre-discussion drafts, not authoritative.
- `.millhouse/` in working clones is gitignored local state; `.millhouse/wiki` is a junction to the shared wiki repo.

## Conventions worth carrying

- **Never write to `/tmp/` or `$env:TEMP`.** Use `.millhouse/scratch/`. (See `plugins/mill/skills/conversation/SKILL.md`.)
- **Generated markdown uses fenced ```yaml for metadata**, not `---` frontmatter. `---` is reserved for `SKILL.md` and plugin manifests. (See `plugins/mill/skills/markdown/SKILL.md`.)
- **Reviews match the tight v1 style**: per-finding = severity-label + 3–4 short bullets. Target a few hundred tokens total, not thousands. The fix-thread has full context and does not need narrative explanation.
- **Loading `mill-receiving-review` is mandatory** before reading any review output. See `plugins/mill/skills/mill-receiving-review/SKILL.md`.
