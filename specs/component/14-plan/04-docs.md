# Batch: docs

```yaml
task: junction-rule enforcement + _paths.py consolidation
batch: docs
cards: 1
verify: null
depends-on: [callsite-migration, scratch-move]
```

## Batch Scope

Add a new `## Path invariants` section to `CLAUDE.md` — the whole point of this spec is that the junction rule and related path conventions have been getting forgotten, and a dedicated section in the session-start instructions is the cheapest durable fix.

Lands last so the section can describe the code as it IS after the other two batches, not as it was or will be.

## Cards

### Card 10: `CLAUDE.md` gains `## Path invariants`

- **Reads:** `CLAUDE.md`, `plugins/mill/scripts/_paths.py` (post-Card-1), `wiki/config.yaml` (accessible as `.millhouse/wiki/config.yaml` from hub root; the "Junctions are IDE/terminal convenience" invariant lives in its header comment, and the new CLAUDE.md text should quote it so it is findable in two places).
- **Modifies:** `CLAUDE.md`
- **Creates:** (none)
- **Requirements:**
  - Insert the new section between `## Conventions worth carrying` and the file's end (CLAUDE.md currently ends with the conventions section — the new section becomes the last top-level section).
  - Content (tight — three bullets, no prose preamble other than a one-line heading intent):

    ```markdown
    ## Path invariants

    Path rules that keep being forgotten — they live here, not spread across SKILL.md files.

    - **Junctions are IDE/terminal convenience only.** Scripts MUST resolve to the real wiki repo via `_paths.resolve_wiki_path(git_toplevel)`, never by treating `.millhouse/wiki` (or any junction) as a path. Junctions exist so the operator can type shorter paths in a shell and see the wiki in the sidebar — they are not a code contract. (The same invariant is documented in `wiki/config.yaml`'s header comment.)
    - **All path resolution goes through `_paths.py`.** The module re-exports `resolve_path` from `_sibling.py` (identical-twin with codeguide's copy per spec 00) and adds `resolve_git_root` + `resolve_wiki_path`. New path-resolver helpers go here too — do not scatter private `_resolve_*` functions across `mill-*.py` CLI scripts.
    - **Scratch lives at `<cwd>/.scratch/`, not under `.millhouse/`.** Shared with other plugins the engineer uses that default to top-level `.scratch/`. `.gitignore` covers it. Integration tests and SKILL.md prose reference `<cwd>/.scratch/` or just `.scratch/`. (Replaces the earlier `.millhouse/scratch/` rule under "Conventions worth carrying" — remove the old bullet there.)
    ```
  - Update "Repo layout pointers" in the same edit — TWO lines in that section mention the old scratch path:
    - Line 47 (the `integration_tests/` pointer) ends with "Use `.millhouse/scratch/` for fixtures." Change to "Use `.scratch/` for fixtures."
    - The `.millhouse/` pointer (bottom of the section) currently reads `- .millhouse/ in working clones is gitignored local state; .millhouse/wiki is a junction to the shared wiki repo.` Add a sibling line for `.scratch/`: `- .scratch/ in working clones is gitignored scratch-only state; not propagated to worktrees.`
  - Remove the `- **Never write to /tmp/ or $env:TEMP.** Use .millhouse/scratch/.` bullet from "Conventions worth carrying" — it's now part of the new Path invariants section with the updated path. The replacement bullet inside Path invariants already says the same thing.
  - Keep the file under the self-imposed `scope: this file is read on session start; keep it short` — if the total length of CLAUDE.md grows by more than ~15 lines net, consider whether the Path invariants bullets could be tighter.
- **Commit:** `docs(CLAUDE): add Path invariants section (closes spec 14)`

## Batch Tests

None. Pure markdown. Manual spot-check at commit time — the full verify from `00-overview.md` is the real gate.
