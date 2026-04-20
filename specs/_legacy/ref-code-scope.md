# Code Scope — what Python handles, what it doesn't

```yaml
status: draft
depends-on: 00-overview
```

## Purpose

Draw the line clearly between what belongs in Python and what belongs elsewhere (markdown skills, templates, config, shell scripts). v1 failed this: orchestration logic, format rules, and workflow decisions all ended up in Python when most belonged in markdown.

## The division

| Concern | Lives in | Why |
|---|---|---|
| Entry-point CLIs (`mill-*`) | Python scripts | Argparse, subprocess, JSON parsing — Python strengths |
| Provider implementations | Python | Stream parsing, HTTP clients, tool-use loops |
| Shared helpers (junction, wiki lock, subprocess) | Python | Library functions used by multiple scripts |
| Validators (plan, status, review-output) | Python | Structural checks on text |
| Workflow logic ("what happens after X") | Markdown skills | Claude reads the skill, executes the workflow |
| Format templates | Markdown files with `<TOKEN>` placeholders | Non-executable content; humans + agents read them |
| Format schemas | Markdown files listing rules | Specifications, not code |
| Configuration | YAML | Static data, edited by humans |
| Integration tests | PowerShell | Shell-level end-to-end verification |
| Manual setup (cloning, symlinking plugins) | Inline commands or PowerShell | One-shot operations, not library code |

## What Python handles (in detail)

### Entry-point scripts (`plugins/mill/scripts/mill-*.py`)

One script per CLI command. Each:
- Parses its own argparse (2–4 args, no subcommands)
- Loads config via a 3-line helper (no framework)
- Calls library functions from `plugins/mill/scripts/_*.py`
- Prints result to stdout, errors to stderr, exits with code

Not in Python:
- The *workflow* of "what to do in this situation" — that's in the skill file for Claude to execute
- User-facing text beyond CLI argument validation — skills tell Claude what to say

### Providers (`plugins/mill/scripts/providers/*.py`)

Each provider implements one function:
```python
def review(prompt: str, model: str, effort: str | None) -> ReviewResult:
    ...
```

Handles:
- API client or subprocess spawn
- Response/stream parsing
- Tool-use loop (if supported)
- Verdict extraction from output

Not in providers:
- Prompt construction (prompts come in as strings, pre-rendered by the caller)
- Workflow decisions (when to review vs when to implement)
- User interaction

### Shared helpers (`plugins/mill/scripts/_*.py`)

Prefixed with `_` to signal "internal, not a CLI". Examples:

- `_subprocess_util.py` — `run()` wrapper with logging and timeout
- `_junction.py` — `create()`, `remove()` for Windows junctions/POSIX symlinks
- `_wiki.py` — `acquire_lock()`, `release_lock()`, `write_commit_push()`
- `_config.py` — `load_config()`, `resolve_model()` — two small functions
- `_render.py` — `render(template_path, **tokens) -> str` for template substitution
- `_validate.py` — `validate(artefact_path, schema_path) -> list[str]`

One file per concern. Flat. No subpackages.

### Validators

Runs against artefacts (plan.md, status.md, etc.) and returns violations.

- Called explicitly by skills that care (e.g., `mill-plan` calls validator before committing plan)
- NOT called on every file write
- Returns a list of human-readable violation strings
- ~50 LOC total

## What Python does NOT handle

### Workflow: "what to do when X"

This is Claude's job. Example from `mill-go/SKILL.md`:

> After the implementer finishes, read `cards/<n>-result.md`. If `status: PASS`, proceed to review. If `status: FAIL`, stop and report.

Python doesn't encode this. Python has a `mill-go.py` that spawns the implementer and reads files. The "what to do next" logic lives in the skill Claude reads.

### Prompt text

Reviewer prompts, implementer briefs, discussion briefs — all are markdown templates under `plugins/mill/templates/`. Python renders them (substitution only) and passes the rendered string to providers. Prompts are NEVER written as Python string literals.

### Format specifications

`plan.md` structure, `status.md` frontmatter, `review-output.md` sections — all defined in `plugins/mill/templates/*.schema.md`. Python validators READ these schemas; they don't embed them.

### User interaction / display

`mill-status` prints a table. The formatting rules are simple enough to live in the script (30 LOC). But more complex display (progress bars, interactive pickers) should stay out of Python — print plain text, let Claude Code's harness or external tools do pretty display.

### Claude-specific prompt engineering

If a prompt needs "you are an expert reviewer...", that's in the template. If it needs "end with JSON output", that's in the template. Python doesn't know about Claude-specific prompt tricks; the template does.

## What PowerShell handles

### Integration tests (`plugins/mill/integration_tests/*.ps1`)

One `.ps1` per end-to-end flow:
```powershell
# test-bootstrap.ps1
$tmp = New-TemporaryDirectory
cd $tmp
python plugins/mill/scripts/mill-setup.py
if (-not (Test-Path ".millhouse/wiki")) { throw "junction not created" }
python plugins/mill/scripts/mill-add.py foo --description "test"
$output = python plugins/mill/scripts/mill-list.py
if ($output -notmatch "foo — test") { throw "task not listed" }
Write-Host "PASS"
```

Why PowerShell here:
- Shell commands are what you're actually testing
- File system + process + comparison is PowerShell's strength
- No Python-specific test infrastructure needed

### One-shot setup operations

- Plugin symlinking (if v1-style `symlink-plugins.ps1` is needed)
- Manual migrations
- Developer utilities

These are not library code; they're operator scripts.

## What config handles

### `wiki/config.yaml` (shared)

- `repo.short-name`, `repo.branch-prefix`
- `wiki.clone-path` (optional override)
- `pipeline.*-model` (which model for each phase)
- `models:` registry (model-id → provider + provider-specific config)

### `.millhouse/config.local.yaml` (local, gitignored)

Non-secret overrides of values in `wiki/config.yaml`. Shape: valid YAML, partial overlay on the shared config.

- Notification preferences
- User overrides for models (e.g. prefer Opus for code-review in this worktree)
- Per-worktree pipeline tweaks

### `<working-clone>/.env` (at repo root, gitignored)

Secrets only. `KEY=value` per line. Loaded as environment variables by scripts that need them. At repo root (not inside `.millhouse/`) because that's the universal `.env` convention.

- `GEMINI_API_KEY`
- `ANTHROPIC_API_KEY` (if using Anthropic API instead of Claude CLI subscription)
- Any other auth tokens

Never put secrets in `config.local.yaml` and never put config in `.env`.

## What skills handle (markdown)

Every skill is ≤200 lines of markdown. Structure:

```markdown
---
name: mill-go
description: ...
---

# mill-go

## When to use
<prose>

## Phases
1. <phase 1 — commands to run, files to read>
2. <phase 2>
...

## Error handling
<what to do when X fails>
```

The skill is the *executable specification* Claude follows. Python is the *implementation* Claude calls.

## The separation principle

**Python is a library of primitives. Skills are the program.**

If a change needs to happen to the workflow, edit the skill. If a change needs to happen to how a primitive works (how we create junctions, how we parse stream-json), edit the Python.

A common v1 failure mode: workflow logic drifted into Python (retry loops, conditional paths, branching on reviewer verdicts). This meant changing workflow required changing Python, which meant running tests, which meant pytest churn. v2 avoids this by keeping workflow in markdown where Claude reads it and executes — no test infrastructure needed.

## Sanity check per file

Before adding anything to a Python file, ask:

1. Is this a primitive operation (junction, subprocess, parse, validate)? → Python.
2. Is this "what happens when condition X is met"? → Markdown skill.
3. Is this a prompt or format template? → Markdown file under `templates/`.
4. Is this static data? → YAML config.
5. Is this a one-shot operator script? → PowerShell.

If more than one fits: it's probably mixing concerns, split it.
