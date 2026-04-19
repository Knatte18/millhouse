# mill-v2 — Overview

```yaml
status: draft
version: 0.0
repo: https://github.com/Knatte18/millhouse
predecessor: https://github.com/Knatte18/millhouse-legacy
```

## Why v2

`mill-v1` (millpy) became unmaintainable: ~15k LOC Python across deep package structure, 645 tests, many layers of abstraction that weren't warranted by the actual behaviour delivered. Most failure modes came from over-engineered orchestration (multi-round reviewers, DAG executors, ensemble handlers) that cost more in complexity than they delivered in value.

v2 is a rewrite with tight scope discipline. We know what mill should do. We do not need to discover it by accretion.

## Goals

1. **Layered build:** one layer lands completely before the next starts.
2. **Minimum viable at each layer:** simplest thing that works end-to-end.
3. **Python base, but flat.** No package structure, no abstractions, no test framework until needed.
4. **All mill-state inside `.millhouse/` at project root.** Single directory for local state, junctions to shared state.
5. **Replaceable providers.** Adding Gemini/Ollama later doesn't touch CLI code.

## Non-goals (v2.0)

- No multi-round reviewer loops
- No DAG orchestration (linear first)
- No ensemble reviewers in core (runnable as a separate script only)
- No Gemini provider in v2.0 (design must allow adding it without refactor)
- No backwards compatibility with v1 plans/config

## Directory layout

```
C:\Code\millhouse\          ← container (NOT a repo itself)
  hub\                      ← primary working clone (any branch)
  wiki\                     ← wiki clone (tasks, plans, active state)
  worktrees\<slug>\         ← worktrees for in-progress tasks
```

Each working clone (hub or worktree) contains:
```
<working-clone>\
  .env                      ← secrets at repo root (standard dotenv convention)
  .millhouse\
    .active    → <wiki>\active\<slug>      (junction; only when task is active)
    .<slug>.slug.md                        (task-identity file; only when task is active)
    config.local.yaml                      (non-secret worktree overrides)
    mill-*.py                              (wrapper scripts created by mill-setup)
    scratch\                               (ephemeral working files)
    wiki       → <container>\wiki          (junction to the single wiki clone)
```

**`.millhouse/` is gitignored.** Wiki content lives in the wiki repo (tracked there). Everything else inside `.millhouse/` is local-only. See `ref-formats.md` for the full directory contract and the `.env` vs `config.local.yaml` distinction.

## Language and discipline

**Base language:** Python 3.10+.

**Rules (violating any is a red flag):**

1. **No package structure.** Flat files under `scripts/` and `providers/`. No `__init__.py` until clearly necessary.
2. **No abstractions before use.** No `class Reviewer(Protocol)`. Use dict-dispatch when polymorphism is needed.
3. **One file, one job, one `def main()`.** Max ~300 lines per file. Over that → split.
4. **Minimal argparse.** 2–4 args per script. No subcommands.
5. **No logger infrastructure.** `print()` to stderr is enough.
6. **No pytest initially.** Integration tests only: shell scripts that run commands and check output.
7. **Test budget:** total test LOC < 30% of source LOC. Over that → delete tests.
8. **Hard cap on v2.0 Python code: 1500 LOC total.** If a layer pushes us over, the design is wrong.

**If Claude Code generates more than ~100 lines for a task, stop and ask for "minimum version".**

## v1 reuse (mandatory check before writing)

Before writing any new code, consult `specs/ref-v1-reuse.md`. It lists which v1 components to lift as-is, which to rewrite with v1 as reference, and which to ignore entirely. Lifting battle-tested v1 code is the default; rewriting from scratch is the exception.

Each layer spec lists its specific v1 reuse candidates. When the worker begins a layer, they should:
1. Read `specs/ref-v1-reuse.md`
2. Open each v1 file listed for that layer in `C:\Code\millhouse-legacy\`
3. Copy, clean (strip imports, package scaffolding), paste into v2
4. Only then write the remaining new logic

## Provider plugin pattern

Providers are independent Python files. Each one exposes one function:
```python
def review(prompt: str, model: str, effort: str | None) -> ReviewResult:
    ...
```

Where `ReviewResult` is a plain dataclass with `verdict: str`, `findings_path: Path`, `raw_output: str`.

Registry lives in config (YAML, not code):
```yaml
models:
  sonnet:        { provider: claude, model_id: claude-sonnet-4-5 }
  sonnet-max:    { provider: claude, model_id: claude-sonnet-4-5, effort: max }
  opus:          { provider: claude, model_id: claude-opus-4 }
  # gemini-3-pro: { provider: gemini, model_id: gemini-3-pro-preview }  ← later
```

The dispatcher looks up the model name, finds the provider module, calls `review()`. Adding Gemini later is one new file plus config entries.

## Format discipline (first-class concern)

v1 had format sprawl: plan-v1 vs plan-v2 vs plan-v3, status.md shapes that drifted, review-output formats varying per reviewer, prompts materialized differently for tool-use vs bulk. This caused bugs, confusion, and meant that every small change to a format cascaded through unrelated code.

**v2 rules:**

1. **One template per format.** Every artefact type (plan, status, review report, brief, handoff prompt) has exactly one canonical template stored in `plugins/mill/templates/`.

2. **Templates live outside code.** They are `.md` files with `<PLACEHOLDER>` tokens. Substitution is done by a single helper; no format-specific code.

3. **Formats are versioned explicitly.** If a format changes, we either:
   - Make the change backwards-compatible (preferred), or
   - Bump the format version and write a migration

   No silent format drift.

4. **Schema, not prose.** Each template has a companion `<name>.schema.md` that lists required sections, field types, and validation rules. A template change must update the schema.

5. **Validators are format-agnostic.** One validator function checks "does this artefact match its schema?" It loads the schema, checks the file. No bespoke validator per format.

6. **Prompts are templates too.** Reviewer prompts, implementer briefs, handoff prompts — all use the same template mechanism. No inline prompt strings in Python code.

7. **No conditional formats per provider.** The reviewer prompt is the same whether the provider is Claude or Gemini. Provider-specific adjustments happen in the provider module, not by swapping templates.

```
plugins/mill/templates/
  plan.md             plan.schema.md
  status.md           status.schema.md
  review-prompt.md    review-prompt.schema.md
  review-output.md    review-output.schema.md
  implementer-brief.md  implementer-brief.schema.md
  slug.md             slug.schema.md
```

Eight or so templates total. Fixed set. Adding a new format is a deliberate act, not an accident.

## Layer map

| Layer | Goal | Delivers |
|---|---|---|
| 01 Bootstrap | Get wiki + tasks working | `mill-setup`, `mill-add`, `mill-list` |
| 02 Review | Single-shot review on demand | `mill-review` + Claude provider |
| 03 Orchestration | Run a plan end-to-end | `mill-go` (linear, no DAG) |
| 04 Extras | Rest of the skills | `mill-plan`, `mill-start`, `mill-merge`, cleanup |

Each layer has its own spec file in `specs/`. No layer starts before the previous one is demonstrably working.

## Out-of-scope plugins (kept from v1, copied-over or split-out)

- `csharp` — copy from legacy as-is
- `python` — copy from legacy as-is
- `weblens` — copy from legacy as-is
- `codeguide` — split out into its own plugin in v2 (in v1 it lives as skills inside mill)

**Note on codeguide:** in v1 codeguide is a set of skills (`codeguide-setup`, `codeguide-update`, etc.) living inside `plugins/mill/skills/`. v2 promotes it to its own plugin at `plugins/codeguide/`. **Mill's git-commit skill triggers `@codeguide:codeguide-update`** as part of its workflow — codeguide does not attempt to maintain itself. Without mill calling it, codeguide's `_codeguide/` docs go stale. The plugin separation is cosmetic/organizational: the trigger still lives in mill, codeguide just has its own plugin home.

## Key lessons from v1 (issues that informed this spec)

- **Subprocess CLI is fine** if parsed correctly. Use `--output-format stream-json`, handle both tool-use and free-text responses. Don't assume Write-tool was called.
- **Config path resolution must be simple.** v1 had multiple fallbacks and `_millhouse/config.yaml` legacy paths. v2 resolves from `<project>/.millhouse/config.yaml` and wiki's `.millhouse/wiki/config.yaml`. Two places, both explicit.
- **Path detection for wiki commits must be structural**, not regex on path components. v1's naive substring match silently failed during the `_millhouse/` → `.millhouse/` migration.
- **Reviewers should have one entry point.** No bulk-vs-tool-use dispatch in the wrapper. If ensemble is wanted, it's an *optional script* that the dispatcher can call.
- **Test churn costs more than it catches.** v1 had 645 tests; maybe 10 caught real bugs. The rest tested thin glue.
