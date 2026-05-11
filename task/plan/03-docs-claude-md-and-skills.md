# Batch: docs-claude-md-and-skills

```yaml
task: 49 (A) — Defensive guards mot cwd-inni-wiki kjedereaksjoner
batch: docs-claude-md-and-skills
number: 3
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Adds two pieces of documentation: (a) a new invariant bullet in CLAUDE.md's `## Path invariants` section plus a new `## Wiki access` section with the four-row anti-pattern table, and (b) a single-line wiki-access note at the top of each of the eight named SKILL.md files (mill-start, mill-plan, mill-go, mill-merge, mill-wiki-push, mill-setup, mill-claim, mill-spawn). The two cards split CLAUDE.md edits from the eight-file SKILL.md sweep so each card has a focused review surface.

`verify: null` because both cards are pure documentation — there is no runnable surface to gate. Batch 2's walker test allowlists every file touched here, so the anti-pattern strings the new content quotes do not regress that test.

Batch-local decision: the per-SKILL.md note is a single line placed immediately under the H1, alongside any pre-existing leading note. The literal text is `> Wiki access: never \`cd .wiki/\`. Use the documented helpers — see CLAUDE.md \`## Wiki access\`.` (Markdown blockquote, single line). Same text in all eight files for grep uniformity.

## Cards

### Card 8: Add cwd invariant + `## Wiki access` section to CLAUDE.md

- **Context:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Make two additions to `CLAUDE.md`:
    1. Append a new bullet to the existing `## Path invariants` section (immediately after the last existing bullet — the one starting `**Scratch lives at`). The new bullet:
       > **cwd is always cwd, and scripts never rewrite it.** Wiki mutations go through `git -C <wiki_path>` or `_wiki.write_commit_push` — never by changing cwd to wiki. If a script detects cwd is inside the wiki clone, it halts with a clear `SystemExit` (or `ValueError` for `_sibling.resolve_path`): that is operator error, not something to recover from. Enforced by `_paths.resolve_git_root` (name + path-equality check), `_paths.resolve_wiki_path` (name check), and `_sibling.resolve_path` (name check; mirrored to the codeguide twin). Regression-guarded by `plugins/mill/unit_tests/test-no-wiki-cwd.py`.
    2. Insert a new top-level section `## Wiki access` immediately after the `## Path invariants` section (so it appears between `## Path invariants` and whatever currently follows in the file — verify current file structure when editing). The section opens with one short paragraph: `Scripts mutate the wiki only through \`_wiki.write_commit_push\` or \`git -C <wiki_path>\` inside a \`_wiki.wiki_lock\` block. Reads go through helper APIs (\`_wiki.sync_pull\`) or \`read_text(wiki_path / …)\`. Never \`cd\` into the wiki, never set \`cwd=<wiki_path>\` in a subprocess.` followed by a markdown table with this exact header and the four data rows from the discussion:

       ```markdown
       | Anti-pattern | Correct replacement |
       |---|---|
       | `cd .wiki/ && git pull --ff-only` | `_wiki.sync_pull(wiki_path)` |
       | `cd .wiki/ && git <anything>` | `git -C <wiki_path> <anything>` |
       | `cd .wiki/ && cat <file>` | `read_text(wiki_path / "<file>")` |
       | `cwd=<wiki_path>` in subprocess | `cwd=<task_worktree>` + `git -C <wiki_path>` |
       ```

  Do NOT modify any other content in CLAUDE.md. Do NOT reorder existing sections. Preserve the existing line endings of CLAUDE.md.
- **Commit:** `docs(claude-md): add cwd-invariant bullet and Wiki access section`

### Card 9: Add wiki-access note to eight SKILL.md files

- **Context:**
  - `CLAUDE.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/skills/mill-wiki-push/SKILL.md`
  - `plugins/mill/skills/mill-setup/SKILL.md`
  - `plugins/mill/skills/mill-claim/SKILL.md`
  - `plugins/mill/skills/mill-spawn/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In each of the eight SKILL.md files listed under Edits, insert the literal line `> Wiki access: never \`cd .wiki/\`. Use the documented helpers — see CLAUDE.md \`## Wiki access\`.` as the first content line immediately after the H1 (the line starting with `# `). Insert one blank line above and one blank line below the new line, preserving any pre-existing leading content directly underneath. The note must be the FIRST non-H1 content; if the file currently has a different leading note, the new wiki-access note goes first and the existing note follows after one blank line. Use the exact text above (single-line markdown blockquote), same in every file for grep uniformity. Do NOT modify any other content in these files. Do NOT reorder existing sections.
- **Commit:** `docs(skills): add wiki-access note to eight task-flow SKILL.md files`

## Batch Tests

`verify: null`. No runnable surface — these are documentation-only edits. Manual smoke check: after the batch lands, `grep -rn "Wiki access:" plugins/mill/skills/` returns nine lines (one per SKILL plus the CLAUDE.md section header). The walker test in batch 2 still passes because every edited file is in its hardcoded allowlist.
