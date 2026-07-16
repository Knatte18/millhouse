# Batch: golang-build-gopath-fallback

```yaml
task: "Miscellaneous small tooling and doc/template accuracy gaps"
batch: "golang-build-gopath-fallback"
number: 3
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Closes GitHub #658: `golang-build/SKILL.md`'s "Tool Installation" section (lines 35-48)
currently has no detection command at all — only prose ("If either tool is not found when
running the build workflow: ... report ... and stop"). In practice the agent following it
runs a bare `command -v`/`which` check, which produces a false negative for tools installed
via `go install` (the method this skill's own "Install:" instructions recommend), since
those land in `$(go env GOPATH)/bin`, not guaranteed to be on `$PATH`. This batch introduces
the full detection snippet with a `$GOPATH/bin` fallback. Pure documentation edit, no
executable surface. External interface for later batches: none.

## Cards

### Card 9: add `$GOPATH/bin` fallback to the tool-detection step

- **Context:** none
- **Edits:**
  - `plugins/golang/skills/golang-build/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the "## Tool Installation" section, replace the current prose-only
  failure-handling block —

  ```
  If either tool is not found when running the build workflow:
  - **Missing goimports**: Report "goimports not found — install with: `go install golang.org/x/tools/cmd/goimports@latest`" and stop.
  - **Missing golangci-lint**: Report "golangci-lint not found — install with: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`" and stop.

  Do not silently skip these steps.
  ```

  — with an explicit detection step performed before those bullets, followed by the same two
  report-and-stop bullets now gated on both checks failing. Add a bash snippet performing,
  per tool: `command -v goimports >/dev/null 2>&1 || test -x "$(go env GOPATH)/bin/goimports"`
  and the equivalent for `golangci-lint`. State explicitly: when the fallback path is what
  resolves the tool (bare `command -v` failed but `$(go env GOPATH)/bin/<tool>` exists),
  invoke the tool via that full path (`"$(go env GOPATH)/bin/<tool>"`) for the remainder of
  the build workflow, or prepend `$(go env GOPATH)/bin` to `PATH` for the session — either
  approach is acceptable, state one clearly. Only emit the existing "not found — install
  with: ..." message and stop when BOTH the bare check and the `$GOPATH/bin` fallback fail.
  Keep "Do not silently skip these steps." unchanged at the end of the section.
- **Commit:** `docs(golang-build): fall back to $GOPATH/bin when tool not on PATH`

## Batch Tests

`verify: null` — pure documentation edit to `golang-build/SKILL.md` (agent-followed
markdown instructions, no executable Python backing it). No test harness in this repo parses
SKILL.md content; verified by plan/code review reading the described bash fallback logic for
correctness, per `_mill/discussion.md`'s Testing section for #658.
