# v1 Reuse — what to lift from millpy

```yaml
status: draft
depends-on: 00-overview
source-path: C:\Code\millhouse-legacy\
source-repo: https://github.com/Knatte18/millhouse-legacy
```

**Use the local path.** GitHub lookup is slow and requires fetching files one-by-one. The local clone at `C:\Code\millhouse-legacy\` has everything immediately available with grep/read. The GitHub URL is listed for reference only (in case the local clone goes stale or someone else is working on this).

## Purpose

Not everything in v1 is bad. Several components work reliably, were built with care, and would be wasteful to rewrite. This document lists what should be carried over (with or without modification) and what should NOT.

**Rule:** Lifting code from v1 is a *deliberate* act. Read the source, understand it, copy it to v2, simplify if possible, then delete any Python-package scaffolding (imports, bootstrap, package structure).

---

## ✅ Carry over with minimal changes

### `millpy/core/subprocess_util.py` → `scripts/_subprocess_util.py`

**Why:** Robust subprocess runner with logging and timeout handling. Used by every entrypoint.

**Changes:** Drop imports from `millpy.core.log_util`. Replace log calls with `print(..., file=sys.stderr)`.

### `millpy/core/junction.py` → `scripts/_junction.py`

**Why:** Cross-platform junction/symlink abstraction. Already has Windows junction support with the Python 3.10+ fallback (FILE_ATTRIBUTE_REPARSE_POINT) that we added during this conversation.

**Changes:** Drop `millpy.core.log_util`. Inline `_MODULE` constant or delete.

### `millpy/tasks/wiki.py` lock + commit/push helpers → `scripts/_wiki.py`

**Why:** Wiki lock (`.wiki-lock`) with retry/backoff is subtle and we got it right. Write/commit/push sequence is also battle-tested.

**Changes:** Strip out the v1-specific event logging. Keep `acquire_lock`, `release_lock`, `write_commit_push` as plain functions.

### Markdown parsing helpers for tasks.md / Home.md

**Why:** The `## <slug>` heading parser handles edge cases (empty sections, trailing whitespace, BOM). Reinventing it is a 2-day job.

**Location in v1:** `millpy/tasks/tasks_md.py`

**Changes:** Extract the parser as a standalone function. Drop the dataclass hierarchy. One function, returns `list[dict]`.

### Verdict extraction

**Why:** v1's `millpy/core/verdict.py` handles three formats (YAML frontmatter, JSON last-line, legacy `VERDICT:` prefix). We might not need all three in v2 — but if we end up supporting both Claude and Gemini outputs, this logic is useful.

**Changes:** Pick the format we want (YAML frontmatter recommended). Delete the other branches. ~30 LOC total.

### `millpy/core/config.py` — the YAML parser

**Why:** `_parse_yaml_mapping` is a pure-stdlib YAML parser for simple mappings. Avoids pulling in PyYAML for small config files.

**Changes:** If PyYAML is acceptable, just use it and delete v1's parser. Otherwise, copy the function.

### Plan validator

**Why:** v1's `millpy/core/plan_validator.py` has sensible checks (card numbers unique, required fields present). The v2 plan format is simpler than v1's, so the validator simplifies too.

**Changes:** Strip it down to match v2's plan format. ~50 LOC max.

---

## ⚠️ Reference but rewrite

These worked but are coupled to v1's package structure enough that cleanest to rewrite.

### Stream-json parsing for Claude CLI

**v1 location:** `millpy/backends/claude.py`

**Why rewrite:** It's tangled with the WorkerExecResult / ReviewerResult types and the BulkResult / ToolUseResult split. Cleaner to write fresh against the stream-json format.

**Lift:** The actual event-parsing logic (which event types to watch, how to extract final text) is informative. Read it as reference.

### Junction + worktree setup sequence

**v1 location:** `millpy/entrypoints/spawn_task.py`, `millpy/entrypoints/worktree.py`

**Why rewrite:** Setup order is subtle (copy config.local.yaml before creating junctions; mkdir `.millhouse/` before creating subdirs). v1 got the order right but the code is spread across multiple functions. Rewrite for clarity, reference v1 for sequence.

### Gemini API client

**v1 has a minimal Gemini client** in `millpy/backends/gemini.py`. It's bulk-only (no tool-use). For v2 we need tool-use, so rewrite. Reference for auth/endpoint URLs.

---

## ❌ Do NOT carry over

### Package infrastructure

- `millpy/` as a package — no, we're flat scripts
- `__init__.py` files — no
- `_bootstrap.py` sys.path hacks — no, use PYTHONPATH env or `sys.path.insert(0, ...)` at top of each script (minimal)
- `entrypoints/` with argparse + `main(argv=None)` — no, each script has its own `if __name__ == "__main__":` block

### Abstractions

- `Worker` / `Cluster` dataclasses
- `SingleWorker` / `ClusterReviewer` classes
- `Reviewer` Protocol
- Anything with ABCs or inheritance

### Test infrastructure

- `conftest.py`, pytest fixtures
- `tests/integration/`, `tests/core/`, etc. — 645 tests is the cautionary tale
- Any `fake_*` or `mock_*` infrastructure

### Multi-format plan handling

- Plan v1 vs v2 vs v3 logic
- `plan_io.resolve_plan_path()` fallback chain
- Plan format version detection

v2 has one plan format.

### Ensemble/handler complexity

- `millpy/reviewers/cluster.py`
- `millpy/reviewers/handler.py`
- Bulk-payload construction for multi-worker
- Handler-prep logic

Ensemble is a separate script in v2 (post-v2.0), not a core concept.

### Legacy fallback paths

- `_millhouse/task/` vs `.mill/active/<slug>/` dual-path logic
- `resolve_plan_path()` trying multiple locations
- Legacy `config.yaml` fallback to `_millhouse/config.yaml`

v2 has one canonical location for each artefact. If a file isn't where it should be, error.

### `millpy/tasks/status_md.py`

Too coupled to the v1 wiki-path detection logic (the one that broke silently during rename). Rewrite against the v2 canonical paths.

### Skills files

v1 skills are over-long and reference many bespoke helpers. v2 skills should be shorter (~50 lines each) and call the scripts directly. Reference v1 skills for the workflow steps, not the text.

### Codeguide skills — split out into own plugin, but keep mill as the trigger

In v1 codeguide is `codeguide-setup`, `codeguide-update`, `codeguide-generate`, `codeguide-maintain` skills living inside `plugins/mill/skills/`. v2 promotes these into their own plugin at `plugins/codeguide/`.

**How v1 arrived at the current pattern:** an even earlier attempt used git-hooks to auto-update codeguide. That was dropped long ago. v1 as it stands has no hooks — mill's git-commit skill explicitly invokes `codeguide-update` as part of its workflow. v2 keeps this pattern, just now as a cross-plugin reference (`@codeguide:codeguide-update` instead of a local skill call).

**For v2, at Layer 04:**

1. Create `plugins/codeguide/` with its own `.claude-plugin/plugin.json`
2. Copy `codeguide-*` skill files from legacy `plugins/mill/skills/` into `plugins/codeguide/skills/`
3. Update mill's `git-commit/SKILL.md` to invoke `@codeguide:codeguide-update` instead of a local skill
4. Test: `/mill-add some-task` → commit → git-commit skill triggers codeguide-update via cross-plugin reference

Git-* skills (`git-commit`, `git-pr`, `git-workflow`) stay inside mill — they're general git workflow, not codeguide-specific. Port from legacy with minimal adjustment.

**Why split codeguide out:**
- Other projects could theoretically use codeguide without mill
- Cleaner plugin boundaries
- Mill becomes smaller (fewer skills to maintain inside one plugin)

**Why keep mill as the trigger (not codeguide-owned auto-update):**
- v1 proved auto-update is unreliable
- Commit-time is the right moment to update docs — mill owns commits, so mill owns the timing

---

## Estimated reuse volume

| Category | v1 LOC | v2 LOC (after trim) |
|---|---|---|
| subprocess_util | 80 | 50 |
| junction | 120 | 90 |
| wiki (lock + write_commit_push) | 200 | 120 |
| tasks.md parser | 150 | 60 |
| verdict extraction | 100 | 30 |
| YAML mapping parser (if we skip PyYAML) | 50 | 40 |
| plan validator | 100 | 50 |
| **Total carried** | ~800 | ~440 |

So roughly 440 LOC comes "for free" via copy-and-clean. That's ~30% of the total v2.0 budget (1500 LOC), reducing what we actually need to write to ~1060 LOC of new code.

## Process for each reuse

1. Open the v1 file in `C:\Code\millhouse-legacy\plugins\mill\scripts\millpy\...`
2. Read it end-to-end
3. Copy only the functions/logic you need into the v2 target file
4. Delete all imports from other `millpy.*` modules
5. Replace those dependencies with stdlib equivalents or inline helpers
6. Delete any log/debug infrastructure, replace with `print(..., file=sys.stderr)` if needed
7. Delete type annotations that reference v1 classes (or replace with dict/str/Path)
8. Run the v2 smoke test for that layer
9. Commit with a clear message: `reuse: carry <function> from v1 <file>`
