# Batch: Create Go plugin files

```yaml
task: "Add Go skill package (build, test, comments)"
batch: "Create Go plugin files"
number: 1
cards: 5
verify: null
depends-on: []
```

## Batch Scope

Create all six files that make up the `plugins/go/` skill plugin: the plugin manifest, permission settings, skills index, and the three SKILL.md files (go-build, go-comments, go-testing). All files are new — no existing files are edited. They are independent of each other in content, so all five cards can be implemented in sequence within the same session.

## Cards

### Card 1: Plugin manifest and permissions

- **Context:**
  - `plugins/csharp/.claude-plugin/plugin.json`
  - `plugins/csharp/settings.json`
- **Edits:** none
- **Creates:**
  - `plugins/go/.claude-plugin/plugin.json`
  - `plugins/go/settings.json`
- **Deletes:** none
- **Requirements:**
  Create `plugins/go/.claude-plugin/plugin.json` with the following exact content (no extra fields, no trailing whitespace):
  ```json
  {
    "name": "go",
    "description": "Go build, comments, and testing conventions",
    "version": "1.0.0",
    "license": "Apache-2.0",
    "author": {
      "name": "Knatte18"
    }
  }
  ```
  Create `plugins/go/settings.json` with the following exact content:
  ```json
  {
    "permissions": {
      "allow": [
        "Skill(go:*)"
      ]
    }
  }
  ```
  Both files must be valid JSON. The permission pattern `Skill(go:*)` must match the csharp pattern exactly (just with `go` substituted).
- **Commit:** `feat(go-plugin): add plugin.json and settings.json`

### Card 2: Skills index

- **Context:**
  - `plugins/csharp/skills/INDEX.md`
- **Edits:** none
- **Creates:**
  - `plugins/go/skills/INDEX.md`
- **Deletes:** none
- **Requirements:**
  Create `plugins/go/skills/INDEX.md` as a Markdown table listing the three skills. Mirror the csharp INDEX.md format exactly. Content:
  ```markdown
  # Go Skills

  | Skill | Description |
  |---|---|
  | [go-build](go-build/SKILL.md) | Build and test commands for Go. Use after completing a task. |
  | [go-comments](go-comments/SKILL.md) | Godoc and inline comment rules for Go. Use when writing Go comments. |
  | [go-testing](go-testing/SKILL.md) | Testing conventions for Go projects. Use when writing tests. |
  ```
  The description column text must match what will appear in the SKILL.md frontmatter `description:` fields for each skill.
- **Commit:** `feat(go-plugin): add skills INDEX.md`

### Card 3: go-build SKILL.md

- **Context:**
  - `plugins/csharp/skills/csharp-build/SKILL.md`
- **Edits:** none
- **Creates:**
  - `plugins/go/skills/go-build/SKILL.md`
- **Deletes:** none
- **Requirements:**
  Create `plugins/go/skills/go-build/SKILL.md` with SKILL.md frontmatter (`name: go-build`, `description: Build and test commands for Go. Use after completing a task.`). Write the following sections, modeled on csharp-build but adapted for Go:

  **Build Commands** — present the complete workflow in order, as a bash code block:
  ```bash
  goimports -w .
  go vet ./...
  go build ./...
  go test ./...
  golangci-lint run
  ```

  **Failure Handling** — same rules as csharp-build (analyze error, fix, retry; do not skip failing tests).

  **Tool Installation** — `goimports` and `golangci-lint` are not part of the standard Go toolchain. Provide install commands:
  - `go install golang.org/x/tools/cmd/goimports@latest`
  - `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`
  State that both must be installed before running the workflow.

  **Missing binary guidance** — if `golangci-lint` is not found, Claude must report "golangci-lint not found — install with: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`" and stop rather than silently skipping the step. Same for `goimports`.

  **Project Configuration** section — customizable per-project (same as csharp-build's section). Include a note on discovering test packages: look for `*_test.go` files; if none found, report "No test files found" rather than running `go test` on an empty package.

  End the file with: `<!-- Project-specific build configuration goes here -->`
- **Commit:** `feat(go-plugin): add go-build SKILL.md`

### Card 4: go-comments SKILL.md

- **Context:**
  - `plugins/csharp/skills/csharp-comments/SKILL.md`
  - `plugins/csharp/skills/csharp-build/SKILL.md`
- **Edits:** none
- **Creates:**
  - `plugins/go/skills/go-comments/SKILL.md`
- **Deletes:** none
- **Requirements:**
  Create `plugins/go/skills/go-comments/SKILL.md` with frontmatter (`name: go-comments`, `description: Godoc and inline comment rules for Go. Use when writing Go comments.`). Structure closely mirrors csharp-comments but adapted for Go. Write the following sections:

  **Intro paragraph** — state the goal: standard Go code with doc comments detailed enough that a reader learning Go understands what a function does, why it exists, and how it works without reading the implementation.

  **Package doc comments** — every package must have one, in one file only (doc.go or the main .go file). Must start with `Package <name>`.

  **Exported symbol doc comments** — all exported functions, types, methods, variables, and constants must have a doc comment. Rules:
  - Placed immediately before the declaration, no blank line between comment and declaration
  - Begin with the name of the symbol being documented
  - Explain what the symbol does AND why it exists (not just restate the name)
  - A reader should understand the symbol's purpose from signature + doc comment alone without reading the implementation
  - Include one bad/good example pair for a function doc comment

  **Boolean-returning functions** — use "reports whether", not "returns true if". Show example.

  **Types** — state what an instance represents, not just its name. Document zero value if meaningful. Document concurrency safety if relevant.

  **Methods on a type** — do not repeat the type name; the receiver is part of the signature.

  **Constants and variables** — group gets one intro comment; individual items get short end-of-line comments when name alone is insufficient.

  **Interface implementations** — when a method satisfies an interface, write a brief comment acknowledging the delegation (e.g., `// Write implements io.Writer by forwarding to the underlying buffer.`). Only write a full doc comment when the implementation adds behavior beyond the interface contract.

  **Inline comments — narrate the reasoning** — inline comments are mandatory at each distinct logical step in non-trivial functions. They explain domain reasoning, not mechanical restatement. Include one bad/good example pair. State the rule: explain why this step is needed, what constraint or domain rule it satisfies — but do not overdo it; trivial operations need nothing.

  **Error handling** — always comment non-obvious error handling choices. Show the `fmt.Errorf("context: %w", err)` pattern with explanation of why `%w` preserves the error chain.

  **Prohibited patterns** — same list as csharp-comments: never comment out code, no edit-history comments, no mechanical restatements. Additionally: no `/* block comments */` inside function bodies.

  End the file with: `<!-- Project-specific comments configuration goes here -->`
- **Commit:** `feat(go-plugin): add go-comments SKILL.md`

### Card 5: go-testing SKILL.md

- **Context:**
  - `plugins/csharp/skills/csharp-testing/SKILL.md`
- **Edits:** none
- **Creates:**
  - `plugins/go/skills/go-testing/SKILL.md`
- **Deletes:** none
- **Requirements:**
  Create `plugins/go/skills/go-testing/SKILL.md` with frontmatter (`name: go-testing`, `description: Testing conventions for Go projects. Use when writing tests.`). Model structure on csharp-testing. Write the following sections:

  **Framework: standard `testing` package** — Go's built-in test library. No testify.

  **Naming conventions** — test files: `<name>_test.go` in the same directory as the code. Test functions: `TestXxx` (uppercase X). Subtests: `TestFoo_ScenarioName` (underscore is the one permitted exception).

  **Table-driven tests (the standard pattern)** — all tests with multiple scenarios use this pattern. Include the exact code example from the discussion's Technical Context:
  - slice named `tests`, each entry `tt`
  - `t.Run(tt.name, ...)` for each entry
  - Error message format: `"Func(input) = got; want expected"` — actual before expected
  State that `t.Error` (continues) is default; `t.Fatal` only when subsequent steps depend on this assertion.

  **Test helpers** — call `t.Helper()` as the first line of any helper function so failure lines point to the caller, not the helper. Use `t.Cleanup(f)` for teardown and `t.TempDir()` for auto-cleaned temp directories.

  **Struct comparison** — for complex structs, use `cmp.Diff` from `github.com/google/go-cmp/cmp` rather than `reflect.DeepEqual`. Show import path explicitly. Note: this is a module dependency of the Go project under test, not of the skill file itself.

  **Package naming** — same-package tests (`package foo`) can access unexported identifiers. External tests (`package foo_test`) test only the exported API; preferred for library packages.

  **Conventions to specify per project** — same pattern as csharp-testing (test directory, fixture strategy, integration test markers).

  End the file with: `<!-- Project-specific testing configuration goes here -->`
- **Commit:** `feat(go-plugin): add go-testing SKILL.md`

## Batch Tests

`verify: null` — this batch creates pure Markdown and JSON files with no compilable or runnable test surface. Correctness is verified by code review: all six files exist at their expected paths, the two JSON files parse without error, each SKILL.md has valid frontmatter with `name:` and `description:` fields, and no file contains the strings `csharp` or `python` in its content.
