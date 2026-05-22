# CLAUDE.md — mill-v2 project conventions

```yaml
repo: millhouse (v2 rewrite)
scope: this file is read on session start; keep it short
```

## Project shape

`mill-v2` — plugin-based task/review/orchestration system. Wiki (sibling clone) owns the task index. Working state lives in `_mill/` on the task branch.

Container layout:

```text
c:/Code/millhouse/               ← container
  wts/
    millhouse/                   ← main worktree (hub)
    <slug>/                      ← task worktrees
  wiki/                          ← wiki clone
  codeguide/                     ← codeguide clone
  portals/
    millhouse -> ../wts/millhouse
    <slug>    -> ../wts/<slug>/_mill/
```

Inside each worktree:

```text
.millhouse/config.local.yaml
.wiki    -> ../../wiki/
.active  -> ../../portals/<slug>/
.portals -> ../../portals/
_mill/   ← status.md, discussion.md, plan/, reviews/
```

## Hard constraints

- **Junctions are IDE/terminal only.** Scripts always resolve real paths via `_paths.py`. Never pass `.wiki`, `.active`, or any junction to a Python helper or SKILL.md command.
- **`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths.** Never `plugins/mill/…` — external repos have no millhouse checkout. Write `${CLAUDE_PLUGIN_ROOT}` literally in Bash tool calls — do NOT read or memorize its value; let the shell expand it at runtime.
- **Working state never goes to wiki.** `_mill/` lives on the task branch. Wiki holds only `Home.md`.
- **No fold into `[active]`/`[ready-to-merge]`/`[pr-pending]` tasks.** Phase tuple at `_tasks_md.LOCKED_FOLD_PHASES`.

## Script invocation

Cache form (all operational calls):

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py"
```

Exceptions: unit tests use `uv run --project plugins/mill`; mill-setup keeps the full path (bootstrapper — it writes `MILL_PYTHON` to `~/.claude/settings.json` via Phase 4.8); nested calls after `--` in millpy-bg inherit PYTHONPATH automatically and must not carry the prefix. `$MILL_PYTHON` is now the standard form for all other mill skills.

## Conventions

- Generated markdown: fenced ` ```yaml ` for metadata — not `---` frontmatter (`---` is for SKILL.md and plugin manifests).
- Reviews: tight v1 style — per-finding = severity-label + 3–4 short bullets. Target a few hundred tokens.
- Load `mill-receiving-review` skill before reading any review output.
- `print()` / `_log()` output: ASCII only (`—` -> ` -- `, `->` -> ` -> `). Windows cp1252 crashes on non-ASCII stdout.
- `mill-config.yaml` hub file and plugin template must stay in sync — template seeds new hubs.
- `CLAUDE_PLUGIN_ROOT` in directory-source mode points to the dev tree (expected); switch to cache-based install to use the cache path.

## Review terminology

| Term | Meaning |
|---|---|
| **Frontend** | The orchestrator (mill-go session in Claude Code) |
| **API** | `millpy-review-{discussion,plan,code}.py` CLI scripts |
| **Backend** | `_review_*.py` + `_review_common.py` — templates, bulking, dispatch, verdict parsing |
| **Reviewer** | Named strategy; declares `MODE` (`"bulk"` / `"tool-use"`); exposes `run(prompt_text, *, session_id=None, resume=False) -> tuple[str, str]` |
| **LLM-provider** | Thin wrapper — no review semantics, just send/receive text |
| **prompt_text** | Fully-rendered prompt string built by backend from template + tokens + bulked file content |

Review severity: `discussion` → GAP/NOTE → APPROVE/GAPS_FOUND; `plan`/`code` → BLOCKING/NIT → APPROVE/REQUEST_CHANGES.

## Repo layout

- `plugins/mill/scripts/` — flat Python (no submodules); `millpy-*.py` CLIs + `_*.py` helpers
- `plugins/mill/templates/` — review-prompt templates + `review-output.schema.md`
- `plugins/mill/skills/` — one `SKILL.md` per skill; indexed at root `SKILLS.md`
- `plugins/mill/unit_tests/` — `test-<name>.py`; run via `run-all.py`. In-memory/tempfile fixtures; no real git/LLM.
- `plugins/mill/integration_tests/` — invokes real git and optionally real claude; uses `.scratch/` for fixtures.
- `.millhouse/` — gitignored local state; `.scratch/` — gitignored scratch (never `/tmp/` or `$env:TEMP`)

## Path invariants

- **Recursive deletion: strip junctions first.** Call `_junction.strip_all_in_worktree(worktree, junctions_cfg)` before any `rmdir /s` or `shutil.rmtree`. Skipping wipes wiki/portals through junctions.
- **All path resolution through `_paths.py`.** `resolve_wiki_path`, `resolve_active_worktree`, `resolve_active_hub`. No inline `container / "wts" / slug` outside `_paths.py`; no inline `<wt> / hub_relative_path` outside `_paths.resolve_hub_relative_path`.
- **`_sibling.resolve_path`** detects container-form via `repo_root.parent.name == "wts"`; prefix-form is everything else. Old hub-form no longer recognised.
- **Helpers with path args must not consult cwd for config.** Thread the explicit path to inner lookups (bug surface: test helpers reading caller's mill-config.yaml instead of fixture's).
- **cwd is never changed to wiki.** Scripts halt with `SystemExit` if cwd is inside the wiki clone. Mutations go through `git -C <wiki_path>` or `_wiki.write_commit_push`.

## Wiki access

| Anti-pattern | Correct |
|---|---|
| `cd .wiki/ && git pull` | `_wiki.sync_pull(wiki_path)` |
| `cd .wiki/ && git <anything>` | `git -C <wiki_path> <anything>` |
| `cd .wiki/ && cat <file>` | `read_text(wiki_path / "<file>")` |
| `cwd=<wiki_path>` in subprocess | `cwd=<task_worktree>` + `git -C <wiki_path>` |

Mutations only through `_wiki.write_commit_push` or `git -C <wiki_path>` inside `_wiki.wiki_lock`.
