# Batch: golangci-lint-sandbox-fallback

```yaml
task: 'mill-setup/wiki/docs/build-env: misc small bugs, round 3'
batch: golangci-lint-sandbox-fallback
number: 4
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Fixes GitHub issue #1111: `golang-build/SKILL.md` requires `golangci-lint` and instructs stopping
the build workflow if it can't be installed, but in network-restricted sandboxes the install itself
fails on an unreachable transitive-dependency host — observed twice, both times worked around ad
hoc with `goimports -w` + `go vet ./...` instead. This batch documents that exact substitute as the
official, narrowly-scoped fallback, per `discussion.md`'s `1111-sandbox-fallback` Decision. No
external interface — self-contained single-file doc fix.

## Cards

### Card 4: Document the network-restricted-sandbox fallback for golangci-lint in golang-build/SKILL.md

- **Context:** none
- **Edits:**
  - `plugins/golang/skills/golang-build/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `## Tool Installation`, the bullet currently reading exactly:
  `- **Missing golangci-lint**: Report "golangci-lint not found — install with: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`" and stop.`
  Replace it with a version that documents the network-restricted-sandbox fallback as a sub-list
  under the same bullet, changing "and stop" to "and attempt that install command", followed by
  three sub-bullets:
  - If the install command succeeds, proceed with the build workflow using the now-installed
    `golangci-lint`.
  - If the install command fails with output indicating a network/fetch failure reaching an
    external VCS host for a transitive dependency — e.g. containing text like
    "Repository not found", "dial tcp", "no such host", "i/o timeout", "unable to fetch" (the
    issue's own repro observed "Repository not found" via `git ls-remote` against the unreachable
    host) — do not stop: substitute `goimports -w <changed-files>` + `go vet ./...` in place of
    `golangci-lint run` for this build workflow run, and note in the summary that `golangci-lint`
    was skipped due to a network-restricted sandbox.
  - Any other install failure (a real compile error, a bad module path, an authentication failure,
    etc. — output that does NOT match the network-failure shape above) still stops and reports
    exactly as before.

  In `## Failure Handling`, after the existing bullet
  `- Do **not** skip or disable failing tests.`, add one new bullet:
  `- **golangci-lint unavailable due to network restriction**: see the network-restricted-sandbox fallback documented under **Tool Installation** — substitute `goimports -w` + `go vet ./...` for `golangci-lint run` instead of stopping; any other install failure still stops and reports.`

  Do not change the `**Missing goimports**` bullet, the tool-detection `command -v`/`$GOPATH/bin`
  fallback logic above it, the "Build Commands" section, "Project Configuration" section, or any
  other part of this file.
- **Commit:** `docs(golang-build): document network-restricted-sandbox fallback for golangci-lint`

## Batch Tests

`verify: null` — this is a doc-only `SKILL.md` change with no runnable surface (`golang-build` is
loaded and followed by an LLM, not executed as code); the repo also has no Go module to run
`go test`/`golangci-lint` against, since this is the `millhouse` Python-based mill repo, not a Go
project. Manual verification at implementation time: confirm the documented fallback matches what
was already used ad hoc in the referenced issue (`goimports -w` + `go vet ./...`), and confirm the
new sub-bullets read as a coherent three-way branch (success / network failure / other failure).
