# CLAUDE.md — mill-v2 project conventions

```yaml
repo: millhouse (v2 rewrite)
scope: this file is read on session start; keep it short
```

## Environment

The harness reports `Shell: PowerShell` environment metadata,
but the Bash tool always uses a POSIX shell regardless.
Emit POSIX syntax in Bash tool calls (`$null` no -- use `2>/dev/null`, `[ -f x ]`, `for x in ...`), and reserve PowerShell syntax for the PowerShell tool.

## Project shape

`mill-v2` — plugin-based task/review/orchestration system.
Wiki (sibling clone) owns the task index.
Working state lives in `_mill/` on the task branch.

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

- **Junctions are IDE/terminal only.**
  Scripts always resolve real paths via `_paths.py`.
  Never pass `.wiki`, `.active`, or any junction to a Python helper or SKILL.md command.
- **`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths.**
  Never `plugins/mill/…` — external repos have no millhouse checkout.
  Write `${CLAUDE_PLUGIN_ROOT}` literally in Bash tool calls — do NOT read or memorize its value;
  let the shell expand it at runtime.
- **Task-worktree path for source verification, not CLAUDE_PLUGIN_ROOT.**
  Reading actual source code to verify plan/discussion accuracy — the code a plan is about to edit, as distinct from invoking a script — must target the task-worktree path, never the plugin cache.
  In this self-hosted repo (millhouse developing millhouse), the cache and the worktree can silently diverge;
  reading stale cache content during plan-writing has previously produced an incorrect conclusion requiring mid-plan rework. `${CLAUDE_PLUGIN_ROOT}` remains correct for script invocation — this bullet narrows only the source-code-verification case, it does not revise the bullet above it.
- **Working state never goes to wiki.** `_mill/` lives on the task branch.
  Wiki holds only `Home.md`.
- **Never cite `_mill/discussion.md` (or any other `_mill/`-rooted path) from a permanent doc.**
  A permanent/roadmap doc (e.g. a wiki Done entry or a module doc) that links to `_mill/discussion.md` is unsafe: `_mill/` is deleted or restored-from-base at merge time (`mill-finalize` Step 3 / `mill-merge` Step 4's cleanup commit), so the file no longer exists on the parent branch once the task merges.
- **Fold only into unclaimed backlog tasks** (`status is None AND not deferred`).
  Claimed, terminal, blocked, or deferred tasks reject fold-ins — guard inlined in `millpy-fold.py` and the two fold SKILLs.

## Script invocation

Cache form (all operational calls):

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py"
```

Exceptions: unit tests use `uv run --project plugins/mill`;
mill-setup keeps the full path (bootstrapper — it writes `MILL_PYTHON` to `~/.claude/settings.json` via Phase 4.8);
nested calls after `--` in millpy-bg inherit PYTHONPATH automatically and must not carry the prefix. `$MILL_PYTHON` is now the standard form for all other mill skills.

**Verify command shape.**
For Python/mill projects: Plan files' `verify:` commands MUST start with `PYTHONPATH=` (literal, empty value, single space) so the test subprocess does not inherit the cache `PYTHONPATH` and load V2-cache modules instead of worktree code.
For non-Python projects (e.g. Go, C#): use the native test runner directly without the prefix.
Enforced conditionally by `_plan_validate.py`'s `verify-not-isolated` check based on the presence of Python markers (`pyproject.toml`, `setup.py`, `setup.cfg`);
mill-plan auto-prepends the prefix on validator failure for Python projects.

## Conventions

- Generated markdown: fenced ` ```yaml ` for metadata — not `---` frontmatter (`---` is for SKILL.md and plugin manifests).
- Reviews: tight v1 style — per-finding = severity-label + 3–4 short bullets.
  Target a few hundred tokens.
- Load `mill-receiving-review` skill before reading any review output.
- `print()` / `_log()` output: ASCII only (`—` -> ` -- `, `->` -> ` -> `).
  Windows cp1252 crashes on non-ASCII stdout.
- `mill-config.yaml` hub file and plugin template must stay in sync — template seeds new hubs.
- `CLAUDE_PLUGIN_ROOT` always resolves to the plugin cache entry, never the dev tree.
  Use it for all intra-plugin paths.
- Ad-hoc `dotnet build`/`dotnet test` (when `csharp-build` isn't loaded): pass `--nologo -clp:ErrorsOnly` and never pipe the gating invocation to `grep`/`tail` — it masks dotnet's exit code.
- Ad-hoc Python lint/format checks (when a project-specific `python-build` override isn't in place): use `uvx ruff check .` — an ephemeral, non-project-mutating invocation.
  Never use `uv add`/`uv sync` to install a lint tool for a one-off check.
- **Never use `sed`** — in this repo or any script/prompt it generates for a dispatched sub-agent (implementer/reviewer/fixer).
  It triggers a permission prompt on every invocation, which blocks unattended/autonomous runs.
  Use `Edit`/`Read`/`Write`, or `awk`/`grep`/plain `cat` for a genuine one-liner.

## Review terminology

| Term | Meaning |
|---|---|
| **Frontend** | The orchestrator (mill-go session in Claude Code) |
| **API** | `millpy-review-{discussion,plan,code}.py` CLI scripts |
| **Backend** | `_review_*.py` + `_review_common.py` — templates, bulking, dispatch, verdict parsing |
| **Reviewer** | Named strategy; declares `MODE` (`"bulk"` / `"tool-use"`); exposes `run(prompt_text, *, session_id=None, resume=False) -> tuple[str, str]` |
| **LLM-provider** | Thin wrapper — no review semantics, just send/receive text |
| **prompt_text** | Fully-rendered prompt string built by backend from template + tokens + bulked file content |

Review severity: `discussion` → GAP/NOTE → APPROVE/GAPS_FOUND;
`plan`/`code` → BLOCKING/NIT → APPROVE/REQUEST_CHANGES.

## Repo layout

- `plugins/mill/scripts/` — flat Python;
  `millpy-*.py` CLIs + `_*.py` helpers;
  `wiki/` subpackage is the deliberate V3 module exception;
  `_daemon.py` is a generic daemon base reusable by future V3 modules
- `plugins/mill/templates/` — review-prompt templates + `review-output.schema.md`
- `plugins/mill/skills/` — one `SKILL.md` per skill;
  indexed at root `SKILLS.md`
- `plugins/mill/unit_tests/` — `test-<name>.py`;
  run via `run-all.py`.
  In-memory/tempfile fixtures;
  no real git/LLM.
- `plugins/mill/integration_tests/` — invokes real git and optionally real claude;
  uses `.scratch/` for fixtures.
- `.millhouse/` — gitignored local state;
  `.scratch/` — gitignored scratch (never `/tmp/` or `$env:TEMP`)

## Path invariants

- **Recursive deletion: strip junctions first.**
  Call `_junction.strip_all_in_worktree(worktree, junctions_cfg)` before any `rmdir /s` or `shutil.rmtree`.
  Skipping wipes wiki/portals through junctions.
- **All path resolution through `_paths.py`.** `resolve_wiki_path`, `resolve_active_worktree`, `resolve_active_hub`.
  No inline `container / "wts" / slug` outside `_paths.py`;
  no inline `<wt> / hub_relative_path` outside `_paths.resolve_hub_relative_path`.
- **`_sibling.resolve_path`** detects container-form via `repo_root.parent.name == "wts"`;
  prefix-form is everything else.
  Old hub-form no longer recognised.
- **Helpers with path args must not consult cwd for config.**
  Thread the explicit path to inner lookups (bug surface: test helpers reading caller's mill-config.yaml instead of fixture's).
- **cwd is never changed to wiki.**
  Scripts halt with `SystemExit` if cwd is inside the wiki clone.
  Mutations go through `git -C <wiki_path>` or `_wiki.write_commit_push`.

## Wiki access

| Anti-pattern | Correct |
|---|---|
| `cd .wiki/ && git pull` | `_wiki.sync_pull(wiki_path)` |
| `cd .wiki/ && git <anything>` | `git -C <wiki_path> <anything>` |
| `cd .wiki/ && cat <file>` | `read_text(wiki_path / "<file>")` |
| `cwd=<wiki_path>` in subprocess | `cwd=<task_worktree>` + `git -C <wiki_path>` |

Mutations only through `_wiki.write_commit_push` or `git -C <wiki_path>` inside `_wiki.wiki_lock`.
