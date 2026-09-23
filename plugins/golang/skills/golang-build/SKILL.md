---
name: golang-build
description: Build and test commands for Go. Use after completing a task.
---

# Build Skill

Build and test configuration for Go projects.

---

## Build Commands

Run these commands after completing a task to verify correctness:

```bash
goimports -w <changed-files>
go vet ./...
go build ./...
go test ./...
golangci-lint run
```

**Convention: Writing formatters (goimports -w) run on changed files only, never on the whole project.
Whole-project build, test, and read-only lint stay whole-project.**

## Failure Handling

- If **build fails**: analyze the error, fix the issue, and retry.
- If **tests fail**: analyze the failure, fix the code or test, and retry.
- If a fix requires changes beyond the current task's scope: stop and report the issue to the user.
- Do **not** skip or disable failing tests.
- **golangci-lint unavailable due to network restriction**: see the network-restricted-sandbox fallback documented under **Tool Installation** — substitute `goimports -w` + `go vet ./...` for `golangci-lint run` instead of stopping; any other install failure still stops and reports.

---

## Tool Installation

The following tools are required and must be installed before running the build workflow:

- **goimports** — organizes and formats imports
  - Install: `go install golang.org/x/tools/cmd/goimports@latest`
- **golangci-lint** — comprehensive linter aggregator
  - Install: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`

Before running the build workflow, detect each tool with a bare `PATH` check first, then a `$GOPATH/bin` fallback — `go install` (the method recommended above) places binaries in `$(go env GOPATH)/bin`, which is not guaranteed to be on `PATH`:

```bash
command -v goimports >/dev/null 2>&1 || test -x "$(go env GOPATH)/bin/goimports"
command -v golangci-lint >/dev/null 2>&1 || test -x "$(go env GOPATH)/bin/golangci-lint"
```

When a tool resolves only via the fallback (bare `command -v` failed but `$(go env GOPATH)/bin/<tool>` exists), invoke it via that full path (`"$(go env GOPATH)/bin/<tool>"`) for the remainder of the build workflow.

Only when BOTH the bare check and the `$GOPATH/bin` fallback fail for a tool:
- **Missing goimports**: Report "goimports not found — install with: `go install golang.org/x/tools/cmd/goimports@latest`" and stop.
- **Missing golangci-lint**: Report "golangci-lint not found — install with: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`" and attempt that install command.
  - If the install command succeeds, proceed with the build workflow using the now-installed `golangci-lint`.
  - If the install command fails with output indicating a network/fetch failure reaching an external VCS host for a transitive dependency — e.g. containing text like "Repository not found", "dial tcp", "no such host", "i/o timeout", "unable to fetch" (the issue's own repro observed "Repository not found" via `git ls-remote` against the unreachable host) — do not stop: substitute `goimports -w <changed-files>` + `go vet ./...` in place of `golangci-lint run` for this build workflow run, and note in the summary that `golangci-lint` was skipped due to a network-restricted sandbox.
  - Any other install failure (a real compile error, a bad module path, an authentication failure, etc. — output that does NOT match the network-failure shape above) still stops and reports exactly as before.

Do not silently skip these steps.

---

## Project Configuration

> Customize per project. Specify test discovery and build behavior.

### Test discovery

Before running tests, verify the project is testable:

1. **Test files:** Look for `*_test.go` files in the project.
   If none are found, report "No test files found" rather than running `go test` on an empty package.
2. **Test packages:** Test files are in the same directory as the code they test.
   A package with at least one `*_test.go` file is testable.

### Defaults

- Build all packages in the current working directory and subdirectories.
- Run all tests found in the project.

### Per-project overrides

Specify these when the defaults don't apply:

- Specific package paths to build or test
- Build flags (e.g., `-tags`, `-ldflags`)
- Test flags (e.g., `-race`, `-cover`)

<!-- Project-specific build configuration goes here -->
