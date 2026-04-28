# CLAUDE.md — mill-v2 project conventions

```yaml
repo: millhouse (v2 rewrite)
scope: this file is read on session start; keep it short
```

## Project shape

`mill-v2` — a plugin-based task/review/orchestration system for Claude Code. Wiki repo (sibling clone) owns task state and shared config.

## Review terminology

These terms are used throughout the review subsystem and in any design discussion about mill.

| Term | Meaning |
|---|---|
| **Frontend** | The orchestrator — the caller (e.g. a `mill-go` session in Claude Code). |
| **API** | The three review CLI scripts: `millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py`. |
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

- `plugins/mill/scripts/` — flat Python (no submodules); `millpy-*.py` CLI scripts + `_*.py` helpers. Helpers hold only production code; no `if __name__ == "__main__":` smoke-test blocks.
- `plugins/mill/templates/` — review-prompt templates + `review-output.schema.md`.
- `plugins/mill/skills/` — `SKILL.md`-per-skill; indexed at repo-root `SKILLS.md`.
- `plugins/mill/unit_tests/` — one `test-<name>.py` per helper. In-memory / `tempfile` fixtures; no real git, no real LLM. Run `python plugins/mill/unit_tests/run-all.py`.
- `plugins/mill/integration_tests/` — local-dev Python tests that invoke real `git` and optionally real `claude`. Use `.scratch/` for fixtures.
- `specs/roadmap/README.md` — canonical status tracker.
- `specs/_legacy/` — pre-discussion drafts, not authoritative.
- `.millhouse/` in working clones is gitignored local state.
- `.scratch/` in working clones is gitignored scratch-only state; not propagated to worktrees.

## Conventions worth carrying

- **Plugin scripts reference `${CLAUDE_PLUGIN_ROOT}`, never the source repo.** Anything installed via plugin manifest — `plugins/mill/`, `plugins/codeguide/`, etc. — runs on a user's machine that has no millhouse source checkout. Every intra-plugin path in a SKILL.md, Python helper, or prompt template must resolve against `${CLAUDE_PLUGIN_ROOT}`, not against `plugins/<name>/…`. This is load-bearing for external repos where CC uses mill/codeguide plugins without the millhouse source being cloned anywhere.
- **Generated markdown uses fenced ```yaml for metadata**, not `---` frontmatter. `---` is reserved for `SKILL.md` and plugin manifests. (See `plugins/mill/skills/markdown/SKILL.md`.)
- **Reviews match the tight v1 style**: per-finding = severity-label + 3–4 short bullets. Target a few hundred tokens total, not thousands. The fix-thread has full context and does not need narrative explanation.
- **Loading `mill-receiving-review` is mandatory** before reading any review output. See `plugins/mill/skills/mill-receiving-review/SKILL.md`.

## Path invariants

Path rules that keep being forgotten — they live here, not spread across SKILL.md files.

- **Junctions are IDE/terminal convenience only.** Scripts MUST resolve to the real wiki repo via `_paths.resolve_wiki_path(git_toplevel)`, never by treating `.millhouse/wiki` (or any junction) as a path. Junctions exist so the operator can type shorter paths in a shell and see the wiki in the sidebar — they are not a code contract. (The same invariant is documented in `wiki/config.yaml`'s header comment.)
- **All path resolution goes through `_paths.py`.** The module re-exports `resolve_path` from `_sibling.py` (identical-twin with codeguide's copy per spec 00) and adds `resolve_git_root` + `resolve_wiki_path`. New path-resolver helpers go here too — do not scatter private `_resolve_*` functions across `millpy-*.py` CLI scripts.
- **Scratch lives at `<cwd>/.scratch/`, not under `.millhouse/`.** Shared with other plugins the engineer uses that default to top-level `.scratch/`. `.gitignore` covers it via `**/.scratch/`. Never write to `/tmp/` or `$env:TEMP`. (See `plugins/mill/skills/conversation/SKILL.md` for the full file-writing conventions.)
