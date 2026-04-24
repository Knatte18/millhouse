# Batch 2: cli

```yaml
batch: 2
name: cli
cards: 3
depends_on: [foundation]
```

## Scope

Implement `mill-status.py` in two cards (data assembly first, table rendering second), then add an integration test. The CLI reads from wiki + git; no wiki writes.

## Cards

### Card 3a: data assembly + `--json`

**Creates:** `plugins/mill/scripts/mill-status.py`

**Requirements:**

**Args:**
- `--json` — emit JSON array; no color, no truncation.
- `--no-color` — disable color even when stdout is a TTY (parsed here; applied in 3b).
- `--sort {slug,phase}` — default `slug` (parsed here; applied in 3b).

**Data assembly:**

1. `git_root = _paths.resolve_git_root()`; `wiki = _paths.resolve_wiki_path(git_root)`.
2. If `wiki / "Home.md"` exists, read its text then parse: `home_tasks = {t.slug: t for t in _tasks_md.parse(text)}`. If missing, `home_tasks = {}`.
3. Enumerate `wiki / "active" /` dirs → set of active-dir slugs.
4. For each active-dir slug call `_status.read_status(wiki / "active" / slug / "status.md")`. On `ValueError` mark that slug with `phase="unreadable"` and all other fields `None`.
5. Call `_worktree.list_worktrees(git_root)` → build `{slug: path}`:
   - Skip entry if `entry["branch"] is None`.
   - Skip entry if `not entry["branch"].startswith("impl/")`.
   - Derive slug: `entry["branch"][len("impl/"):]`.
   - This correctly excludes the main worktree (`main` branch) and detached-HEAD entries.
6. Union all slugs from steps 2, 3, 5. For each slug build a row dict:
   - `slug`: the slug string.
   - `title`: from `read_status["task"]` if active-dir present, else from `home_tasks[slug].title` if in Home.md, else `None`.
   - `phase`: from `read_status["phase"]` if active-dir present; `None` if slug only in Home.md (backlog task, no active-dir); `None` if only in worktree with no active-dir.
   - `marker`: `home_tasks[slug].phase if home_tasks[slug].phase is not None else "unclaimed"` for slugs in Home.md; `"missing"` for slugs with no Home.md entry. Legacy `"abandoned"` markers from `_tasks_md` pass through verbatim.
   - `marker_flag`:
     - `"WT?"` when marker is `"active"` and slug not in worktree map.
     - `"HM?"` when active-dir exists but slug has no Home.md entry.
     - `""` otherwise. Spawn-ready (`"s"`) tasks with no worktree get no flag — a worktree is created at spawn time, not at task-creation time; `[s]` + no worktree is normal.
   - `worktree_path`: path string from worktree map, or `"-"`.
   - `current_batch`: from read_status or `None`.
   - `last_timeline_entry`: from read_status or `None`.
   - `blocked_reason`: from read_status or `None`.

**JSON output** (when `--json`):

Emit `json.dumps(rows, indent=2)` where each row is the dict above with `null` for `None` values. Print to stdout and exit 0.

**Exit code**: 0 always.

**Commit:** `feat: mill-status.py — data assembly + json output`

---

### Card 3b: table rendering + color + sort

**Modifies:** `plugins/mill/scripts/mill-status.py`

**Requirements:**

**Sort** (applied before rendering):
- Default (`--sort slug`): alphabetical by slug.
- `--sort phase`: order by phase priority index: `blocked=0, implementing=1, reviewing=2, fixing=3, planning=4, discussed=5, discussing=6`. Phases not in the map use sort key `("z", phase or "")` so they sort last — `None` → `("z", "")` which sorts before `("z", "foo")` for any non-empty string.

**Table columns** (in order): `SLUG | TITLE | PHASE | MARKER | WORKTREE | BATCH | LAST EVENT | BLOCKED`

- `TITLE`: truncate to 40 chars with `…`; `"-"` when `None`.
- `PHASE`: rendered as `—` when `None` (backlog tasks). Color applied only to this cell (see below). Always plain text before ANSI wrapping.
- `MARKER` rendered cell: `marker + (" " + marker_flag if marker_flag else "")`. Always plain text — no ANSI codes in this cell ever.
- `WORKTREE`: no truncation; `"-"` when absent.
- `LAST EVENT`: truncate to 40 chars with `…`; `"-"` when `None`.
- `BLOCKED`: no truncation; `"-"` when `None`.
- `BATCH`: `-` when `None`.

**Column width calculation** (must happen before rendering, using plain text values):
- For each column: `width = max(len(header), max(len(rendered_cell) for all rows))`.
- TITLE and LAST EVENT: use the truncated form (≤41 chars incl. `…`) when computing width.
- MARKER: `len(marker) + (1 + len(marker_flag) if marker_flag else 0)`.
- ANSI codes are added after width calculation and must NOT contribute to width math.

**Table layout:**
- Header row: each header left-aligned, padded to column width; columns separated by `" | "`.
- Separator row: dashes (`-`) of column width, separated by `-+-`.
- Data rows: each cell left-aligned, padded to column width.

**Color** (applied to PHASE cell only; enabled when `sys.stdout.isatty()` and `--no-color` not given; never in `--json` mode):
- `blocked` → `\033[31m` (red)
- `implementing` / `reviewing` / `fixing` → `\033[33m` (yellow)
- `done` → `\033[32m` (green)
- `unreadable` → `\033[35m` (magenta)
- `abandoned` → no color (legacy v2-unproduced value; pass through as plain text)
- All other phases including `None`/`—` → no color
- Reset with `\033[0m` immediately after the colored text.

**Commit:** `feat: mill-status.py — table rendering, color, sort`

---

### Card 4: integration test

**Creates:** `plugins/mill/integration_tests/test-status.py`

**Reads:** `plugins/mill/integration_tests/test-cleanup.py` (pattern reference)

**Requirements:**

- Use `.scratch/test-status-<timestamp>/` as fixture root. Clean up on success; leave in place on failure.
- Fixture status files: use `_status.render_initial(...)` to produce `status.md` content so the files include a Timeline block. This exercises the `last_timeline_entry` parsing path.
- Fixture: a minimal hub repo (default branch `main`) + wiki repo. Write `.millhouse/config.local.yaml` in the hub repo pointing to the wiki path (same as `test-cleanup.py` lines 148–150) so `_paths.resolve_wiki_path` finds the fixture wiki. Wiki has `Home.md` and `active/<slug>/status.md` for five slugs:
  1. `slug-alpha`: `[active]` in Home.md + active-dir with `render_initial`-rendered `status.md` + registered worktree on branch `impl/slug-alpha`.
  2. `slug-beta`: `[done]` in Home.md + active-dir with rendered `status.md` + no worktree.
  3. `slug-gamma`: `[active]` in Home.md + active-dir with rendered `status.md` + no worktree (triggers `WT?`).
  4. `slug-delta`: active-dir with rendered `status.md` + no Home.md entry + no worktree (triggers `HM?`).
  5. `slug-echo`: Home.md entry only (unclaimed, no marker — heading `## Echo task [slug-echo]`, no phase bracket) + no active-dir + no worktree (backlog task).
- Assertions:
  - Plain run (`python mill-status.py`): exit code 0; stdout contains all five slugs; `WT?` on `slug-gamma`; `HM?` on `slug-delta`; `slug-alpha` row shows worktree path; `slug-echo` row shows `—` in PHASE column.
  - `--json` run: exit code 0; parse JSON; all five slugs present; `slug-gamma` has `marker_flag == "WT?"`; `slug-delta` has `marker_flag == "HM?"`; `slug-echo` has `phase == null`, `marker_flag == ""`, and `marker == "unclaimed"`; `slug-alpha` has `worktree_path != "-"` and not `null`; `slug-alpha` has non-`null` `last_timeline_entry` (Timeline block present via `render_initial`).
  - `--sort phase` run: exit code 0; non-empty output; no crash.
  - Main worktree guard: in `--json` output, no row has `slug == "main"`.
- Print `PASS: ...` per assertion group.

**Commit:** `test(integration): test-status.py for mill-status`
