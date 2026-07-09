# Batch: goimports-halt

```yaml
task: Fix mill-start instruction gaps, baseline long-path on Windows, and language skill tooling reliability
batch: goimports-halt
number: 4
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Fixes #614: the git-commit pre-commit lint step delegates to `{lang}-build` but its terse "run the lint/format step" wording is silent on what happens when a required tool (e.g. `goimports`) is missing, so an agent can silently skip it. `golang-build` already documents the correct behavior (halt with an actionable "install X" message — its Tool Installation section), so no change is needed there; the single card makes `git-commit` explicitly inherit that halt contract. Pure-documentation batch: `verify: null`.

## Cards

### Card 7: Make git-commit inherit the {lang}-build tool-availability halt

- **Context:**
  - `plugins/golang/skills/golang-build/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/git-commit/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `git-commit/SKILL.md`, `## Pre-commit steps` → `### 1. Lint (language-specific)`, add one sentence stating that the delegated `{lang}-build` skill's tool-availability checks apply to this pre-commit lint step: if a required formatter/linter (e.g. `goimports`) is not installed, follow that skill's documented halt-with-actionable-message behavior (e.g. golang-build's Tool Installation section, which reports "install with: ..." and stops) — do NOT silently skip the lint/format step. Keep the existing "changed files only" scoping and every other part of step 1 unchanged. Do NOT edit `golang-build/SKILL.md` (its halt behavior already stands and is the referenced contract).
- **Commit:** `fix(git-commit): inherit {lang}-build tool-availability halt in pre-commit lint`

## Batch Tests

`verify: null` — the single card edits `git-commit/SKILL.md` prose only; there is no automated test for skill instruction content. Correctness is established by the plan reviewer confirming step 1 now names the halt contract (no silent skip) while preserving the changed-files-only scoping, and that `golang-build` was left unedited; confirmed at merge time by human read-through.
