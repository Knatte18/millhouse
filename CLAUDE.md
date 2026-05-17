# CLAUDE.md — mill-v2 project conventions

```yaml
repo: millhouse (v2 rewrite)
scope: this file is read on session start; keep it short
```

## Project shape

`mill-v2` — a plugin-based task/review/orchestration system for Claude Code. Wiki repo (sibling clone) owns the task index and shared config. Working state (`_mill/status.md`, `_mill/discussion.md`, `_mill/plan/`, `_mill/reviews/`) lives in the `_mill/` subdirectory on the task branch.

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
    <slug>    -> ../wts/<slug>/_mill/
```

Inside each worktree:

```text
c:/Code/millhouse/wts/<slug>/
  plugins/                        ← (only meaningful in main worktree)
  ... (rest of repo files)
  .millhouse/
    config.local.yaml
  .wiki    -> ../../wiki/              ← junction to wiki clone
  .active  -> ../../portals/<slug>/    ← junction to portal entry for this task
  .portals -> ../../portals/           ← junction to all portals
  _mill/                           ← per-task working state, on the branch
    status.md
    discussion.md
    plan/
    reviews/
```

## Constraints

Hard rules — violation causes silent bugs or breaks external repos using mill as a plugin.

- **Junctions and hardlinks are NEVER used by scripts or skills.** `.wiki`, `.active`, `tasks.md`, and any other junction or hardlink exist solely for operator IDE/terminal navigation. Scripts always resolve real paths programmatically via `_paths.py`. Never pass a junction path to a Python helper or reference one in a SKILL.md instruction.
- **`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths.** Never hardcode `plugins/mill/…` — external repos have no millhouse source checkout.
- **Working state is never written to the wiki.** `_mill/status.md`, `_mill/discussion.md`, `_mill/plan/`, `_mill/reviews/` live on the task branch. The wiki holds only `Home.md`.
- **Folding scope into a Home.md task entry** — via `/mill-fold` or the fold-in branch of `/mill-ghissues-to-tasks` — is forbidden when the target's phase marker is `[active]`, `[ready-to-merge]`, or `[pr-pending]`. The plan was committed at spawn time and scope additions silently invalidate it. Phase tuple lives at `_tasks_md.LOCKED_FOLD_PHASES`; both skills import it. Personal memory is NOT a valid place for this rule — it must travel with the repo.

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
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-spawn.py"
  ```
- **Mill scripts are invoked via the cache venv's Python binary directly, not via `uv run --project`.** Cache-form SKILL.md blocks use `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py" [args]`; inline helpers use `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "..."`. The `PYTHONPATH=` prefix is required because the Bash subshell does not reliably inherit the global Windows user env var that `mill-setup` Phase 4.7 sets. The venv at `${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe` is created and maintained by `update-plugins.ps1` when the plugin is installed or upgraded. **Exception (source-tree form):** when running from the millhouse repo itself (e.g. unit tests, or when `${CLAUDE_PLUGIN_ROOT}` is unset in some Bash subshells observed in Windows VS Code's integrated terminal), use `uv run --project plugins/mill plugins/mill/scripts/millpy-X.py` or the inline `PYTHONPATH="plugins/mill/scripts" uv run --project plugins/mill python -c "..."` form — `uv run` will create the source-tree venv on demand. **Exception (mill-go):** mill-go's body calls use `"$MILL_PYTHON"` (an alias to `${PLUGIN_ROOT}/.venv/Scripts/python.exe`) defined in its Step 0 block. **Exception (nested calls):** Python invocations that appear after `--` inside a `millpy-bg.py` launcher line MUST NOT carry the `PYTHONPATH=` prefix — tokens after `--` are passed as argv to a subprocess; the outer launcher already set PYTHONPATH in the process environment, which is inherited automatically.
- **Generated markdown uses fenced ```yaml for metadata**, not `---` frontmatter. `---` is reserved for `SKILL.md` and plugin manifests. (See `plugins/mill/skills/markdown/SKILL.md`.)
- **Reviews match the tight v1 style**: per-finding = severity-label + 3–4 short bullets. Target a few hundred tokens total, not thousands. The fix-thread has full context and does not need narrative explanation.
- **Loading `mill-receiving-review` is mandatory** before reading any review output. See `plugins/mill/skills/mill-receiving-review/SKILL.md`.
- **Template `mill-config.yaml` is the canonical config schema.** When changing a config key in `mill-config.yaml` at the hub repo root, mirror the change in `plugins/mill/templates/mill-config.yaml` -- the template ships with the plugin and seeds new hubs via mill-setup. Drift means new hubs are seeded with a stale schema. The hub-root file is the source of truth for valid schema; the template is the source of truth for the documentation comments inside the file (overlay precedence, env-var registry).
- **All `print()` and `_log()` output strings use ASCII only.** Em-dash (`—`) -> ` -- `; right-arrow (`->`) -> ` -> `. Docstrings and comments are exempt. Windows cp1252 terminals crash on non-ASCII stdout/stderr.
- **`CLAUDE_PLUGIN_ROOT` resolution on directory-source marketplaces:** The `.claude-plugin/marketplace.json` uses relative source paths (`./plugins/mill`, etc.) to enable directory-source mode for development. When CC loads plugins in directory-source mode, it sets a Process-level `CLAUDE_PLUGIN_ROOT` environment variable pointing to the dev tree, overriding the User-level `CLAUDE_PLUGIN_ROOT` set by `update-plugins.ps1`. This is expected behavior: directory-source mode is intended for local development. If scripts must use cache paths, either run from a process with an explicit `CLAUDE_PLUGIN_ROOT` override (e.g., `$env:CLAUDE_PLUGIN_ROOT=$target; invoke-expression $script`), or switch to cache-based installation by removing relative source paths from the marketplace.

## Path invariants

Path rules that keep being forgotten — they live here, not spread across SKILL.md files.

- **Junctions are IDE/terminal convenience only.** Scripts MUST resolve to the real wiki repo via `_paths.resolve_wiki_path(git_toplevel)`, never by treating `.wiki` (or any junction) as a path. Junctions exist so the operator can type shorter paths in a shell and see the wiki in the sidebar — they are not a code contract. (The same invariant is documented in `mill-config.yaml`'s header comment.)
- **NTFS junctions are followed by `rmdir /s` and `shutil.rmtree`.** Any recursive deletion targeting a worktree path must call `_junction.strip_all_in_worktree(worktree, junctions_cfg)` first. Skipping this wipes the wiki, the portals dir, or sibling worktrees through the junctions mill-spawn placed inside every worktree (`.wiki`, `.active`, plus any future entries). `git worktree remove --force` is junction-safe by itself, but the long-path fallback (`cmd /c rmdir /s /q`, `shutil.rmtree`) is not. See GitHub issue #100.
- **All path resolution goes through `_paths.py`.** The module re-exports `resolve_path` from `_sibling.py` (identical-twin with codeguide's copy per spec 00) and adds `resolve_git_root` + `resolve_wiki_path`. New helpers: `resolve_hub_relative_path(worktree_root, hub_subpath)` for cwd-as-hub resolution (reads `hub_relative_path:` from `.millhouse/config.local.yaml`); `resolve_active_worktree(container, slug, *, cfg, git_root)` for slug-to-worktree lookup; `resolve_active_hub(container, slug, *, cfg, git_root)` for slug-to-hub lookup (handles in-place mode and sub-dir hub configs). New path-resolver helpers go here too — do not scatter private `_resolve_*` functions across `millpy-*.py` CLI scripts.
- **Slug-to-path resolution goes through `resolve_active_worktree` / `resolve_active_hub`.** Any code that needs "the worktree directory for a given slug" calls `_paths.resolve_active_worktree(container, slug, *, cfg, git_root)`. Any code that needs "where `.millhouse/` and `_mill/` live for a given slug" calls `_paths.resolve_active_hub(container, slug, *, cfg, git_root)`. Both helpers detect in-place mode (hub IS the worktree, no `<container>/wts/<slug>/` directory) and sub-dir hub configs (`hub_relative_path != "."`). Inline `container / "wts" / slug` constructions are banned outside `_paths.py`; inline `<wt> / hub_relative_path` arithmetic is banned outside `_paths.resolve_hub_relative_path`. `discover_active_worktrees`-style enumerations of `<container>/wts/` are exempt — they enumerate, not slug-resolve.
- **`_sibling.resolve_path` detects container-form via `repo_root.parent.name == "wts"`.** Container-form returns `parent.parent / role` (sibling of `wts/`). Prefix-form returns `parent / f"{repo_root.name}.{role}"`. Old hub-form (`repo_root.name == "hub"`) is no longer recognised — migrate first.
- **Working state lives in `_mill/` on the task branch.** `_mill/status.md`, `_mill/discussion.md`, `_mill/plan/`, and `_mill/reviews/` are committed to the task branch, not written to the wiki. The wiki holds only the task index (`Home.md`). mill-merge's cleanup commit removes the `_mill/` directory before squash-merging back to the parent branch.
- **Scratch lives at `<cwd>/.scratch/`, not under `.millhouse/`.** Shared with other plugins the engineer uses that default to top-level `.scratch/`. `.gitignore` covers it via `**/.scratch/`. Never write to `/tmp/` or `$env:TEMP`. (See `plugins/mill/skills/conversation/SKILL.md` for the full file-writing conventions.)
- **cwd is always cwd, and scripts never rewrite it.** Wiki mutations go through `git -C <wiki_path>` or `_wiki.write_commit_push` — never by changing cwd to wiki. If a script detects cwd is inside the wiki clone, it halts with a clear `SystemExit` (or `ValueError` for `_sibling.resolve_path`): that is operator error, not something to recover from. Enforced by `_paths.resolve_git_root` (name + path-equality check), `_paths.resolve_wiki_path` (name check), and `_sibling.resolve_path` (name check; mirrored to the codeguide twin). Regression-guarded by `plugins/mill/unit_tests/test-no-wiki-cwd.py`.
- **Helpers that take a path argument MUST NOT consult cwd for config.** Route the explicit path through to any inner config lookup. The bug surface is unit-test helpers that read the caller's mill-config.yaml instead of the fixture's. Already fixed in main during the config-move-to-hub squash via `_wiki.read_junctions(wiki_path=...)` / `_wiki.read_hardlinks(wiki_path=...)` accepting an optional `wiki_path` argument; `_setup.create_hub_links` now uses `target_root` as `hub_root` and threads `wiki_path` through (#318).

## Wiki access

Scripts mutate the wiki only through `_wiki.write_commit_push` or `git -C <wiki_path>` inside a `_wiki.wiki_lock` block. Reads go through helper APIs (`_wiki.sync_pull`) or `read_text(wiki_path / …)`. Never `cd` into the wiki, never set `cwd=<wiki_path>` in a subprocess.

| Anti-pattern | Correct replacement |
|---|---|
| `cd .wiki/ && git pull --ff-only` | `_wiki.sync_pull(wiki_path)` |
| `cd .wiki/ && git <anything>` | `git -C <wiki_path> <anything>` |
| `cd .wiki/ && cat <file>` | `read_text(wiki_path / "<file>")` |
| `cwd=<wiki_path>` in subprocess | `cwd=<task_worktree>` + `git -C <wiki_path>` |
