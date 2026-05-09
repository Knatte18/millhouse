# CLAUDE.md — mill-v2 project conventions

```yaml
repo: millhouse (v2 rewrite)
scope: this file is read on session start; keep it short
```

## Project shape

`mill-v2` — a plugin-based task/review/orchestration system for Claude Code. Wiki repo (sibling clone) owns the task index and shared config. Working state (`task/status.md`, `task/discussion.md`, `task/plan/`, `task/reviews/`) lives in the `task/` subdirectory on the task branch.

Container layout (`<container>/wts/<repo>/` for the main worktree, `<container>/wts/<slug>/` for task worktrees, `<container>/portals/` for cross-worktree junctions, `<container>/wiki/` for the wiki clone, `<container>/codeguide/` for codeguide):

```text
c:/Code/millhouse/                ← container, named after the repo
  wts/                            ← all worktrees
    millhouse/                    ← main worktree, named after repo
    <slug>/                       ← task worktrees, named after slug
  wiki/                           ← wiki clone
  codeguide/                      ← codeguide clone
  portals/                        ← junctions to all task worktrees
    millhouse -> ../wts/millhouse
    <slug>    -> ../wiki/active/<slug>/
```

Inside each worktree:

```text
c:/Code/millhouse/wts/<slug>/
  plugins/                        ← (only meaningful in main worktree)
  ... (rest of repo files)
  .millhouse/
    active.slug.md
    config.local.yaml
  .wiki   -> ../../wiki/              ← junction to wiki clone
  .active -> ../../wiki/active/<slug>/← junction to wiki state dir for this task
  task/                           ← per-task working state, on the branch
    status.md
    discussion.md
    plan/
    reviews/
```

## Constraints

Hard rules — violation causes silent bugs or breaks external repos using mill as a plugin.

- **Junctions and hardlinks are NEVER used by scripts or skills.** `.wiki`, `.active`, `tasks.md`, and any other junction or hardlink exist solely for operator IDE/terminal navigation. Scripts always resolve real paths programmatically via `_paths.py`. Never pass a junction path to a Python helper or reference one in a SKILL.md instruction.
- **`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths.** Never hardcode `plugins/mill/…` — external repos have no millhouse source checkout.
- **Working state is never written to the wiki.** `status.md`, `discussion.md`, `plan/`, `reviews/` live on the task branch. The wiki holds only `Home.md` and `config.yaml`.

---

## Review terminology

These terms are used throughout the review subsystem and in any design discussion about mill.

| Term | Meaning |
|---|---|
| **Frontend** | The orchestrator — the caller (e.g. a `mill-go` session in Claude Code). |
| **API** | The three review CLI scripts: `millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py`. |
| **Backend** | Everything behind the API — templates, bulking, file-writing, reviewer dispatch, verdict parsing, ReviewResult assembly. Lives in `_review_*.py` + `_review_common.py`. |
| **Reviewer** | A named strategy module (simple LLM, cluster, round-switching hybrid). Declares a module-level `MODE` constant (`"bulk"` or `"tool-use"`) and exposes `run(prompt_text, *, session_id=None, resume=False) -> tuple[str, str]`. File pattern: `_reviewer_<name>.py`. |
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
- Task worktrees live under `<container>/wts/`; portal junctions under `<container>/portals/`.

## Conventions worth carrying

- **Plugin scripts reference `${CLAUDE_PLUGIN_ROOT}`, never the source repo.** Anything installed via plugin manifest — `plugins/mill/`, `plugins/codeguide/`, etc. — runs on a user's machine that has no millhouse source checkout. Every intra-plugin path in a SKILL.md, Python helper, or prompt template must resolve against `${CLAUDE_PLUGIN_ROOT}`, not against `plugins/<name>/…`. This is load-bearing for external repos where CC uses mill/codeguide plugins without the millhouse source being cloned anywhere.
- **In operational Bash commands typed at the agent level, never reference `plugins/mill/...` or `plugins/codeguide/...` source-tree paths. Use `${CLAUDE_PLUGIN_ROOT}` (which resolves to the cache). Tests run as `python plugins/mill/unit_tests/...` are the sole exception, and only when explicitly invoked from a test runner.**

  ```bash
  # WRONG — invokes from source tree
  uv run --project plugins/mill plugins/mill/scripts/millpy-spawn.py

  # RIGHT — invokes from cache
  uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-spawn.py"
  ```
- **Mill scripts are invoked via `uv run`, not `python`.** All SKILL.md examples use `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py" [args]`; inline helpers use `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."`. PYTHONPATH is set globally as a Windows user environment variable by `mill-setup` Phase 4.7. This takes effect in **new shell sessions opened after mill-setup completes**. Within the same session, and on some Windows configurations, the Bash tool subshell may not inherit it — prefix inline `uv run python -c` calls with `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` if you see `ModuleNotFoundError`. Exception: `mill-setup` itself is the bootstrapper and uses an inline `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` prefix on each call. Similarly, `${CLAUDE_PLUGIN_ROOT}` may be empty in some Bash subshells (observed on Windows VS Code's integrated terminal); when empty, hardcode the cache path the user supplies, or fall back to `plugins/mill/` source-tree paths only when running from the millhouse repo itself — never assume the env var resolves at runtime.
- **Generated markdown uses fenced ```yaml for metadata**, not `---` frontmatter. `---` is reserved for `SKILL.md` and plugin manifests. (See `plugins/mill/skills/markdown/SKILL.md`.)
- **Reviews match the tight v1 style**: per-finding = severity-label + 3–4 short bullets. Target a few hundred tokens total, not thousands. The fix-thread has full context and does not need narrative explanation.
- **Loading `mill-receiving-review` is mandatory** before reading any review output. See `plugins/mill/skills/mill-receiving-review/SKILL.md`.

## Path invariants

Path rules that keep being forgotten — they live here, not spread across SKILL.md files.

- **Junctions are IDE/terminal convenience only.** Scripts MUST resolve to the real wiki repo via `_paths.resolve_wiki_path(git_toplevel)`, never by treating `.wiki` (or any junction) as a path. Junctions exist so the operator can type shorter paths in a shell and see the wiki in the sidebar — they are not a code contract. (The same invariant is documented in `wiki/config.yaml`'s header comment.)
- **NTFS junctions are followed by `rmdir /s` and `shutil.rmtree`.** Any recursive deletion targeting a worktree path must call `_junction.strip_all_in_worktree(worktree, junctions_cfg)` first. Skipping this wipes the wiki, the portals dir, or sibling worktrees through the junctions mill-spawn placed inside every worktree (`.wiki`, `.active`, plus any future entries). `git worktree remove --force` is junction-safe by itself, but the long-path fallback (`cmd /c rmdir /s /q`, `shutil.rmtree`) is not. See GitHub issue #100.
- **All path resolution goes through `_paths.py`.** The module re-exports `resolve_path` from `_sibling.py` (identical-twin with codeguide's copy per spec 00) and adds `resolve_git_root` + `resolve_wiki_path`. New helpers: `resolve_hub_relative_path(worktree_root, hub_subpath)` for cwd-as-hub resolution (reads `hub_relative_path:` from `.millhouse/config.local.yaml`); `resolve_active_worktree(container, slug, *, cfg, git_root)` for slug-to-worktree lookup; `resolve_active_hub(container, slug, *, cfg, git_root)` for slug-to-hub lookup (handles in-place mode and sub-dir hub configs). New path-resolver helpers go here too — do not scatter private `_resolve_*` functions across `millpy-*.py` CLI scripts.
- **Slug-to-path resolution goes through `resolve_active_worktree` / `resolve_active_hub`.** Any code that needs "the worktree directory for a given slug" calls `_paths.resolve_active_worktree(container, slug, *, cfg, git_root)`. Any code that needs "where `.millhouse/` and `task/` live for a given slug" calls `_paths.resolve_active_hub(container, slug, *, cfg, git_root)`. Both helpers detect in-place mode (hub IS the worktree, no `<container>/wts/<slug>/` directory) and sub-dir hub configs (`hub_relative_path != "."`). Inline `container / "wts" / slug` constructions are banned outside `_paths.py`; inline `<wt> / hub_relative_path` arithmetic is banned outside `_paths.resolve_hub_relative_path`. `discover_active_worktrees`-style enumerations of `<container>/wts/` are exempt — they enumerate, not slug-resolve.
- **`_sibling.resolve_path` detects container-form via `repo_root.parent.name == "wts"`.** Container-form returns `parent.parent / role` (sibling of `wts/`). Prefix-form returns `parent / f"{repo_root.name}.{role}"`. Old hub-form (`repo_root.name == "hub"`) is no longer recognised — migrate first.
- **Working state lives in `task/` on the task branch.** `task/status.md`, `task/discussion.md`, `task/plan/`, and `task/reviews/` are committed to the task branch, not written to the wiki. The wiki holds only the task index (`Home.md`) and shared config (`config.yaml`). mill-merge's cleanup commit removes the `task/` directory before squash-merging back to the parent branch.
- **Scratch lives at `<cwd>/.scratch/`, not under `.millhouse/`.** Shared with other plugins the engineer uses that default to top-level `.scratch/`. `.gitignore` covers it via `**/.scratch/`. Never write to `/tmp/` or `$env:TEMP`. (See `plugins/mill/skills/conversation/SKILL.md` for the full file-writing conventions.)
