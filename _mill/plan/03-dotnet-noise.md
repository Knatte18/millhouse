# Batch: dotnet-noise

```yaml
task: Fix mill-start instruction gaps, baseline long-path on Windows, and language skill tooling reliability
batch: dotnet-noise
number: 3
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Fixes #622: unfiltered `dotnet build`/`dotnet test` floods agent context with whole-solution MSBuild warning noise. Card 5 makes `--nologo -clp:ErrorsOnly` (unpiped) the default in the `csharp-build` skill — the chokepoint `workflow` language-detection routes all dotnet through — and documents the exit-code-preservation and never-tail rules. Card 6 adds a one-line backstop to the root `CLAUDE.md` for ad-hoc invocations where the skill isn't loaded. `csharp-testing` is intentionally untouched (it shells no dotnet command). Pure-documentation batch: `verify: null`.

## Cards

### Card 5: Make filtered, unpiped dotnet the default in csharp-build

- **Context:**
  - `plugins/mill/skills/workflow/SKILL.md`
- **Edits:**
  - `plugins/csharp/skills/csharp-build/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `csharp-build/SKILL.md`, `## Build Commands`, replace the two commands with `dotnet build --nologo -clp:ErrorsOnly` and `dotnet test --nologo -clp:ErrorsOnly`, BOTH unpiped. Add two explicit rules near the commands: (1) the gating invocation (mill-go verify, git-commit lint, any pass/fail check) MUST NOT be piped to `grep` or `tail` — `cmd | grep` returns the downstream tool's exit status, not dotnet's, so a failing suite would exit 0 and silently pass the gate; the unpiped form preserves dotnet's authoritative exit code. If a human-readable summary-only view is ever wanted (never for gating), it must be guarded with `set -o pipefail`. (2) Never `tail -N` a dotnet build/test — warnings can evict the `Passed!`/`Failed!` summary from the tail window. Add a one-sentence rationale that `-clp:ErrorsOnly` suppresses only MSBuild build-phase warnings (`CS8618`, `MSB3246`, `RZ10012`, etc.), leaving VSTest failure detail (failing test names, `Error Message:` blocks) and the run summary intact. Do NOT edit `csharp-testing/SKILL.md`. Preserve the existing "formatters run on changed files only" convention text.
- **Commit:** `fix(csharp-build): default to --nologo -clp:ErrorsOnly, unpiped, to cut MSBuild noise`

### Card 6: Add ad-hoc dotnet backstop rule to CLAUDE.md

- **Context:**
  - `plugins/csharp/skills/csharp-build/SKILL.md`
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the root `CLAUDE.md` (the mill-v2 project conventions file at the repo root), add a one- to two-line backstop rule under the `## Conventions` section: for ad-hoc `dotnet build`/`dotnet test` invocations where the `csharp-build` skill isn't loaded, pass `--nologo -clp:ErrorsOnly` and never pipe the gating invocation to `grep`/`tail` (it masks dotnet's exit code). Keep it concise — one or two lines, mirroring the canonical rule in `csharp-build/SKILL.md`; do not reproduce the full rationale. Edit the repo-root `CLAUDE.md`, not the user global one.
- **Commit:** `docs(claude-md): backstop rule for ad-hoc dotnet noise filtering`

## Batch Tests

`verify: null` — both cards edit `SKILL.md` / `CLAUDE.md` prose only, with no runnable surface and no test that asserts skill instruction content. Correctness is established by the plan reviewer confirming the commands are unpiped `--nologo -clp:ErrorsOnly`, the never-pipe-gating and never-tail rules are present, `csharp-testing` is untouched, and the `CLAUDE.md` backstop is a concise one-liner; confirmed at merge time by human read-through.
