# Discussion: Add Go skill package (build, test, comments)

```yaml
task: Add Go skill package (build, test, comments)
slug: golang-skills
status: discussing
parent: main
```

## Problem

The millhouse plugin ecosystem has skill packages for C# and Python that guide Claude's code style, documentation, and testing conventions. Go has no equivalent. When working on a Go project with millhouse loaded, Claude falls back to generic behavior — writing comments in whatever style it feels like, using inconsistent test patterns, and running whatever build commands seem reasonable.

The user is new to Go and learning the language. Standard Go code is required, but doc comments should be extra detailed — explaining what a function does, why it exists, and how it works — so the codebase doubles as a learning resource. The C# module is the quality reference: that module produces code the user would write themselves.

## Scope

**In:**
- New `plugins/go/` directory with the same layout as `plugins/csharp/`
- `plugin.json` and `settings.json` for the plugin
- `skills/INDEX.md` listing all three skills
- `skills/go-comments/SKILL.md` — godoc and inline comment conventions
- `skills/go-build/SKILL.md` — complete build/lint/test workflow
- `skills/go-testing/SKILL.md` — table-driven test conventions using the standard `testing` package

**Out:**
- No changes to the C# or Python plugins
- No code generation templates or snippets
- No project-specific configuration (the skill files are generic; per-project overrides go in the comment placeholder at the bottom of each file, identical to how C# does it)
- No mill-config changes
- No codeguide integration

## Decisions

### Plugin name: `go`

- Decision: Name the plugin `go`, skills namespaced as `go:go-build`, `go:go-comments`, `go:go-testing`.
- Rationale: Mirrors the `csharp` naming pattern exactly. Short, unambiguous.
- Rejected: `golang` — longer, and the language itself uses `go` as its tool name.

### Modeled on C#, not Python

- Decision: The C# module is the structural and style reference. The Python module is explicitly not the reference.
- Rationale: The user is satisfied with the code Claude produces under the C# skill. The Python module produces output the user is not happy with. The C# module is tighter, more prescriptive, and produces code that feels idiomatic to the user.
- Rejected: Python-style narration of every step — too verbose, not what the user wants.

### Doc comments: extra detailed

- Decision: All exported symbols must have godoc comments that explain what + why + how. More detailed than typical Go style. Inline comments explain why (and optionally what when the operation is non-obvious), but without overdoing it.
- Rationale: User is learning Go. The codebase serves as a learning resource. "Extra detailed but don't overdo it" — every logical block gets a comment when it would otherwise be opaque, but trivial operations need nothing.
- Rejected: Minimal godoc (name + one-liner only) — too sparse for a learning context.

### Test library: standard `testing` package only

- Decision: Use Go's standard `testing` package. For struct comparison, use `cmp.Diff` from `github.com/google/go-cmp/cmp`. No testify.
- Rationale: "De facto standard" — the user asked for this. The standard library is what all official Go style guides use. Testify is popular but adds a dependency and obscures idiomatic Go patterns that are worth learning.
- Rejected: testify — adds `require.*`/`assert.*` abstractions that hide standard Go error reporting patterns.
- Note: `google/go-cmp` is a dependency only of Go projects that use these skill files as guidance — the skill files themselves are pure Markdown documentation; no `go.mod` is required in the plugin directory.

### Build workflow: complete

- Decision: `go-build` prescribes a complete workflow: `goimports -w .` → `go vet ./...` → `go build ./...` → `go test ./...` → `golangci-lint run`.
- Rationale: User explicitly chose the complete option over the minimal C#-style approach. The full workflow enforces formatting, catches bugs statically, and runs tests in one pass.
- Rejected: Minimal (vet + test only) — user chose completeness.

### Table-driven tests with `t.Run`

- Decision: All tests with multiple scenarios use table-driven style with `t.Run` subtests. Test slice named `tests`, each entry `tt`.
- Rationale: This is the idiomatic Go pattern, endorsed by the standard library itself, the Google style guide, and Uber's guide. It allows running individual cases with `-run TestFoo/case_name`.
- Rejected: Individual test functions per scenario — verbose, harder to extend.

## Technical context

The plugin lives at `plugins/go/` inside the golang-skills worktree, which already contains the equivalent `plugins/csharp/` and `plugins/python/` directories. The exact file tree to replicate:

```
plugins/go/
  .claude-plugin/
    plugin.json          ← name, description, version, license, author
  settings.json          ← permissions: allow Skill(go:*)
  skills/
    INDEX.md             ← table of all three skills
    go-build/
      SKILL.md
    go-comments/
      SKILL.md
    go-testing/
      SKILL.md
```

Reference file: `plugins/csharp/.claude-plugin/plugin.json` — copy structure, change name/description.
Reference file: `plugins/csharp/settings.json` — copy, change `csharp` → `go`.
Reference file: `plugins/csharp/skills/csharp-comments/SKILL.md` — the style template for comment rules.
Reference file: `plugins/csharp/skills/csharp-build/SKILL.md` — carries the `<!-- Project-specific ... -->` placeholder that **all three** Go SKILL.md files must end with. Note: `csharp-comments/SKILL.md` does NOT have this placeholder; do not use it as the reference for the placeholder — use `csharp-build/SKILL.md` instead.

Go-specific technical facts mill-plan needs:

**Godoc format:**
- `//` line comments only (no `/* */` inside functions)
- Placed immediately before the declaration — no blank line between comment and declaration
- First sentence is the summary used by `go doc` and IDEs — must start with the name of the thing
- Package comment starts with `Package <name>`
- Boolean functions: "reports whether", not "returns true if"
- Doc links: `[TypeName]` for same-package symbols, `[pkg.TypeName]` for external

**Build tool chain (in order):**
1. `goimports -w .` — formats code AND manages imports (superset of `gofmt`)
2. `go vet ./...` — static analysis for common bugs
3. `go build ./...` — compilation check
4. `go test ./...` — run tests
5. `golangci-lint run` — unified linter (covers errcheck, revive, staticcheck, etc.)

`goimports` and `golangci-lint` are not part of the standard Go toolchain and must be installed separately:
- `go install golang.org/x/tools/cmd/goimports@latest`
- `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`

The go-build SKILL.md must include these install commands and instruct Claude to report "golangci-lint not found — install with the command above" rather than failing silently if the binary is missing. Mirror the C# build skill's test-discovery guidance pattern.

**Error handling (for go-comments):**
- `fmt.Errorf("context: %w", err)` — `%w` wraps for `errors.Is`/`errors.As`
- `%v` at system boundaries to hide internals
- Error strings: lowercase, no trailing punctuation

**Test pattern:**
```go
func TestFoo(t *testing.T) {
    tests := []struct {
        name  string
        input int
        want  int
    }{
        {"zero", 0, 0},
        {"positive", 5, 10},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got := Foo(tt.input)
            if got != tt.want {
                t.Errorf("Foo(%d) = %d; want %d", tt.input, got, tt.want)
            }
        })
    }
}
```

## Constraints

No `CONSTRAINTS.md` present in this worktree.

- Plugin files must be pure Markdown + JSON — no scripts, no Python.
- Skill files follow the SKILL.md frontmatter convention: `---\nname: ...\ndescription: ...\n---`.
- The `settings.json` permission entry must match the pattern in other plugins exactly.
- Each SKILL.md ends with a `<!-- Project-specific configuration goes here -->` comment block (same as C# and Python), so per-project overrides can be appended without modifying the base file.

## Testing

These are static text files — no automated tests. Mill-plan should verify:

- All five files exist at the correct paths after the task
- `plugin.json` is valid JSON
- `settings.json` is valid JSON with the correct permission entry
- Each SKILL.md has valid frontmatter (name + description fields)
- No references to `csharp` or `python` remain in the new files (grep check)

## Q&A log

- **Q:** Inline comments — C#-style why-only or narrate every step? **A:** Extra detailed but don't overdo it. Explain each logical step when it would be opaque, but skip the trivial.
- **Q:** Test assertion library — standard library or testify? **A:** Use the de facto standard (standard `testing` package + `cmp.Diff`).
- **Q:** go-build scope — minimal like C# or complete workflow? **A:** Complete: `goimports` + `go vet` + `go build` + `go test` + `golangci-lint`.
