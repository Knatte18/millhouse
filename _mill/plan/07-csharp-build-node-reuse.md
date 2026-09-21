# Batch: csharp-build-node-reuse

```yaml
task: "Misc infra/wiki/PR/self-hosting reliability bugs"
batch: csharp-build-node-reuse
number: 7
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Fixes #1094: repeated `dotnet build`/`dotnet test` calls across a long mill-orchestrated session
(per-batch verify, baseline pre-flight, merge-in verify replay, git-pr's final verify) accumulate
`nodeReuse:true` MSBuild worker processes with no teardown, and a later `dotnet test` can stall
11+ minutes on file-lock contention as a result. Pure documentation edit to the shared `csharp-build`
skill's default commands, no runnable surface in this repo (it documents commands for target C#
repos, not code in this repo).

## Cards

### Card 16: add node-reuse-disabling flags to the documented dotnet commands

- **Context:** none
- **Edits:**
  - `plugins/csharp/skills/csharp-build/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/csharp/skills/csharp-build/SKILL.md`'s `## Build Commands` section, the two documented
  default commands are:
  ```bash
dotnet build --nologo -clp:ErrorsOnly
dotnet test --nologo -clp:ErrorsOnly
  ```
  Add `-p:UseSharedCompilation=false /nr:false` to both, matching exactly the flags the source
  issue's own incident confirms resolve the stall (the issue's repro: the same `dotnet test` command
  with these two flags added completed in 32s versus an 11+ minute stall without them). Add a short
  note immediately below the commands (or as a new bullet in the existing bullet list right after
  them) explaining why: a long orchestrated mill session chains many sequential `dotnet
  build`/`dotnet test` calls in one process tree (per-batch verify, baseline pre-flight, merge-in
  verify replay, git-pr's final verify), and MSBuild's `nodeReuse:true` default lets worker processes
  accumulate and contend across that whole session unless explicitly disabled per invocation.
- **Commit:** `docs(csharp-build): disable MSBuild node reuse in default build/test commands (#1094)`

## Batch Tests

Documentation-only — no runnable surface in this repo. Verified by re-reading the edited section and
confirming both commands carry the new flags exactly as the incident's own working repro used them.
