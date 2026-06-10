# Plan: Add Go skill package (build, test, comments)

```yaml
task: "Add Go skill package (build, test, comments)"
slug: golang-skills
approved: false
started: 20260610-070413
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: Create Go plugin files
    file: 01-create-go-plugin-files.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: C# is the style reference

- **Decision:** All skill file content follows the C# module's style — tighter, more prescriptive, direct rules with good/bad examples.
- **Rationale:** User confirmed the C# module produces code they would write themselves. Python module style is explicitly rejected.
- **Applies to:** all batches

### Decision: Extra-detailed doc comment policy

- **Decision:** `go-comments` SKILL.md requires doc comments that explain what + why + how. Inline comments explain why and optionally what when non-obvious, without overdoing it.
- **Rationale:** User is learning Go; the codebase should serve as a learning resource.
- **Applies to:** all batches

### Decision: No references to csharp or python in new files

- **Decision:** New Go plugin files must not contain the strings `csharp` or `python` (case-insensitive) in their content.
- **Rationale:** The Go plugin is standalone; leaking reference names into content confuses future readers.
- **Applies to:** all batches

## All Files Touched

- `plugins/go/.claude-plugin/plugin.json`
- `plugins/go/settings.json`
- `plugins/go/skills/INDEX.md`
- `plugins/go/skills/go-build/SKILL.md`
- `plugins/go/skills/go-comments/SKILL.md`
- `plugins/go/skills/go-testing/SKILL.md`
