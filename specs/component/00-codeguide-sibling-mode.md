# codeguide sibling-mode — docs outside the target repo

```yaml
type: plugin change (codeguide) + CLAUDE.md convention
layer: bookkeeping / external tooling
v1_ref: none — new capability
status: partially discussed — key decisions captured, not ready for full-write
note: "Let `_codeguide/` live in a sibling git repo (`<repo-parent>/<repo>.codeguide/`) instead of inside the target repo. Zero-footprint mode for repos where docs should not pollute the source tree. Wiki stays unaffected (already sibling). Mill-v2 unaffected at the skill-contract level — only the codeguide plugin changes."
priority: run before specs 07+. Triggered by the engineer's upcoming work on a third-party codebase where `_codeguide/` files cannot live in the main repo.
```

**For the thread that will do the full-write:** these notes are *starting points*, not a finished spec. Grill Henrik further on the Open design points before writing plan or code. Treat the existing `plugins/codeguide/` plugin as the primary reference — most of this spec modifies it rather than adding new surface. The Millhouse hub itself (this repo) is not seeded with `_codeguide/` during this work; per project convention we wait until mill-v2 can drive that seed through its own workflow.

## Problem

`_codeguide/` files inside the target repo cause friction in two scenarios:

1. **Third-party repos** the engineer does not own and does not want to clutter with Claude-Code-specific docs. Example: the NORCE codebase referenced in discussion — Chief Engineer approved use of CC but the team does not want `_codeguide/` directories committed to their source tree.
2. **Repos where a gitignored `_codeguide/` caused problems before:** `git-commit` skill's per-commit sync sometimes force-staged ignored files, creating surprise commits. Accepting inline-and-ignored is fragile.

Sibling layout — `<parent>/<repo>.codeguide/` as its own git repo — sidesteps both: zero files in the target repo, full version control on the docs, consistent with Millhouse's existing wiki pattern (`<parent>/<repo>.wiki/`).

## Decisions

- **Two modes, user-chosen at setup time:**
  - **Inline** (current default): `<repo>/_codeguide/` inside the target repo. Committed with source via `git-commit` skill.
  - **Sibling**: `<repo-parent>/<repo>.codeguide/` as its own git repo. Committed independently.
- **Location resolution — `resolve.py` walks up from cwd:**
  - For each level between cwd and git-toplevel (inclusive):
    - Try inline: `<level>/_codeguide/Overview.md`.
    - Try sibling-mirror: `<git-parent>/<repo>.codeguide/<rel-path>/_codeguide/Overview.md` where `<rel-path>` is the path from git-toplevel to `<level>`.
  - First match wins.
  - Env var `CODEGUIDE_ROOT`, when set, replaces `<git-parent>/<repo>.codeguide/` with its value. Rare — only for oddball layouts where sibling convention cannot apply.
  - No match at any level → "run /codeguide-setup first".
- **Multi-codeguide support:** the mirror scheme handles it naturally — if `src/csharp/NORCE.Models/` runs setup with `--sibling`, its codeguide lives at `<sibling>/src/csharp/NORCE.Models/_codeguide/`. A second subfolder gets its own `_codeguide/` at the mirrored path. First-to-setup triggers `git init` on the sibling repo; later setups just `mkdir` + commit inside it.
- **Subfolder-init respects git-toplevel:** every path computation in `codeguide-setup` and `resolve.py` anchors on `git rev-parse --show-toplevel`, not on cwd. Running `/codeguide-setup --sibling` from `Models/src/csharp/NORCE.Models/` places the codeguide at `Models.codeguide/src/csharp/NORCE.Models/_codeguide/`, not at `src/csharp/NORCE.Models.codeguide/`.
- **Sibling is always its own git repo.** `codeguide-setup` handles `git init` automatically on first use (analogous to how `mill-setup` handles the wiki clone). Optional `--from-url <git-url>` clones an existing remote instead.
- **Monorepo-branch pattern is NOT a dedicated mode.** Users who want "one GitHub repo, many codeguides as branches, worktree-checkout per active one" handle the git plumbing themselves and pass `--sibling <path>` to setup. Keeps the plugin scope small; the worktree-per-branch pattern is a user-level choice, not a plugin responsibility.
- **Commit discipline splits by mode:**
  - **Inline:** unchanged. `git-commit` step 2 stages codeguide files alongside source.
  - **Sibling:** `codeguide-update` calls a new helper (`${CLAUDE_PLUGIN_ROOT}/scripts/millpy/codeguide/codeguide_commit.py`) that does `git -C <sibling> add … && git -C <sibling> commit -m "…"` rooted in the sibling repo. `git-commit` step 2 still invokes `codeguide-update` but does not try to stage its output — the helper already committed in the other repo.
- **Never assume the millhouse source repo is cloned.** All plugin scripts reference `${CLAUDE_PLUGIN_ROOT}` for their own files. A session running on a third-party repo with `codeguide` installed must work with nothing on disk but the plugin install + the target repo + the sibling repo (if in sibling mode).

## Flow — sibling setup first-time

1. User runs `/codeguide-setup --sibling [--from-url <git-url>] [.cs .ts …]` from any directory inside the target repo.
2. `resolve.py` computes: `repo_root = git rev-parse --show-toplevel`, `rel = cwd.relative_to(repo_root)`, `sibling_root = repo_root.parent / f"{repo_root.name}.codeguide"`, `cg_anchor = sibling_root / rel`.
3. If `sibling_root` does not exist:
   - `--from-url` set → `git clone <url> <sibling_root>`.
   - otherwise → `mkdir sibling_root`, `git init`, initial empty commit.
4. `mkdir -p cg_anchor`. Copy plugin-owned template files (`DocumentationGuide.md`, `cgignore.md`, `config.yaml` etc.) into `cg_anchor / "_codeguide/"`.
5. `git -C sibling_root add <cg_anchor>/_codeguide/`, commit with "codeguide-setup: init <rel-path>".
6. Report the sibling path to the user.

## Flow — sibling update

`codeguide-update` after any source file changes:

1. `resolve.py` finds the relevant `_codeguide/` for the files in the staged diff (walks up from each changed file).
2. Update the doc files inside `_codeguide/` according to the scope rules in the existing skill (DocumentationGuide, config, ignore, exclude).
3. Instead of staging into the current repo, call `codeguide_commit.py` with the sibling-repo path and the list of updated doc files. The helper runs `git add` + `git commit` inside the sibling repo.
4. Report what was updated.

## Backend

**New / to add:**
- `${CLAUDE_PLUGIN_ROOT}/scripts/millpy/codeguide/codeguide_commit.py` — mode-aware commit helper. Inline mode → `git add` inside target repo, leaves commit to outer `git-commit` skill. Sibling mode → `git -C <sibling> add && commit`. Reads mode from `resolve.py`'s result.
- `codeguide-setup` gains `--sibling` and `--from-url` flags.

**Modified:**
- `${CLAUDE_PLUGIN_ROOT}/scripts/millpy/codeguide/resolve.py` — extend lookup chain: inline level N → sibling-mirror level N → next level up. Return structured result including mode (inline/sibling), `_codeguide/` path, and sibling repo root if applicable.
- `plugins/codeguide/skills/codeguide-setup/SKILL.md` — sibling mode step. Auto-init or clone the sibling repo. Subfolder support: create mirrored path.
- `plugins/codeguide/skills/codeguide-update/SKILL.md` — final step switches from "stage files" to "call codeguide_commit.py".
- `plugins/mill/skills/git-commit/SKILL.md` step 2 — comment that codeguide-update handles its own commit in sibling mode, so `git-commit` must not attempt to stage codeguide files when in sibling mode.
- `CLAUDE.md` — add hard rule: "All plugin-installed scripts reference `${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths. Never assume the millhouse source repo is cloned on the user's machine." (Later migrates to `CONSTRAINTS.md` when mill-v2 is mature.)

**Reused / already exists:**
- Existing codeguide-setup "new subfolder activation" mode (`_codeguide/root.txt` pointer) continues to work for the *shared-codeguide-from-subfolder* use-case. Independent per-subfolder codeguides are the new path this spec adds.
- `plugins/mill/scripts/_parent_branch.py` pattern (git-toplevel-based resolution) is directly applicable.

## Out of scope vs. current codeguide plugin

- No GUI / interactive branch-picker when `--from-url` points at a monorepo with many branches. User picks the branch via `<url>#<branch>` or a separate `--branch` flag — TBD in full-write.
- No automatic migration from inline → sibling. A user who decides to switch after the fact moves the files manually and re-runs setup with `--sibling`.
- No CC-driven auto-seed of the hub (Millhouse) repo's own codeguide. That is spec `13-mill-codeguide.md` and remains deferred until mill-v2 self-sufficiency.

## Open design points

- **Mode persistence:** when `resolve.py` discovers a sibling, should it cache the result (e.g. in `<git-toplevel>/.git/info/codeguide-mode`) so subsequent skill invocations skip the walk? Probably yes for perf, but cache invalidation rules need specifying.
- **`codeguide-update` on a multi-codeguide repo:** if a source-commit touches files under two subfolders that each have their own codeguide, the skill must update both. Scope currently says "scan the staged diff" — confirm resolve.py handles the diff-file-to-codeguide mapping gracefully.
- **`codeguide-setup` refresh on an existing sibling:** what does `/codeguide-setup` do when invoked from a subfolder that already has a sibling-mirrored `_codeguide/`? "Root refresh" in current SKILL.md assumes inline. Sibling refresh needs equivalent semantics (overwrite plugin-owned files, keep user-owned).
- **`.gitignore` for the target repo:** should sibling-mode setup *optionally* add `/_codeguide/` to the target repo's `.gitignore` as a safety net against stray inline files? Probably yes, guarded by a flag to avoid surprise diffs.
- **`CODEGUIDE_ROOT` env var:** exact semantics. Override sibling-root only, or entire resolve chain? Lean toward "overrides sibling-root path", resolve chain otherwise unchanged.
- **Subfolder that previously used `root.txt` pointer in sibling mode:** spec says cg-workspaces still work. Confirm the subfolder activation flow in sibling mode creates the pointer correctly.
- **Verify + lint interactions:** `git-commit` step 1 is lint. When codeguide is sibling, does lint run in the target repo only, or also touch the sibling? (Likely target only — lint is about source code, not docs.)
- **Spec 13 (`mill-codeguide` placeholder) reference:** should be updated after this spec lands so it points to "sibling or inline" rather than assuming inline. Minor edit.

## References

- `plugins/codeguide/skills/codeguide-setup/SKILL.md` — current setup modes (first-time root, root refresh, subfolder refresh, new subfolder activation).
- `plugins/codeguide/skills/codeguide-update/SKILL.md` — current update flow that stages into the current repo.
- `plugins/mill/skills/git-commit/SKILL.md` step 2 — current "Codeguide sync" invocation of `@codeguide:codeguide-update`.
- Discussion thread in which this spec was grilled — key insights: monorepo-with-branches is acceptable for personal use (user manages plumbing), sibling is the right primitive, subfolder-init must anchor on git-toplevel, multiple independent subfolder codeguides must be supported, setup automates git-init/clone.
