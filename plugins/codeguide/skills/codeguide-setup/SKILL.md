---
name: codeguide-setup
description: "Set up, refresh, or activate codeguide (inline or sibling). Detects context automatically: first-time root, refresh, or subfolder."
argument-hint: "[--sibling] [--from-url <git-url>] [.cs .py .ts]"
---

Set up or refresh codeguide for the current git repo. Two placement modes:

- **Inline** (default): files live inside the target repo, under `<repo>/_codeguide/`. `@git-commit` stages them alongside source changes.
- **Sibling** (`--sibling`): files live in a separate git repo next to the target repo — `<container>/<repo>.codeguide/` by default, or `<container>/codeguide/` when the target is hub-form (directory named exactly `hub`). The sibling repo has its own history. The target repo is never modified.

In both modes, any source-folder subtree can also carry its own `_codeguide/` (subfolder workspace) that points back to the root via `root.txt`. In sibling mode the subfolder's `_codeguide/` lives under the same relative path inside the sibling repo, not in the target repo.

Does **not** commit in inline mode. Commits in the sibling repo when in sibling mode (the sibling's history is independent).

## What this creates (first-time root)

```
<root>/_codeguide/
├── config.yaml                    ← source file extensions (you own this)
├── local-rules.md                 ← repo-specific doc rules (you own this)
├── Overview.md                    ← repo routing table (you own this)
├── cgignore.md                    ← system-level ignores (plugin-owned)
├── cgexclude.md                   ← module exclusions (you own this)
└── modules/
    └── DocumentationGuide.md      ← how to write docs (plugin-owned)
```

Where `<root>` is either the target repo (inline) or `<sibling-anchor>/<rel-path>/` (sibling).

## Steps

1. **Parse flags from `$ARGUMENTS`:**
   - `--sibling` → sibling mode
   - `--from-url <git-url>` → when creating the sibling repo for the first time, `git clone <git-url>` instead of `git init`. Ignored without `--sibling`.
   - Any tokens starting with `.` (e.g. `.cs .py`) → source extensions for `config.yaml`.

2. **Detect git toplevel:** Run `git rev-parse --show-toplevel`. If not in a git repo, stop with an error.

3. **Resolve existing codeguide state:** Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py --json` to locate the nearest `_codeguide/` with config.yaml. Parse the JSON: `{mode, cg_root, sibling_anchor, found}`.

4. **Compute target root** `<root>`:
   - Inline mode: `<root> = cwd` (first-time root) or whichever folder the resolve result points at.
   - Sibling mode:
     - Compute `<sibling-anchor>` by invoking `python ${CLAUDE_PLUGIN_ROOT}/scripts/_sibling.py codeguide <git-toplevel>` via subprocess. Parse the printed path.
     - If `.codeguide-root` exists at the git-toplevel, use its contents instead (single absolute or relative-to-toplevel path). Do NOT auto-create this file; users who want a non-default anchor write it themselves.
     - If `<sibling-anchor>` does not exist yet: create it with `git init`, OR `git clone <git-url> <sibling-anchor>` when `--from-url <url>` was given. Then `<root> = <sibling-anchor> / <rel-path>` where `<rel-path> = cwd.relative_to(git-toplevel)`.
     - If `<sibling-anchor>` already exists and is a git repo: `<root> = <sibling-anchor> / <rel-path>`.

5. **Determine mode (first-time / refresh / subfolder):**
   - `found == false` AND `<root>` has no `_codeguide/` → **first-time root setup**
   - `<root>` has `_codeguide/config.yaml` → **root refresh**
   - `found == true` and `<root>/_codeguide/root.txt` exists → **subfolder refresh**
   - `found == true` and `<root>` is under an ancestor's `_codeguide/` reach, but `<root>` has no `_codeguide/` OR has one without `root.txt` → **new subfolder** (ask user to confirm before proceeding)

---

### First-time root setup

6. **Check prerequisites:** Inline → verify cwd's git repo exists. Sibling → verify `<sibling-anchor>` is a git repo (created above if needed).

7. **Read plugin files** from `${CLAUDE_PLUGIN_ROOT}`:
   - `templates/DocumentationGuide.md`
   - `templates/config.yaml`
   - `templates/local-rules.md`
   - `templates/cgignore.md`
   - `templates/cgexclude.md`
   - `templates/codeguide-overview-starter.md`

8. **Create directories:** `<root>/_codeguide/modules/`.

9. **Copy plugin-owned files:**
   - `templates/DocumentationGuide.md` → `<root>/_codeguide/modules/DocumentationGuide.md`

10. **Create user-owned files** (only if they don't exist):
    - `<root>/_codeguide/cgignore.md` — copy from template (user adds repo-specific entries).
    - `<root>/_codeguide/config.yaml` — if `$ARGUMENTS` contained extensions, write a config with those extensions. Otherwise copy the template.
    - `<root>/_codeguide/local-rules.md` — copy from template.
    - `<root>/_codeguide/cgexclude.md` — copy from template.
    - `<root>/_codeguide/Overview.md` — read `templates/codeguide-overview-starter.md`, strip the leading HTML comment, and write the body.

11. **Commit (sibling mode only):** In the sibling repo, `git -C <sibling-anchor> add -A && git -C <sibling-anchor> commit -m "codeguide-setup: init <rel-path>"` (use `init root` when `<rel-path>` is empty).

12. **Report** what was created and where (inline vs sibling; print `<root>`).

---

### Root refresh

6. **Read plugin source files** from `${CLAUDE_PLUGIN_ROOT}`:
   - `templates/DocumentationGuide.md`
   - `templates/config.yaml`

7. **Overwrite plugin-owned files:**
   - `<root>/_codeguide/modules/DocumentationGuide.md`

8. **Merge config schema:** For each key in the template that is missing from `<root>/_codeguide/config.yaml`, add it with its default value and comment. Do not change existing values.

9. **Create `<root>/_codeguide/cgexclude.md`** if it doesn't exist.

10. **Commit (sibling mode only):** `codeguide-setup: refresh <rel-path>`.

11. **Report** what was updated.

---

### Subfolder refresh

6. **Update `<root>/_codeguide/root.txt`** with the current resolved path to the root `_codeguide/`.

7. **Create `<root>/_codeguide/cgexclude.md`** if it doesn't exist.

8. **Commit (sibling mode only):** `codeguide-setup: subfolder refresh <rel-path>`.

9. **Report** what was updated.

---

### New subfolder activation

6. **Report findings:** "Found root `_codeguide/` at `<path>` (mode: inline|sibling)." If `<root>` already has a `_codeguide/` directory without `root.txt`, add: "`<root>` already has `_codeguide/` with files: `<list>`. Promote this folder to a subfolder workspace without touching existing files?" Otherwise: "Set up this folder as a subfolder workspace?"

7. **Wait for user confirmation.** If denied, stop.

8. **Create `<root>/_codeguide/` directory** if it does not exist. If it already exists, leave existing files untouched — this step is the promote case.

9. **Create `<root>/_codeguide/root.txt`** with the resolved path to the ancestor `_codeguide/`.

10. **Create `<root>/_codeguide/cgexclude.md`** from template — only if it does not already exist.

11. **Commit (sibling mode only):** `codeguide-setup: activate subfolder <rel-path>`.

12. **Report** what was created (distinguish "created new subfolder workspace" vs "promoted existing `_codeguide/` to subfolder workspace").

## Rules

- Do not overwrite user-owned files: config.yaml values, local-rules.md, cgexclude.md, Overview.md, module docs.
- Inline mode: do not commit. Outer `@git-commit` stages and commits.
- Sibling mode: commit each change in the sibling repo as its own commit; the target repo is never touched.
- **Never modify the target repo in sibling mode.** Don't touch `.gitignore`, don't drop marker files, don't auto-create `.codeguide-root` — users who want that override file create it themselves.
- Safe to re-run in any mode. Plugin-owned files are refreshed, user-owned files are preserved.
