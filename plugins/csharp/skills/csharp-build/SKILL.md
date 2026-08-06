---
name: csharp-build
description: Build and test commands for C#/.NET. Use after completing a task.
---

# Build Skill

Build and test configuration for C#/.NET projects.

---

## Build Commands

Run these commands after completing a task to verify correctness:

```bash
dotnet build --nologo -clp:ErrorsOnly
dotnet test --nologo -clp:ErrorsOnly
```

`-clp:ErrorsOnly` suppresses only MSBuild build-phase warnings (`CS8618`, `MSB3246`, `RZ10012`, etc.) — VSTest failure detail (failing test names, `Error Message:` blocks) and the run summary are untouched.

- **Never pipe the gating invocation** (mill-go verify, git-commit lint, any pass/fail check) to `grep` or `tail`. `cmd | grep` returns the downstream tool's exit status, not dotnet's — a failing suite would exit 0 and silently pass the gate. The unpiped form above preserves dotnet's authoritative exit code. If a human-readable summary-only view is ever wanted (never for gating), guard it with `set -o pipefail`.
- **Never `tail -N` a dotnet build/test.**
  Warnings can evict the `Passed!`/`Failed!` summary from the tail window.

**Convention: Writing formatters (when used) run on changed files only, never on the whole project.
This is precautionary since csharp-build today ships no formatter.
Any future formatter must be scoped to changed files.
Whole-project build and test stay whole-project.**

## Failure Handling

- If **build fails**: analyze the error, fix the issue, and retry.
- If **tests fail**: analyze the failure, fix the code or test, and retry.
- If a fix requires changes beyond the current task's scope: stop and report the issue to the user.
- Do **not** skip or disable failing tests.

---

## Project Configuration

> Customize per project. Specify which solution/project to build and test.

### Test discovery

Before running tests, verify the project is testable:

1. **Solution file:** Look for `*.sln` files in the project root.
   If found, `dotnet build` and `dotnet test` operate on the solution (discovers all projects automatically).
2. **Test projects:** If no solution file, look for `*.csproj` files.
   Test projects follow naming conventions: `*.Tests.csproj`, `*.Test.csproj`, or `*Tests.csproj`.
   Check for test framework package references (`xunit`, `NUnit`, `MSTest`) to confirm a project is a test project.
3. **No tests:** If no test projects are found, report "No test projects found" rather than running `dotnet test` on a non-test project.

### Defaults

- Build the solution or project in the current working directory.
- Run all tests in the test project associated with the current project.

### Per-project overrides

Specify these when the defaults don't apply:

- Solution file path (if not in current directory)
- Specific test project to run
- Build configuration (Debug/Release)
- Additional build flags

<!-- Project-specific build configuration goes here -->
