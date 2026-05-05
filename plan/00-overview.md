# Plan: '3 (A) — codeguide improvements: sibling placement + --branch flag'

```yaml
task: '3 (A) — codeguide improvements: sibling placement + --branch flag'
slug: codeguide-improvements
approved: false
started: 20260505-130128
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: codeguide-generate-skill
    file: 01-codeguide-generate-skill.md
    depends-on: []
    verify: null
  - name: codeguide-setup-skill
    file: 02-codeguide-setup-skill.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: SKILL.md prose only — no script changes

- **Decision:** Both batches modify only `SKILL.md` files. No Python scripts, no templates, no other files are touched.
- **Rationale:** The proposal explicitly states `resolve.py`'s sibling walk already handles the placement layout correctly (`anchor / rel / "_codeguide" / filename`), and the codeguide-setup CLI parsing is interpreted by the agent reading the SKILL.md, not a Python `argparse`. The scope rules out `resolve.py`, `_sibling.py`, and any other codeguide scripts.
- **Applies to:** all batches

### Decision: No verify command — pure docs

- **Decision:** `verify:` is `null` in both batches and at the plan level. Batch Tests sections describe manual integration verification only.
- **Rationale:** SKILL.md prose has no executable surface. Existing `plugins/codeguide/integration_tests/` does not cover SKILL.md content. Adding fake unit tests for prose would be cargo-culting.
- **Applies to:** all batches

### Decision: Use Edit tool for surgical changes, not Write

- **Decision:** Implementer uses `Edit` (find/replace) for each change, not `Write` (full-file overwrite). Each `Edit` call covers one logical change.
- **Rationale:** Surgical edits keep the diff small and easy to review. Full overwrites risk silently dropping unrelated content.
- **Applies to:** all batches

### Decision: No backwards compatibility for old `--from-url` flag

- **Decision:** `--from-url` is removed outright from `codeguide-setup`. No alias, no deprecation note, no transition period. The argument-hint, Step 1 parsing, and any references in Step 4 are updated to the new `--sibling <url>` form.
- **Rationale:** Discussion `### --from-url redesign` explicitly rejected the alias option. SKILL.md is agent instructions, not a public CLI — there are no in-flight users.
- **Applies to:** codeguide-setup-skill

## All Files Touched

- `plugins/codeguide/skills/codeguide-generate/SKILL.md`
- `plugins/codeguide/skills/codeguide-setup/SKILL.md`
