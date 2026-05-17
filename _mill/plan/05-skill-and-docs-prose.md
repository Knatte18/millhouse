# Batch: skill-and-docs-prose

```yaml
task: 59 (A) -- Small infra fixes batch 8
batch: skill-and-docs-prose
number: 5
cards: 5
verify: null
depends-on: [1, 2]
```

## Batch Scope

Pure documentation batch: SKILL.md prose changes for the existing mill skills, signature lines documenting the helper APIs added in Batch 1, a CLAUDE.md path-invariant note for #318, and the marketplace investigation deliverable for #307. Five small cards in one batch because each is a couple of lines of prose and reviewing them together is cheaper than splitting. `verify: null` because docs have no runnable surface; the holistic plan reviewer is the verification.

Depends on Batches 1 and 2 because Card 9 cites the helper signatures those batches ship. Drafting Card 9 ahead of those batches would risk documenting a stale signature if the implementer adjusts the API during Batch 1.

## Cards

### Card 7: mill-start GAPS_FOUND branch commits review files (#309)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/skills/mill-start/SKILL.md`, Phase: Discussion Review step 5 (current line 124): change the embedded shell command from `git -C <worktree> add <discussion_path> && git commit -m "mill-start: discussion-gap-fix round {N} for {slug}"` to `git -C <worktree> add <discussion_path> <reviews_dir>/ && git commit -m "mill-start: discussion-gap-fix round {N} for {slug}"`. The git-add now stages the new review file along with the updated discussion. Single substring replacement; preserve every other character in step 5 verbatim (including the surrounding inline-backtick code block syntax). No other section changes in this card.
- **Commit:** `fix(mill-start): commit review files on GAPS_FOUND path (#309)`

### Card 8: mill-go remove contradictory mill-receiving-review Builder load instruction (#311)

- **Context:**
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/skills/mill-go/SKILL.md`, apply four focused edits to remove the contradiction between the Builder-flow body and the Principles bullet at line 394 (`Implementer owns receive-review.`):
  1. Execute step 3 (current line 203): replace `3. **Before reading any review file, load the \`mill-receiving-review\` skill.** Non-negotiable.` with `3. **Builder reads only the JSON envelope verdict, never the findings.** Loading \`mill-receiving-review\` is the dispatched implementer's job (see Principles below). Builder does not load the skill.`
  2. Execute step 4, `NEED_CONTEXT` branch (line 207): append the sentence `Reading the structured \`## Missing context\` bullet list does not require \`mill-receiving-review\` -- only finding-handling does.` to the end of the existing `NEED_CONTEXT` bullet, after the `notify` signature line. Keep all other behaviour identical.
  3. Holistic step 5 (current line 343): replace `5. On \`REQUEST_CHANGES\`: **Load \`mill-receiving-review\` before reading any finding.** Dispatch:` with `5. On \`REQUEST_CHANGES\`: the holistic-fix CLI dispatches a fresh implementer; the implementer loads \`mill-receiving-review\` (see Principles below). Builder does not load the skill. Dispatch:`. Preserve the bash block that follows.
  4. Resume step 4 (current line 282): replace `4. **\`mill-receiving-review\` is still mandatory.** When resume lands you at any point that reads a review file, load the skill first (per the existing rule at Execute step 3 sub-step 3 and Holistic step 5).` with `4. **\`mill-receiving-review\` remains the implementer's responsibility.** When resume re-dispatches the implementer (\`millpy-implement.py --resume ...\`), the fix-prompt itself instructs the implementer to load the skill before reading findings. Builder still does not load it.`
  The Principles bullet at line 394 stays as the canonical statement; no edit there. The other Principles bullets stay unchanged.
- **Commit:** `fix(mill-go): clarify mill-receiving-review is implementer-only (#311)`

### Card 9: Document new helper signatures in mill-plan and mill-start SKILL.md (#295, #296)

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Both SKILL.md files document helper signatures inline (the convention from CLAUDE.md `## Conventions worth carrying`: `Helper signatures are documented inline. Every helper this skill names has an explicit one-line signature in the section that calls it.`). Add the three new signature lines:
  1. In `plugins/mill/skills/mill-plan/SKILL.md`, Entry section, locate the existing line `\`signature: _config.load_config(wiki_path: Path, worktree_root: Path) -> dict\`` (between Entry steps 3 and 4). Immediately after that line, add `\`signature: _paths.resolve_git_root(start: Path | None = None) -> Path\`` and `\`signature: _paths.resolve_wiki_path(git_toplevel: Path) -> Path\`` on consecutive lines.
  2. In the same file, Phase: Plan section, find the line `**Update \`_mill/status.md\`.**` (after the self-validate DAG block). Immediately above that line, add `\`signature: _status.read(status_path: Path) -> dict\`` -- callers may want to read the current status before mutating it.
  3. In `plugins/mill/skills/mill-start/SKILL.md`, Entry section, locate the existing line `\`signature: _wiki.sync_pull(wiki_path: Path, *, slug: str) -> None\`` (Entry step 1). Below the `_config.load_config` signature line (Entry step 3), add `\`signature: _paths.resolve_git_root(start: Path | None = None) -> Path\`` and `\`signature: _paths.resolve_wiki_path(git_toplevel: Path) -> Path\``.
  The implementer should verify the signatures match the actual function definitions that landed in Batch 1 (`_status.py` line for `read`, `_paths.py` line 115 for `resolve_git_root`). Use the exact return types and argument shapes from those landed functions; if Batch 1's review caused any signature drift, this card's signature lines must reflect what shipped.
- **Commit:** `docs(skills): add signature lines for _status.read and resolve_git_root (#295, #296)`

### Card 10: CLAUDE.md path-helper config-lookup invariant (#318)

- **Context:**
  - `plugins/mill/scripts/_setup.py`
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `CLAUDE.md`, locate the section `## Path invariants` (somewhere after `## Constraints`). At the end of that section, add a new bullet: `- **Helpers that take a path argument MUST NOT consult cwd for config.** Route the explicit path through to any inner config lookup. The bug surface is unit-test helpers that read the caller's mill-config.yaml instead of the fixture's. Already fixed in main during the config-move-to-hub squash via \`_wiki.read_junctions(wiki_path=...)\` / \`_wiki.read_hardlinks(wiki_path=...)\` accepting an optional \`wiki_path\` argument; \`_setup.create_hub_links\` now uses \`target_root\` as \`hub_root\` and threads \`wiki_path\` through (#318).`
  Preserve all existing bullets in that section; do not reorder. Single insertion at the end of the bullet list. ASCII-only output (no em-dashes).
- **Commit:** `docs(CLAUDE.md): codify path-helper config-lookup invariant (#318)`

### Card 11: Marketplace directory-source CLAUDE_PLUGIN_ROOT investigation + docs (#307)

- **Context:**
  - `.claude-plugin/marketplace.json`
- **Edits:**
  - `update-plugins.ps1`
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Three deliverables in one card, in order:
  1. **Investigate.** Determine why directory-source marketplaces resolve `CLAUDE_PLUGIN_ROOT` to the dev tree (`C:\Code\millhouse\wts\millhouse`) rather than the cache (`%USERPROFILE%\.claude\plugins\cache\millhouse\mill\2.0.0\`). Inspect: (a) `.claude-plugin/marketplace.json` for any `installLocation` / `source` field that would force directory mode; (b) `update-plugins.ps1` -- it already sets `CLAUDE_PLUGIN_ROOT` to the cache target via `[System.Environment]::SetEnvironmentVariable('CLAUDE_PLUGIN_ROOT', $target, 'User')` (line ~43), but Claude Code's own subprocess-env resolution may override this. (c) Compare a Process-level vs User-level scope; if CC is setting a Process-level CLAUDE_PLUGIN_ROOT that overrides User-level, document it. Capture the root cause in a one-paragraph note in the commit message body. Do not fabricate findings -- if the cause is non-discoverable from the code in this repo, say so plainly.
  2. **Fix if in-repo cause exists.** If the investigation surfaces an in-repo change (e.g., a missing flag in `update-plugins.ps1`, a wrong field in `marketplace.json`, or an `installLocation` value that needs to point at the cache), apply it. Otherwise leave both files unchanged in step 2 and proceed to step 3.
  3. **Document.** In `CLAUDE.md`, at the end of `## Conventions worth carrying`, add a new bullet starting `- **\`CLAUDE_PLUGIN_ROOT\` resolution on directory-source marketplaces:**` followed by 3-5 sentences capturing: where CC resolves the env var; whether it overrides `update-plugins.ps1`'s User-level setting; the workaround (run from cache OR set a Process-level override) if no in-repo fix exists. In `update-plugins.ps1`, add a header comment line (after the existing 5-line introductory comment block at the top of the file) documenting the same: which scope it sets and what scope Claude Code uses. Both notes must be ASCII-only.
  The investigation is bounded: spend no more than 2-3 commits of attempts before settling on "document the workaround". If you find a fix, apply it; if you do not, state that plainly in the docs and commit message.
- **Commit:** `docs(marketplace): investigate directory-source CLAUDE_PLUGIN_ROOT resolution (#307)`

## Batch Tests

`verify: null`. Documentation changes have no automated assertion shape. The plan reviewer and the eventual code reviewer verify the prose changes. Manual verification on the operator side: (a) re-read mill-start GAPS_FOUND branch and confirm `git status` after a synthetic gap-fix shows reviews/ committed; (b) re-read mill-go SKILL.md and confirm Builder and Principles agree; (c) re-read the new CLAUDE.md path-invariant; (d) for #307, the in-repo doc plus any code fix.
