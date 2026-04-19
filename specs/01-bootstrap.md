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

See `06-v1-reuse.md` for the full lifting protocol.

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
3. Create `.millhouse/` directory structure (layout per `05-formats.md`)
4. Call `_junction.py create` helper to make `.millhouse/wiki` → `../../wiki`
5. Copy `plugins/mill/templates/config.local.yaml` → `.millhouse/config.local.yaml` if missing
6. If `wiki/Home.md` doesn't exist: write minimal Home.md from template and commit/push
7. Verify the setup end-to-end; print summary

**Idempotent:** re-running produces no changes if already set up.

**Helper scripts the skill uses:**
- `plugins/mill/scripts/_junction.py` (create/remove junctions)
- `plugins/mill/scripts/_wiki.py` (acquire_lock, write_commit_push) — for Home.md init
- `plugins/mill/templates/config.local.yaml` — copied verbatim
- `plugins/mill/templates/Home.md` — initial wiki landing page

**Exit criteria:**
- `.millhouse/wiki` junction exists and points at the wiki clone
- `wiki/Home.md` exists
- `.millhouse/config.local.yaml` exists

### 2. `mill-add` — add a task to the wiki tasks list

**Arguments:**
```
mill-add <slug> [--description "..."]
```

**Behaviour:**
- Open `.millhouse/wiki/Home.md`
- Append a new task section with the given slug and description
- Commit + push to wiki repo
- Acquire/release wiki lock (simple `.lock` file with retry)

**Task format in Home.md:**
```markdown
## <slug>

<description>
```

That's it. No statuses, no metadata. Statuses come later in Layer 03 or 04 when tasks get claimed and have lifecycle.

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
