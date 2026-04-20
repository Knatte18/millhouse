# Layer 01 — Bootstrap

```yaml
status: draft
depends-on: 00-overview
delivers:
  - skill: mill-setup
  - script: mill-add
  - script: mill-list
  - helpers: _junction, _wiki, _subprocess_util
loc-budget: 450   # ~90 for scripts + ~330 for lifted helpers + 30 new
```

## Goal

Get the minimum viable infrastructure working: wiki clone + tasks list + `.millhouse/` local state. After this layer, a user can initialise a fresh machine and add/list tasks. Nothing else.

## What this layer does NOT do

- No task spawning (no worktree creation)
- No reviewers
- No plans
- No claiming tasks
- No orchestration

## v1 reuse for this layer

Before writing new code, lift these from `C:\Code\millhouse-legacy\plugins\mill\scripts\millpy\`:

| v1 source | v2 target | What to take |
|---|---|---|
| `core/subprocess_util.py` | `scripts/_subprocess_util.py` | The `run()` function with timeout + logging. Drop all `millpy.core.log_util` imports. |
| `core/junction.py` | `scripts/_junction.py` | Both `create()` and `remove()` (incl. the Python 3.10 FILE_ATTRIBUTE_REPARSE_POINT fallback). |
| `tasks/wiki.py` | `scripts/_wiki.py` | `acquire_lock()`, `release_lock()`, `write_commit_push()`. Strip v1 event logging. |
| `tasks/tasks_md.py` | Inline into `mill-list.py` / `mill-add.py` | The `## <slug>` heading parser. Extract as one function returning `list[dict]`. |
| `core/config.py` | Inline into each script that reads config | Just the YAML load (use PyYAML, skip v1's `_parse_yaml_mapping` unless avoiding dependency matters). |
| `skills/mill-setup/SKILL.md` | `skills/mill-setup/SKILL.md` | **Reference heavily.** Lift the setup phases (order: derive wiki URL → clone → junction → config) and conflict-handling branches. Drop v1's orphan-tasks-branch era steps. |
| `entrypoints/spawn_task.py` lines 260–290 | Reference for `mill-setup` skill | Setup-sequence order (mkdir → junction → config copy). The skill describes these steps; no Python script implements them. |

See `ref-v1-reuse.md` for the full lifting protocol.

## Deliverables

### 1. `mill-setup` — initialise mill in a fresh clone (SKILL, not script)

`mill-setup` is a **skill**, not a Python script. Setup has many edge cases (wiki already exists vs doesn't, private repo auth, partial prior setup, Windows junction vs POSIX symlink, conflicting existing files) that need judgment. A script would either be rigid or grow to 500+ lines of condition handling. A skill lets Claude inspect state, ask clarifying questions, and pick the right action.

**Invocation:** User runs `/mill-setup` in a Claude Code session from `C:\Code\millhouse\hub\` (or equivalent primary clone).

**What the skill does (high-level):**

1. Detect git remote URL of current clone → derive wiki URL (`<repo>.wiki.git`)
2. Check if `../wiki/` already exists:
   - Valid clone of the wiki repo: skip clone, just verify junctions
   - Something else: stop and ask the user
   - Not present: `git clone <wiki-url> ../wiki`
3. Create `.millhouse/` directory structure (layout per `ref-formats.md`)
4. Call `_junction.py create` helper to make `.millhouse/wiki` → `../../wiki`
5. Copy `plugins/mill/templates/config.local.yaml` → `.millhouse/config.local.yaml` if missing
6a. Initialise `wiki/_Sidebar.md` via `_sidebar.regenerate(wiki_path)` — this produces a sidebar with just the Navigation section on a fresh wiki (no tasks yet), and populates the Tasks section as soon as `mill-add` runs. Commit + push alongside any other Phase 6 wiki changes.

6. Initialise `wiki/Home.md` if needed:
   - **Missing:** write minimal Home.md from template and commit/push.
   - **GitHub-default content** (file matches the literal pattern `Welcome to the <repo> wiki!` followed by optional whitespace — exactly what GitHub creates when the user clicks "Create the first page" with no edits): overwrite from template and commit/push. This is safe because no human ever wrote this content; GitHub did.
   - **Already in v2 shape** (first non-blank line is `# Tasks`): skip.
   - **Anything else** (custom user content): skip with a warning that the wiki Home.md is non-standard and `mill-add` may behave unexpectedly. Do not overwrite — user content is sacred.
7. Verify the setup end-to-end; print summary
8. **VS Code window colour for the hub** — write `.vscode/settings.json` from `templates/vscode-settings.json` with:
   - `<COLOR_HEX>` → `#2d7d46` (the canonical "main = green" invariant; mill-spawn picks non-green colours per worktree in M3.1)
   - `<WINDOW_TITLE>` → just `<short-name>`, derived from the origin URL (the repo name without the `.git` suffix). Example: `millhouse`. Deliberately short — must be readable in the Windows 11 taskbar at small sizes. No `${activeEditorShort}` or other VS Code variables; the active file changes constantly and the title should not.

   Behaviour:
   - File missing → create.
   - File present with `titleBar.activeBackground == "#2d7d46"` → no-op (idempotent).
   - File present with a non-green colour → back up to `.vscode/settings.json.bak`, then overwrite from template.

**Idempotent:** re-running produces no changes if already set up.

**Helper scripts the skill uses:**
- `plugins/mill/scripts/_junction.py` (create/remove junctions)
- `plugins/mill/scripts/_wiki.py` (acquire_lock, write_commit_push) — for Home.md init
- `plugins/mill/scripts/_vscode.py` (`render_settings`, `write_settings`) — VS Code workspace settings; shared with `mill-spawn` (M3.1) for worktree colours
- `plugins/mill/scripts/_render.py` — used transitively by `_vscode` and `_wiki`
- `plugins/mill/templates/config.local.yaml` — copied verbatim
- `plugins/mill/templates/Home.md` — initial wiki landing page (also used to normalise GitHub-default Home.md)
- `plugins/mill/templates/vscode-settings.json` — VS Code colour + title template (consumed by `_vscode`)

**Exit criteria:**
- `.millhouse/wiki` junction exists and points at the wiki clone
- `wiki/Home.md` exists and starts with `# Tasks`
- `wiki/_Sidebar.md` exists with Navigation + Tasks sections
- `.millhouse/config.local.yaml` exists
- `.vscode/settings.json` exists with `titleBar.activeBackground == "#2d7d46"`

**Deferred to M2 (when `wiki/config.yaml` first lands):**
- Prompt user for `repo.short-name` (default: derived from origin URL initials), store in `wiki/config.yaml`. Used by `_vscode.py` for window titles instead of the current "take last URL segment" heuristic.

### 2. `mill-add` — add a task to the wiki tasks list

**Arguments:**
```
mill-add <slug> --title "Human-readable title" [--summary "..."] [--proposal-body "..."]
```

**Behaviour:**
- Open `.millhouse/wiki/Home.md`
- Append a new task section: `## <title> [<slug>]` (or `[[<slug>]](proposal-<slug>)` if `--proposal-body` given)
- If `--proposal-body` given: write `wiki/proposal-<slug>.md` with the long-form content
- Regenerate `wiki/_Sidebar.md` from the updated Home.md (via `_sidebar.py`)
- Commit Home.md + _Sidebar.md (+ proposal-<slug>.md if present) in **one commit** under one wiki-lock acquisition
- Acquire/release wiki lock (`.mill-lock` with retry, per `_wiki.py`)

**Task format in Home.md:**

Without proposal:
```markdown
## <Human-readable title> [<slug>]

<summary, ~1 paragraph>
```

With proposal:
```markdown
## <Human-readable title> [[<slug>]](proposal-<slug>)

<summary, ~1 paragraph>
```

The double-bracket syntax keeps `[<slug>]` visible in rendered output while making it a link to `proposal-<slug>.md` at wiki root. Flat namespace because GitHub Wiki does not reliably render subdirectory pages — see `ref-formats.md`.

That's it. No statuses, no metadata in the heading. Statuses come later in Layer 03 or 04 when tasks get claimed and have lifecycle.

### 2.5 `mill-add` skill (M1.3.5)

`plugins/mill/skills/mill-add/SKILL.md` — thin skill that wraps `mill-add.py` for the *long-discussion* case. Workflow:

1. User has a discussion with Claude that ends "log this as a task".
2. Claude (via the skill) decides:
   - A short slug (kebab-case, derived from the agreed-upon topic)
   - A title (one-line human-readable)
   - A summary (~1 paragraph) for Home.md
   - Whether the discussion produced enough background to warrant a `proposal-<slug>.md` (heuristic: >150 words or >3 paragraphs of substantive content)
3. Claude calls `mill-add.py <slug> --title "..." --summary "..."` (with optional `--proposal-body "..."` if step 2 said so).
4. The script handles wiki lock, commit, push, sidebar regen.

Skill is judgment-heavy (deciding slug, title, when to extract proposal). Script is mechanical (write files, commit, push).

### 3. `_sidebar.py` — regenerate `_Sidebar.md`

Helper used by `mill-add` (M1.3) and `mill-setup` (M1.2). Layer 04 commands (`mill-merge`, `mill-abandon`, `mill-groom`) call it too once they land.

API:
```python
def parse_home_tasks(home_path: Path) -> list[dict]:
    """Return list of {slug, title, has_proposal} parsed from Home.md."""

def render_sidebar(tasks: list[dict]) -> str:
    """Build _Sidebar.md content: Navigation section first, Tasks section after."""

def regenerate(wiki_path: Path) -> None:
    """Read Home.md, scan for proposal-*.md files, write _Sidebar.md."""
```

Tasks with a proposal get a link in the sidebar (`[<title>](proposal-<slug>)`); tasks without get plain text.

### 3. `mill-list` — list tasks from Home.md

**Arguments:** none

**Behaviour:**
- Read `.millhouse/wiki/Home.md`
- Parse `## <slug>` headings
- Print one line per task: `<slug> — <first line of description>`
- Exit 0

## File layout for this layer

```
plugins/mill/
  scripts/
    mill-add.py          # ~60 LOC (writes Home.md, commits via _wiki)
    mill-list.py         # ~30 LOC (parses Home.md, prints)
    _junction.py         # ~120 LOC (lifted from v1 with Python 3.10 fallback)
    _wiki.py             # ~150 LOC (lifted from v1 — lock + commit/push)
    _subprocess_util.py  # ~60 LOC (lifted from v1)
  templates/
    config.local.yaml
    Home.md              # template used when wiki is empty
  skills/
    mill-setup/SKILL.md  # full skill — setup is judgment-heavy
    mill-add/SKILL.md    # thin skill — wraps mill-add.py
    mill-list/SKILL.md   # thin skill — wraps mill-list.py
  integration_tests/
    test-bootstrap.ps1   # single end-to-end: setup → add → list
```

**No `mill-setup.py`.** Setup is a skill because it needs judgment. Other CLIs are scripts because they're mechanical.

## Acceptance criteria

After this layer ships, the user can:

1. Clone a fresh repo to `C:\Code\myproject\hub\`
2. Run `/mill-setup` in Claude Code — Claude creates `.millhouse/`, clones wiki, creates junctions
3. Run `python plugins/mill/scripts/mill-add.py foo --description "do foo"` — task appears in wiki
4. Run `python plugins/mill/scripts/mill-list.py` — `foo — do foo` prints
5. On a second machine, clone the repo, run `mill-setup` again → wiki pulls, `mill-list` shows `foo`

## Design decisions locked in this layer

- **Wiki is a separate git clone.** Not a submodule, not a junction target in the main repo.
- **Config is split:** `wiki/config.yaml` (shared, tracked in wiki) + `.millhouse/config.local.yaml` (local secrets, gitignored).
- **Home.md is the tasks file.** No separate `tasks.md`. The wiki's landing page IS the tasks list.
- **Wiki lock is a file, not a DB.** `.wiki-lock` in the wiki root. Retry with backoff. No transaction semantics.

## Open questions (to resolve before coding)

- [ ] Do we need a wiki-lock at all for v2.0, or is "don't run two mill commands simultaneously" a user-level rule?
- [ ] Should `mill-setup` also create worktrees/ directory, or lazy-create on first worktree?
- [ ] Is `Home.md` format a markdown-like `## <slug>` or YAML frontmatter blocks? (spec says markdown, user to confirm)

## Non-goals for Layer 01 (pushed to later layers)

- Worktree creation (Layer 03 or 04)
- Branch management (Layer 03 or 04)
- Status lifecycle (Layer 04)
- Config validation (handled implicitly by scripts erroring on missing keys)
