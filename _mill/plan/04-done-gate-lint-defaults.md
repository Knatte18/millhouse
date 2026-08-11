# Batch: done-gate-lint-defaults

```yaml
task: 'mill-go: quality-gate coverage gaps (NIT-fix regressions, missing lint gate)'
batch: done-gate-lint-defaults
number: 4
cards: 2
verify: null
depends-on: []
```

## Batch Scope

This batch closes #800 (lint findings slipping past every gate to PR-time) by changing `mill-plan/SKILL.md`'s authoring guidance so a plan's `pipeline.done_gate` defaults to including the target language's lint command whenever one is defined, decoupled from whether a repo-wide test is also included — and brings the `done_gate` comment in `mill-config.yaml` (hub file) and `plugins/mill/templates/mill-config.yaml` (plugin template) into sync, reflecting that new default. This is documentation/comment-only — no code path reads or executes anything differently; `_done_gate.py` and mill-go's pre-done gate step already run whatever `done_gate` string a plan author writes, unchanged. It is independent of batches 01-03 (different subsystem, no shared file).

**Batch-local note (wiki-config-mutation):** Card 10 edits `mill-config.yaml`, which triggers the plan validator's `wiki-config-mutation` check. This is a comment-only edit — the `done_gate: null` value and every other key are untouched, so it carries zero mid-flight config-mutation risk; mill-plan applies condition (a) of the skip-check override (a bootstrap-card justification, this paragraph) and re-runs the validator with `--skip-check wiki-config-mutation`.

## Cards

### Card 9: `mill-plan/SKILL.md` Done-gate reminder — default to lint

- **Context:**
  - `plugins/golang/skills/golang-build/SKILL.md`
  - `plugins/python/skills/python-build/SKILL.md`
  - `plugins/csharp/skills/csharp-build/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Replace the current "**Done-gate reminder.**" paragraph (the block currently reading: "If the plan's batch-verify scopes do not cover the entire module tree (the common case for scoped plans), consider setting `pipeline.done_gate` in `mill-config.yaml` to a cheap repo-wide test command (e.g. `go test ./...` for Go repos, `dotnet test` for .NET solutions). mill-go runs this command from `git_root` before marking the task `done`, catching regressions in packages outside the batch-verify scope." followed by "Leave `done_gate: null` (the default) if a repo-wide test would be too slow or is not meaningful for the project.") with:
    ```
    **Done-gate reminder.**
    If the plan's batch-verify scopes do not cover the entire module tree (the common case for scoped plans), consider setting `pipeline.done_gate` in `mill-config.yaml` to a cheap repo-wide test command (e.g. `go test ./...` for Go repos, `dotnet test` for .NET solutions). mill-go runs this command from `git_root` before marking the task `done`, catching regressions in packages outside the batch-verify scope.
    When the target language's build skill defines a lint command (Go: `golangci-lint run`; Python: `ruff check .`), default `done_gate` to include it — e.g. `go test ./... && golangci-lint run`. This applies even when a repo-wide *test* command is skipped as too slow: author `done_gate: golangci-lint run` (lint-only) rather than leaving it `null`, since linters are fast, unlike full regression suites. `csharp-build` defines no lint command today, so C# projects are unaffected by this default.
    Leave `done_gate: null` only when the project has neither a meaningful repo-wide test nor a defined lint command.
    ```
  - Verify the lint-command names cited (`golangci-lint run`, `ruff check .`) exactly match `golang-build/SKILL.md`'s and `python-build/SKILL.md`'s own Build Commands sections, and that `csharp-build/SKILL.md` still defines no lint command (its "Convention" note: "This is precautionary since csharp-build today ships no formatter.").
- **Commit:** `docs(mill-plan): default done_gate to lint when the language defines one`

### Card 10: sync `done_gate` comment across hub file and plugin template

- **Context:** none
- **Edits:**
  - `mill-config.yaml`
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `mill-config.yaml` (repo root), replace the current `done_gate:` line — `  done_gate: null  # Repo-wide test command run from git_root before marking done. null = disabled.` — with:
    ```
      done_gate: null  # Repo-wide check command run from git_root before marking done; null = disabled. Default to including the language's lint command (e.g. golangci-lint run, ruff check .) even when a full test run is skipped as too slow. e.g. "go test ./... && golangci-lint run" or "dotnet test". (#561)
    ```
  - In `plugins/mill/templates/mill-config.yaml`, replace the current `done_gate:` line — `  done_gate: null  # Repo-wide test command run from git_root before marking done. null = disabled. e.g. "go test ./..." or "dotnet test". (#561)` — with the byte-identical replacement line used above in `mill-config.yaml`, so both files carry the exact same `done_gate:` comment text (per this repo's "mill-config.yaml hub file and plugin template must stay in sync" convention).
  - Leave the `done_gate_baseline_preflight:` line immediately below unchanged in both files (it is already identical between them and out of scope for this task).
- **Commit:** `docs(mill-config): sync done_gate comment to mention lint default`

## Batch Tests

`verify: null` — this batch is documentation/comment-only, matching this task's discussion Testing section ("`mill-plan/SKILL.md` done_gate guidance change: documentation-only — no automated test; verify by re-reading the edited section for internal self-consistency"). Verification is a manual re-read of Card 9's edited paragraph for internal consistency with `golang-build`/`python-build`/`csharp-build`'s actual lint-command definitions, and a byte-level diff confirming Card 10 left both `mill-config.yaml` files' `done_gate:` comment lines identical.
