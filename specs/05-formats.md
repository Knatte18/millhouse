# Formats — canonical list

```yaml
status: draft
depends-on: 00-overview
```

## Goal

Enumerate every format v2 uses, in one place. Prevent the format-sprawl that plagued v1 (plan-v1/v2/v3, three status shapes, inconsistent review outputs).

## Directory layouts (non-negotiable)

These are not "formats" in the template sense, but they are structural contracts. Scripts and skills assume them; changing them is a breaking change.

### `C:\Code\<project>\` (the container)

```
<project>\
  hub\                      ← primary clone (any branch)
  wiki\                     ← wiki clone (separate git repo)
  worktrees\<slug>\         ← one per active task
```

`<project>\` itself is NOT a git repo. It holds three peers.

### `.millhouse/` (inside every working clone)

Either in `hub\.millhouse/` or in each `worktrees/<slug>/.millhouse/`. Exact same shape in both.

**Organised into 5 groups, each with a purpose:**

```
<working-clone>/
  .env                              # [GROUP 0] secrets at repo root (dotenv convention)
  .millhouse/
    # [GROUP 1: task identity — topmost for visibility, dot-prefix sorts to top]
    .active     -> <wiki>/active/<slug>/   # junction; only when task is active
    .<slug>.slug.md                        # task-identity file; only when task is active

    # [GROUP 2: user-invoked scripts — the mill-* wrappers]
    mill-add.py
    mill-abandon.py
    mill-cleanup.py
    mill-go.py
    mill-list.py
    mill-merge.py
    mill-plan.py
    mill-review.py
    mill-spawn.py
    mill-start.py
    mill-status.py
    # (plus any user-added helper scripts)

    # [GROUP 3: config]
    config.local.yaml                      # worktree-local overrides (not secrets)

    # [GROUP 4: junctions to shared state]
    wiki        -> <container>/wiki        # always present after mill-setup

    # [GROUP 5: ephemeral]
    scratch/                               # briefs, prompts, review snapshots — safe to delete anytime
```

**Why this order (alphabetical within each group):**

When you open `.millhouse/` in a file explorer alphabetically:
- Dot-prefixed task-identity items appear first (if a task is active) — acts as a header telling you what this worktree is doing
- `config.local.yaml` appears before `mill-*` alphabetically
- `mill-*` scripts grouped together, easy to scan
- `scratch/` and `wiki` at the bottom — you rarely browse into them manually

No subfolders for scripts or config — kept flat so paths stay short (`.millhouse/mill-add.py` is shorter than `.millhouse/scripts/mill-add.py`).

**Dot-prefix convention:** `.active` and `.<slug>.slug.md` are prefixed with `.` so they appear at the top when the directory is listed alphabetically (Windows Explorer, `dir`, typical IDE file tree). Acts as a visual header: when you open `.millhouse/` you see the task identity first.

On Linux/Mac, `ls` hides dotfiles by default — use `ls -a`. Mill-v2 is Windows-primary, so this is a minor concern.

**.env vs config.local.yaml:**

- **`.env`** (at repo root, not inside `.millhouse/`) — *secrets only.* API keys (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`), OAuth tokens. Loaded as environment variables via python-dotenv or equivalent. Shape: `KEY=value` per line. Never YAML, never structured. **At repo root because that's the universal `.env` convention** — any tool expecting to find `.env` will look there.
- **`config.local.yaml`** (inside `.millhouse/`) — *non-secret overrides* of values in the shared `wiki/config.yaml`. Per-worktree or per-machine preferences: notifications on/off, a user's preferred model when multiple worktrees share the same repo, worktree-specific pipeline overrides. Must be valid YAML in the same shape as `wiki/config.yaml` (partial overlay).

Both are gitignored. `.env` explicitly via `.env` line in `.gitignore`. `config.local.yaml` implicitly because `.millhouse/` is ignored.

**Per-worktree:** each worktree has its own `.env` and `.millhouse/config.local.yaml`. `mill-spawn` copies them from the hub on worktree creation. Worktrees can diverge (rare) if the user edits them locally.

**Wrapper scripts (`.millhouse/mill-*.py`):**

Required. Created by `mill-setup` (one per CLI: `mill-add.py`, `mill-list.py`, `mill-spawn.py`, `mill-go.py`, etc.). They are thin forwarders that:

1. Locate the installed `millhouse` plugin in the Claude Code plugin cache (`~/.claude/plugins/cache/millhouse/mill/<version>/scripts/`).
2. Import the real script module from there.
3. Call its `main()` with the current `sys.argv`.

Why wrappers exist:
- Users run `python .millhouse/mill-add.py foo` — short and worktree-local, no need to know plugin-cache paths.
- Wrappers resolve the current plugin version automatically (so an upgrade takes effect without editing the wrapper).
- They let CLIs work from both `hub/` and any `worktrees/<slug>/` without path gymnastics.

A wrapper template lives at `plugins/mill/templates/wrapper.py`. `mill-setup` copies it for each CLI, substituting the target entrypoint.

**Rules:**

- `.millhouse/` is gitignored by the project repo (`**/.millhouse/` in `.gitignore`). Its contents are local, except the `wiki` and `active` junctions which point at content that IS tracked (in the wiki repo).
- `wiki` junction is mandatory after `mill-setup`. Scripts fail loudly if missing.
- `active` junction is only present when a task is claimed in this worktree. `mill-spawn` creates it; `mill-cleanup` removes it.
- `.<slug>.slug.md` mirrors the `active` junction: only exists when a task is active.
- `scratch/` never goes in git. Never commit anything from here.
- Wrapper scripts (`mill-*.py`) are optional convenience — they forward to the real scripts in `plugins/mill/scripts/`. Not all users need them.

### `wiki/` (the shared wiki repo)

```
wiki/
  Home.md                   # task list (active + un-started; where abandoned tasks return to)
  _Sidebar.md               # navigation sidebar (regenerated)
  config.yaml               # shared config (models registry, pipeline choices)
  proposals/                # long-form task backgrounds — extracted from Home.md when bodies grow long
    <slug>.md               # one per task that has a proposal
  active/<slug>/            # owned by the worktree working on <slug>
    status.md
    discussion.md           # after mill-start
    plan.md                 # after mill-plan
    <slug>-result.md        # after mill-go (filename TBD per plan-format decision)
    reviews/<timestamp>-<type>-r<N>.md
  archive/<slug>/            # mill-merge moves active/<slug>/ → archive/<slug>/ (done tasks only)
  .wiki-lock                # transient lock file — ONLY for writes to shared resources
```

**Task outcome semantics:**

| Outcome | Home.md | active/<slug>/ | archive/<slug>/ |
|---|---|---|---|
| **merged / done** (`mill-merge`) | entry removed (task is finished) | moved to archive | gets the content |
| **abandoned** (`mill-abandon`) | entry restored (task re-enters backlog) | deleted from tree (preserved in git history) | unchanged |

Why the asymmetry: "done" produces lasting output worth keeping as reference (plan, reviews, decisions). "Abandoned" means we changed direction — the artefacts are not reference material, just dead ends. If needed, they're recoverable from wiki git history.

- Wiki is a git repo. Every write commits and pushes.
- Top-level directories: `active/` (in progress) and `archive/` (completed history). Abandoned tasks appear in neither — they're back in `Home.md`.

**Wiki lock scope:**

`.wiki-lock` is held ONLY when writing to shared-across-tasks resources:

- `Home.md` — multiple tasks may be added concurrently
- `config.yaml` — shared config
- `_Sidebar.md` — regenerated from multiple sources

Per-task writes (anything under `active/<slug>/`) do NOT acquire the lock. Each task's files are logically single-writer — only the worktree working on `<slug>` writes to `active/<slug>/`. Git push handles the final ordering; no in-process coordination needed.

This matters: it means two operators on different tasks can run mill commands simultaneously without blocking each other, as long as they're not both touching Home.md or config.yaml.

- `.wiki-lock` is gitignored; if it lingers, something crashed mid-operation.

---

## Format inventory

| Name | File pattern | Template | Schema | Used by |
|---|---|---|---|---|
| **Home.md** | `wiki/Home.md` | `templates/Home.md` | `templates/Home.schema.md` | mill-add, mill-list, mill-groom |
| **proposal.md** | `wiki/proposals/<slug>.md` | — (free-form markdown) | `templates/proposal.schema.md` (minimal) | mill-groom |
| **config.local.yaml** | `.millhouse/config.local.yaml` | `templates/config.local.yaml` | `templates/config.schema.md` | all |
| **config.yaml** | `wiki/config.yaml` | `templates/config.yaml` | `templates/config.schema.md` | all |
| **status.md** | `wiki/active/<slug>/status.md` | `templates/status.md` | `templates/status.schema.md` | mill-spawn, mill-go, mill-start, mill-plan, mill-merge, mill-abandon |
| **slug.md** | `.millhouse/.<slug>.slug.md` | `templates/slug.md` | `templates/slug.schema.md` | mill-spawn, mill-status |
| **discussion.md** | `wiki/active/<slug>/discussion.md` | — (free-form) | `templates/discussion.schema.md` | mill-start, mill-plan |
| **plan.md** | `wiki/active/<slug>/plan.md` | `templates/plan.md` | `templates/plan.schema.md` | mill-plan, mill-go |
| **review-prompt-<type>.md** | `templates/review-prompt-<type>.md` | self | `templates/review-prompt.schema.md` | mill-review |
| **review-output.md** | `wiki/active/<slug>/reviews/<ts>-<type>-r<N>.md` | `templates/review-output.md` | `templates/review-output.schema.md` | mill-review |
| **implementer-brief.md** | `.millhouse/scratch/implementer-brief-card-<n>.md` | `templates/implementer-brief.md` | `templates/implementer-brief.schema.md` | mill-go, mill-start, mill-plan |
| **result.md** (placeholder) | `wiki/active/<slug>/<result-file>.md` | `templates/result.md` | `templates/result.schema.md` | mill-go (written by implementer) |

**Total: 12 canonical formats.** No additions without a spec change.

## Format details

### Home.md

The wiki landing page IS the task list. Each task is an `## <slug>` heading with a free-text body.

**Canonical shape:**

```markdown
# Tasks

## <slug-in-kebab-case>

<short description — ideally one paragraph, max ~150 words>

[Background →](proposals/<slug>)     <!-- auto-inserted when body is extracted -->

## <another-slug>

<description>

---

## Archive

(Optional section listing archived slugs with links to archive/<slug>/)
```

**Rules (enforced by `Home.schema.md`):**

- One `## <slug>` heading per task
- Slug: kebab-case, unique within Home.md, matches `[a-z][a-z0-9-]*`
- Body: free-form markdown, but should be short. Long descriptions are extracted (see below).
- No status markers on tasks in `Home.md`. A task's state is communicated by which directory it lives in (`active/<slug>/` exists = in progress; `archive/<slug>/` exists = done; neither = just a backlog entry here).

### Home.md — long-description handling

You can author a task by writing it straight into `Home.md` with a long prose body (requirements, constraints, options considered). A skill then tidies it:

**Skill: `mill-groom`** (lifted from v1 with this mechanism)

What it does:
1. Scan Home.md for all task sections
2. For each task whose body exceeds a threshold (default 150 words or 3 paragraphs):
   a. Extract the full body to `wiki/proposals/<slug>.md` (preserving markdown formatting)
   b. Generate a short summary (first paragraph, or Claude-summarised)
   c. Replace the Home.md body with: the summary + `[Background →](proposals/<slug>)`
3. Commit Home.md + proposals/<slug>.md together, push

This means you can do:

```markdown
## refactor-parser

The current parser uses regex but we've hit edge cases where regex backtracking
causes O(n²) behaviour. Consider switching to a proper lexer/parser combo:

- Option A: hand-written recursive descent (bigger code, total control)
- Option B: parser-generator (PLY, Lark) — easier but adds a dep

We also need to handle the new syntax from RFC-42 which the current parser
can't even parse at all. See discussion in issue #89.
```

And after running `mill-groom`:

```markdown
## refactor-parser

Switch the parser off regex due to backtracking issues and RFC-42 support gap.

[Background →](proposals/refactor-parser)
```

With the full original body now living at `wiki/proposals/refactor-parser.md`.

**When to run:** any time Home.md feels cluttered. There's no automatic trigger; you invoke the skill manually (`/mill-groom`).

### wiki/proposals/

```
wiki/proposals/
  <slug>.md        # long-form background for task <slug>
```

- One file per task that has a proposal
- Markdown, no required schema (free-form)
- Referenced from Home.md as `[Background →](proposals/<slug>)`
- When a task is merged or abandoned, the proposal stays (archived along with the task's active state)

### status.md

Single source of truth for a task's phase.

```markdown
```yaml
task: <slug>
created: <iso-8601>
phase: discussing | planning | planned | implementing | reviewing | done
# note: no "abandoned" phase — abandonment deletes the status file entirely and returns task to Home.md
last_updated: <iso-8601>
```

# Status: <slug>

## Timeline

```text
discussing  <iso-8601>
planning    <iso-8601>
...
```
```

Phase is the *only* lifecycle state. No sub-states. Transitions are written by the skill that caused them.

### plan.md

Flat list of cards. No batches, no layers.

```markdown
```yaml
task: <slug>
created: <iso-8601>
approved: <iso-8601 | null>
```

# Plan: <task-title>

## Card 1: <short title>

**Reads:** paths/a, paths/b
**Modifies:** paths/c
**Verify:** pytest tests/test_c.py
**Commit:** fix: add c

<implementation notes in prose, as many paragraphs as needed>

## Card 2: ...
```

Validation rules (in `plan.schema.md`):
- At least one `## Card N:` heading
- Card numbers are unique and sequential
- Each card has `Reads:`, `Modifies:`, `Verify:`, `Commit:` fields
- Only `Reads:` may be empty; `Modifies:` and `Commit:` are required

### review-output.md

```markdown
```yaml
verdict: APPROVE | REQUEST_CHANGES
reviewer_model: <model-id>
reviewed_file: <path>
date: <iso-8601>
```

# Review: <artefact-name>

## Findings

### [BLOCKING] <short title>
**Section:** <section or line ref>
**Issue:** <description>
**Suggested fix:** <what to do>

### [NIT] <short title>
...

## Verdict

<APPROVE | REQUEST_CHANGES>
<one-sentence summary>
```

### implementer-brief.md

```markdown
```yaml
task: <slug>
card: <n>
plan_hash: <git-sha of plan.md at brief time>
```

# Implementer Brief — Card <n>

## Task
<task title + description>

## Card content
<copied from plan.md>

## Reads
- paths/a
- paths/b

## Modifies (expected)
- paths/c

## Verify
<command>

## Commit
<message>

## Output contract
Write `wiki/active/<slug>/cards/card-<n>-result.md` with:
- YAML frontmatter: `status: PASS | FAIL`
- Any notes worth preserving
```

### card-result.md

```markdown
```yaml
card: <n>
status: PASS | FAIL
commits: [<sha1>, <sha2>]
duration_seconds: <int>
```

# Card <n> Result

<implementer's notes — what was done, what was tricky, what's left for follow-up>
```

### slug.md

```markdown
```yaml
slug: <slug>
branch: <branch-name>
created: <iso-8601>
```

# <slug>

<task-title>

<description>
```

Written by `mill-spawn`. Displayed by `mill-status`. Never modified after creation.

### discussion.md

Free-form markdown. No schema beyond "it's markdown". Used as input to `mill-plan`. Required fields (in `discussion.schema.md`) are advisory, not enforced:

- Problem statement
- Approach options considered
- Chosen approach
- Open questions

### config.yaml and config.local.yaml

See `02-review.md` for models section.

Shared (`wiki/config.yaml`, tracked in wiki):
```yaml
repo:
  short-name: <str>
  branch-prefix: <str | null>

wiki:
  clone-path: <str | null>   # default: derived from git remote

pipeline:
  # v2.0 default: SonnetMax for all review types
  plan-review-model:       sonnet-max
  code-review-model:       sonnet-max
  discussion-review-model: sonnet-max   # future candidate: gemini-3-pro (tool-use exploration)
  implementer-model:       sonnet-max

models:
  sonnet:        { provider: claude, model_id: claude-sonnet-4-5 }
  sonnet-max:    { provider: claude, model_id: claude-sonnet-4-5, effort: max }
  opus:          { provider: claude, model_id: claude-opus-4 }
  gemini-3-pro:  { provider: gemini, model_id: gemini-3-pro-preview }
```

Local (`.millhouse/config.local.yaml`, gitignored):
```yaml
gemini:
  api_key: <str>

notifications:
  toast: true
```

## Template substitution

One helper, ~20 LOC:
```python
def render(template_path: Path, **tokens) -> str:
    text = template_path.read_text(encoding="utf-8")
    for key, value in tokens.items():
        text = text.replace(f"<{key.upper()}>", str(value))
    return text
```

No Jinja2, no Python expressions in templates. Just `<TOKEN>` → value replacement. If a template needs conditional logic, it's a sign the format is wrong.

## Schema validation

One validator, ~50 LOC:

```python
def validate(artefact_path: Path, schema_path: Path) -> list[str]:
    """Return list of violations. Empty list = valid."""
    ...
```

Schema file is plain markdown with sections:
- **Required fields:** list of YAML frontmatter keys
- **Required sections:** list of `## Heading` strings
- **Field types:** YAML block listing `field: type`

Validator parses schema, parses artefact, checks. Called explicitly by skills that care (e.g., `mill-plan` validates before committing; `mill-go` validates plan before execution).

Not called automatically on every file I/O — adds friction without catching much.

## Rule: no new formats without spec update

If a skill wants to write a new file format, the developer (human or CC) must:
1. Add it to the inventory table above
2. Create the template in `templates/`
3. Create the schema in `templates/`
4. Get review approval

This is a deliberate speed-bump to prevent format-drift.
