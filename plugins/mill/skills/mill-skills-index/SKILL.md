---
name: mill-skills-index
description: Regenerate SKILLS.md at the repo root from SKILL.md frontmatter. Manual invocation only — no pre-commit hook.
---

# mill-skills-index

Regenerate `SKILLS.md` by scanning `plugins/*/skills/**/SKILL.md` for YAML frontmatter (`name:` and `description:`) and writing a combined table at the repo root.

v2 only writes the root `SKILLS.md` — per-plugin `INDEX.md` files from v1 are dropped. The scanner is deterministic — sorted alphabetically by skill name, `\n`-only line endings, trailing newline. Re-running produces byte-identical output.

## Usage

```
/mill-skills-index
```

## Steps

1. **Run the scanner.** v2's flat-layout entrypoint is `plugins/mill/scripts/millpy-skills-index.py`:

   ```bash
   uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-skills-index.py"
   ```

2. **Parse stdout.** The entrypoint prints a one-line summary followed by the list of written file paths. Relay that list to the user.

3. **Stage and commit** the generated file:

   ```bash
   git add SKILLS.md
   git commit -m "chore: regenerate SKILLS.md"
   git push
   ```

## Rules

- Missing or malformed frontmatter on any SKILL.md emits a warning to stderr and skips that file — the scanner never raises.
- The skill is manual-only. No pre-commit hook, no auto-fire.
- The frontmatter is the source of truth; `SKILLS.md` is a view. Do not hand-edit it — edit the underlying `SKILL.md` files and regenerate.
