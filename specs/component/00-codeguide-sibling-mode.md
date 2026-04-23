# codeguide sibling-mode + unified sibling-path convention

```yaml
type: plugin change (codeguide) + _sibling.py helper + mill-config unification
layer: bookkeeping / external tooling
v1_ref: none — new capability
status: discussed — ready for plan-writing
note: "Let `_codeguide/` live in a sibling git repo next to the target repo. Same hub-form detection rule (`repo/.name == 'hub'`) unifies the naming convention across wiki, worktrees, and codeguide. Zero-footprint inside the target repo. Mill-v2 skill-contracts unaffected."
priority: run before specs 07+. Triggered by the engineer's upcoming work on a third-party codebase where `_codeguide/` files cannot live in the main repo.
```

## Scope summary (post-discussion)

Three logical pieces, all shipped together:

1. **`_sibling.py` helper in mill plugin** — single source of truth for where sibling dirs live (wiki, codeguide, worktrees). Hub-form detection: if the repo directory is literally named `hub`, use role-only paths (`<parent>/codeguide/`); otherwise prefix with repo dir name (`<parent>/<repo-name>.codeguide/`).
2. **Codeguide plugin gains sibling mode** — `_codeguide/` can live outside the target repo as its own git repo. Inline mode (current behaviour) stays as default. Resolution chain: inline first → `.codeguide-root` file override → sibling via hub-form rule → fail.
3. **Mill-setup and mill-spawn use `_sibling.py`** — removes the `spawn.worktrees_dir` token-template config default and the documented `<WIKI_PATH>` default, replacing both with the unified helper. Explicit overrides in `.millhouse/config.local.yaml` continue to work.

## Problem

`_codeguide/` files inside the target repo cause friction in two scenarios:

1. **Third-party repos** the engineer does not own and does not want to clutter with Claude-Code-specific docs. Example: the NORCE codebase referenced in discussion — Chief Engineer approved use of CC but the team does not want `_codeguide/` directories committed to their source tree.
2. **Repos where a gitignored `_codeguide/` caused problems before:** `git-commit` skill's per-commit sync sometimes force-staged ignored files, creating surprise commits. Accepting inline-and-ignored is fragile.

Sibling layout — `<parent>/<repo>.codeguide/` as its own git repo — sidesteps both: zero files in the target repo, full version control on the docs, consistent with Millhouse's existing wiki pattern (`<parent>/<repo>.wiki/`).

## Decisions (finalized)

### Hub-form detection rule — single string check

```python
def is_hub_form(repo_root: Path) -> bool:
    return repo_root.name == "hub"
```

The repo directory name is the entire signal. No heuristic on sibling presence, no config flag, no setup-time question. Existing Millhouse layout (`<container>/hub/`) triggers hub-form automatically; every other repo triggers prefix-form.

### `_sibling.resolve_path(role, repo_root)` — one helper; two identical copies

```python
def resolve_path(role: str, repo_root: Path) -> Path:
    parent = repo_root.parent
    if repo_root.name == "hub":
        return parent / role
    return parent / f"{repo_root.name}.{role}"
```

Applied uniformly to `role` in `{"wiki", "codeguide", "worktrees"}`.

**Two independent copies** — one per plugin — deliberately NO cross-plugin import:

- `plugins/mill/scripts/_sibling.py` — used by mill-spawn and by the mill-setup skill's subprocess calls. Exposes a CLI mode so the skill's prose can run `python ${CLAUDE_PLUGIN_ROOT}/scripts/_sibling.py <role> <repo_root>` to fetch the computed path.
- `plugins/codeguide/scripts/_sibling.py` — used by codeguide's own `resolve.py` and `codeguide_commit.py`. Identical 3-line logic.

Rationale: three lines of pure arithmetic. Duplicating across plugins avoids any assumption that mill and codeguide plugins install in a specific relative layout (which `${CLAUDE_PLUGIN_ROOT}/../mill/` would require). Plugin independence is the load-bearing property; minor duplication is the acceptable cost. If the rule ever changes, both files get the same edit — a linter check or a pre-merge grep can catch divergence.

### Codeguide — two modes, chosen at setup time

- **Inline** (default): `<repo>/_codeguide/` inside the target repo. Committed with source via `@git-commit` skill's pre-commit step 2. Current behaviour, unchanged.
- **Sibling**: `_sibling.resolve_path("codeguide", repo_root)` as its own git repo. Committed independently by `codeguide_commit.py` helper. Never touches the target repo.

`codeguide-setup --sibling [--from-url <git-url>]` creates the sibling repo on first use (`git init` locally, or clone from URL). Subsequent setups in subfolders `mkdir` + commit into the existing sibling repo.

### Resolve chain (codeguide, walked from cwd up to git-toplevel)

1. For each level between cwd and git-toplevel (inclusive):
   - Inline: does `<level>/_codeguide/Overview.md` exist?
2. If no inline match: is there a `.codeguide-root` file at git-toplevel? If yes, read the path inside it.
3. If no override file: compute `sibling_root = _sibling.resolve_path("codeguide", git_toplevel)`.
4. For each level (same sweep): does `<sibling_root>/<rel-path>/_codeguide/Overview.md` exist? (`<rel-path>` is the path from git-toplevel to `<level>`.)
5. First match wins. No match at any step → "run /codeguide-setup first".

### `.codeguide-root` override file

- Path: `<git-toplevel>/.codeguide-root`. Single line containing an absolute or relative path (relative to git-toplevel).
- Purpose: point at an existing codeguide directory in a non-conventional location (monorepo-branch worktree, shared drive, etc.).
- The plugin does NOT add this file to the target repo's `.gitignore`. The user is responsible for ignoring it (e.g., via `~/.gitignore_global`). "Zero-footprint" means we never modify the target repo — not even its gitignore.
- `CODEGUIDE_ROOT` env var is NOT supported. `.codeguide-root` is the single override mechanism.

### Multi-codeguide — sibling mirrors the subfolder structure

When subfolders of the repo each have their own codeguide:
- `<repo>/src/csharp/NORCE.Models/` runs setup → `<sibling>/src/csharp/NORCE.Models/_codeguide/`.
- `<repo>/src/csharp/NORCE.Drilling/` runs setup → `<sibling>/src/csharp/NORCE.Drilling/_codeguide/`.

The sibling repo only contains paths where codeguides actually exist; empty mirror directories are not created. A codeguide at the repo root, if the user sets one up there, lives at `<sibling>/_codeguide/`.

Multi-codeguide also implies **grouping by codeguide-root**: `codeguide-update` parses the staged diff, calls `resolve.py` per file to find that file's governing codeguide-root, groups files by root, updates each group independently. `resolve.py` finds roots (deterministic); the DocumentationGuide rules inside each root govern which specific `.md` doc files change (non-deterministic — CC decides based on the routing rules).

### Subfolder-init anchors on git-toplevel

All path computation uses `git rev-parse --show-toplevel`, not cwd. Running `/codeguide-setup --sibling` from `Models/src/csharp/NORCE.Models/` places the codeguide at `Models.codeguide/src/csharp/NORCE.Models/_codeguide/`, not at `src/csharp/NORCE.Models.codeguide/` or similar cwd-anchored guess.

### Commit discipline splits by mode

- **Inline:** `git-commit` skill stages `_codeguide/` files alongside source in the same target-repo commit. Current behaviour.
- **Sibling:** `codeguide-update` calls `${CLAUDE_PLUGIN_ROOT}/scripts/millpy/codeguide/codeguide_commit.py`. The helper does `git -C <sibling> add … && git -C <sibling> commit -m "…"` inside the sibling repo. `git-commit`'s step 2 still invokes `codeguide-update` but does not try to stage its output — the sibling commit is already done. Cadence stays per-commit.
- Recovery path when the user bypasses `@git-commit`: `codeguide-maintain` skill (already in the plugin) sweeps a commit range and fixes drift. Documentation pointer included in the spec, no new tooling required.

### Mill-v2 integration — shared helper, removed token defaults

- `mill-spawn.py` switches from reading `cfg["spawn"]["worktrees_dir"]` as a token template to calling `_sibling.resolve_path("worktrees", repo_root)` when the key is absent. Explicit `spawn.worktrees_dir` set in `.millhouse/config.local.yaml` continues to override.
- `mill-setup` is a **skill** (`plugins/mill/skills/mill-setup/SKILL.md`), not a Python script. Its SKILL.md prose currently contains two internally-inconsistent defaults: Phase 3 clones the wiki at literal `<container>/wiki/` (hub-form), while Phase 3.5 declares the `<WIKI_PATH>` token default as `<CONTAINER_PATH>/<REPO>.wiki/` (prefix-form). The plan reconciles both to `_sibling.resolve_path("wiki", repo_root)` by updating the skill's prose to invoke `python ${CLAUDE_PLUGIN_ROOT}/scripts/_sibling.py wiki <hub-path>` as a subprocess call and using the printed result for both Phase 3 and Phase 3.5. Explicit `wiki_path:` in `.millhouse/config.local.yaml` continues to override.
- `wiki/config.yaml` drops the `spawn.worktrees_dir` default and the `<WIKI_PATH>` documented default from its header comments. Override-only keys remain documented.
- Integration test fixtures (`test-spawn.py`, `test-merge.py`) update to the new layout: test hub is at `<container>/hub/` → worktrees at `<container>/worktrees/` (not `<container>/hub.worktrees/`).

### Pre-existing bug in codeguide plugin — fix before the sibling work

The codeguide skills (`codeguide-setup`, `codeguide-update`, `codeguide-generate`, `codeguide-maintain`) all reference `${CLAUDE_PLUGIN_ROOT}/scripts/millpy/codeguide/resolve.py` — a stale path from the v1 `millpy`-package layout. The file actually lives at `${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py`. Any invocation of those skills on a real install would fail at the first `python` call.

This spec fixes all four SKILL.md files to reference the correct flat path BEFORE touching the resolver code. Scope creep is acceptable because the sibling-mode work compounds the issue (adding `codeguide_commit.py` at the stale path). Fix the path first, then extend.

### Monorepo-branch pattern — user-managed, not a plugin mode

Users who want "one GitHub repo with many codeguides as branches, worktree-checkout per active one" set up the clone + branch-worktree themselves and point `.codeguide-root` at the chosen worktree directory. The plugin does not orchestrate this. Keeps plugin scope small; the pattern is a user-level choice.

### Never assume the millhouse source repo is cloned

All plugin scripts reference `${CLAUDE_PLUGIN_ROOT}` for their own files. A session running on a third-party repo with codeguide and mill plugins installed must work with nothing on disk but the plugin install + the target repo + the sibling repo (when in sibling mode). Rule enshrined in `CLAUDE.md` in this same spec's commit.

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

## Open design points (resolved during grilling)

Kept for audit trail.

- **Mode cache under `.git/info/`** — rejected. No cache; `resolve.py` walks fresh every call. Walk cost is microseconds; LLM calls dominate.
- **Multi-codeguide per staged commit** — confirmed: `resolve.py` finds cg-ROOT per file (deterministic), `codeguide-update` groups files by root and updates each root independently.
- **Sibling refresh semantics** — same as root refresh: overwrite plugin-owned files, preserve user-owned. Just applied at the sibling-mirror anchor.
- **`.gitignore` safety-net in target repo** — rejected. Zero-footprint in target repo means we NEVER modify it, not even gitignore. User handles their own gitignore via `~/.gitignore_global` if needed.
- **`CODEGUIDE_ROOT` env var** — rejected. `.codeguide-root` file at git-toplevel is the single override mechanism.
- **`root.txt` workspaces in sibling mode** — same pattern as inline, just living at mirrored paths inside the sibling repo. No re-design.
- **Lint scope** — `git-commit` step 1 lints source in the target repo only. Sibling is docs; markdown-skill conventions apply at EDIT time (inside `codeguide-update`), not at commit-lint time.
- **Spec 13 reference** — one-line edit included in this implementation's final batch.

## Out of scope vs. current codeguide plugin

- No GUI / interactive branch-picker when `--from-url` points at a monorepo with many branches. User passes `<url>#<branch>` or separate `--branch` flag; implementation detail.
- No automatic migration from inline → sibling. A user who decides to switch after the fact moves files manually and re-runs setup with `--sibling`.
- No CC-driven auto-seed of the hub (Millhouse) repo's own codeguide. That is spec `13-mill-codeguide.md` and remains deferred until mill-v2 self-sufficiency.
- Wiki stays config-override-able via `.millhouse/config.local.yaml` → `wiki_path:` — overriding the new `_sibling` default when present.

## References

- `plugins/codeguide/skills/codeguide-setup/SKILL.md` — current setup modes (first-time root, root refresh, subfolder refresh, new subfolder activation).
- `plugins/codeguide/skills/codeguide-update/SKILL.md` — current update flow that stages into the current repo.
- `plugins/mill/skills/git-commit/SKILL.md` step 2 — current "Codeguide sync" invocation of `@codeguide:codeguide-update`.
- Discussion thread in which this spec was grilled — key insights: monorepo-with-branches is acceptable for personal use (user manages plumbing), sibling is the right primitive, subfolder-init must anchor on git-toplevel, multiple independent subfolder codeguides must be supported, setup automates git-init/clone.
