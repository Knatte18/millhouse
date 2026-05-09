---
name: codeguide-update
description: "Update docs for recently changed source files. Default: current git diff. Lightweight, safe for commit-time use."
argument-hint: "[1h | 3d | HEAD~3 | file1 file2 ...]"
---

Update `_codeguide/` docs for source files that changed recently. Designed to be fast and non-intrusive — only touches docs for files in scope.

Commit behavior is mode-aware:
- **Inline mode** → `codeguide_commit.py` stages doc files in the current repo. The outer `@git-commit` skill that invoked us will commit them alongside the source changes.
- **Sibling mode** → `codeguide_commit.py` stages AND commits doc files inside the sibling repo (its own history). The outer `@git-commit` must NOT try to stage sibling-rooted paths.

## Resolution

Before doing anything else, run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py --json` to find the codeguide root for this repo. The script prints a JSON object: `{mode, cg_root, sibling_anchor, found}`. If `found == false`, halt and tell the user to run `/codeguide-setup` first.

## Scope

`$ARGUMENTS` controls which source files are in scope:

- No argument → files in the current git diff (staged + unstaged). This is the default when called by `@git-commit`.
- `1h`, `3d`, `2w` → files with git commits in the last hour / 3 days / 2 weeks
- `HEAD~3` → files changed in the last 3 commits
- Explicit file/folder paths → only those

## Steps

1. **Resolve per file → group by cg-root.** For each source file in scope, run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py --json` from that file's directory to get `{mode, cg_root, sibling_anchor}`. Group files whose resolve result shares the same `cg_root`. Files with `found == false` (no governing codeguide) → flag and skip.

   Most repos have a single root codeguide, so typically you get one group. Multi-codeguide repos (repo-level + one-or-more subfolder workspaces) get one group per subtree.

2. **For each group** — each group has its own `mode`, `cg_root`, and (for sibling) `sibling_anchor`:

   a. **Read config:** Load source extensions from `<cg_root>/config.yaml`. Filter the group's files to recognized source extensions only.

   b. **Read `cgignore.md` and `cgexclude.md`:** Skip files matching ignore or exclude patterns.

   c. **Read the Documentation Guide:** `<cg_root>/modules/DocumentationGuide.md`.

   d. **Read local rules:** `<cg_root>/local-rules.md` if it exists.

   e. **For each source file in the group's filtered scope:**

      - Find the corresponding doc using the guide's naming rules (two-step lookup via Overview.md).
      - **If doc exists:** Read the doc and the source file. If the doc is stale or inaccurate, update it. Preserve accurate content.
      - **If no doc exists and not in cgexclude:** Create it following the guide structure. Update the Overview.md module table.
      - **If source was deleted** (only applies to git diff scope): Flag the orphan doc to the user. Do not delete it.

   f. **Update Overview.md routing tables** if any docs were added or if routing hints changed.

   g. **Stage / commit for this group:** Collect all absolute paths of docs that were created or updated for this group into a `--file` list. Run:

      ```
      python ${CLAUDE_PLUGIN_ROOT}/scripts/codeguide_commit.py \
        --mode <group-mode> \
        [--sibling-anchor <group-sibling-anchor>] \
        --file <path> [--file <path> ...] \
        -m "codeguide-update: <summary>"
      ```

      Pass the `mode` and (if sibling) `sibling-anchor` that resolve.py returned for THIS group. Never re-invoke `resolve.py` from the helper.

3. **Report** per group: cg_root, mode, files updated/created/flagged. In sibling mode, report the sibling commit SHA for traceability.

## Rules

- Read the Documentation Guide and local rules first — do not rely on memory.
- Do not touch docs outside the scope.
- Do not include API signatures, code-derived values, or line-by-line walkthroughs.
- Inline mode: do NOT commit (the outer `@git-commit` does that). `codeguide_commit.py --mode inline` only stages.
- Sibling mode: `codeguide_commit.py --mode sibling` stages + commits in the sibling repo. One commit per group.
- Multi-codeguide: always process each cg-root's group with its own mode + anchor, never a mixed call.
