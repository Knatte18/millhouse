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

**Convention: Writing formatters (goimports -w) run on changed files only, never on the whole project. Whole-project build, test, and read-only lint stay whole-project.**

## Failure Handling

- If **build fails**: analyze the error, fix the issue, and retry.
- If **tests fail**: analyze the failure, fix the code or test, and retry.
- If a fix requires changes beyond the current task's scope: stop and report the issue to the user.
- Do **not** skip or disable failing tests.

---

## Tool Installation

The following tools are required and must be installed before running the build workflow:

- **goimports** — organizes and formats imports
  - Install: `go install golang.org/x/tools/cmd/goimports@latest`
- **golangci-lint** — comprehensive linter aggregator
  - Install: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`

If either tool is not found when running the build workflow:
- **Missing goimports**: Report "goimports not found — install with: `go install golang.org/x/tools/cmd/goimports@latest`" and stop.
- **Missing golangci-lint**: Report "golangci-lint not found — install with: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`" and stop.

Do not silently skip these steps.

---

## Project Configuration

> Customize per project. Specify test discovery and build behavior.

### Test discovery

Before running tests, verify the project is testable:

1. **Test files:** Look for `*_test.go` files in the project. If none are found, report "No test files found" rather than running `go test` on an empty package.
2. **Test packages:** Test files are in the same directory as the code they test. A package with at least one `*_test.go` file is testable.

### Defaults

- Build all packages in the current working directory and subdirectories.
- Run all tests found in the project.

### Per-project overrides

Specify these when the defaults don't apply:

- Specific package paths to build or test
- Build flags (e.g., `-tags`, `-ldflags`)
- Test flags (e.g., `-race`, `-cover`)

<!-- Project-specific build configuration goes here -->
