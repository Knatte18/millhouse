# Discussion: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split

```yaml
task: '11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split'
slug: container-restructure
status: discussing
parent: main
```

## Problem

The current millhouse container layout has accumulated structural issues that block several follow-on improvements:

1. **Asymmetric layout.** Main worktree (`hub/`) sits at one level, task worktrees at another (`worktrees/<slug>/`). Hub is technically also a git worktree but is treated specially because plugins/scripts/CLAUDE.md live there.
2. **Wiki bloat.** All task working state lives in the wiki (`wiki/active/<slug>/{status.md, reviews/, plan/, discussion.md}`), generating ~40 commits per task and forcing history-rewrite gymnastics for cleanup.
3. **No clean cross-worktree visibility once state moves out of wiki.** Today it works because everything is in wiki; if state moves to task branches we need a different mechanism that doesn't require fetch/checkout-dance.
4. **Brittle hub-form detection.** `_sibling.resolve_path` checks `repo_root.name == "hub"` (literal); renaming `hub/` for any reason breaks every script.
5. **Hub-as-subfolder broken.** Downstream consumer (NORCE-DrillingAndWells/Models) installs mill plugins in a subfolder of an existing repo; mill scripts assume hub == git toplevel and place state at the wrong location (folded #53).
6. **gitignore in the wrong file.** mill-managed block writes anchored entries (`/.active`, `/tasks.md`) at the toplevel even when the actual files live in a subfolder, silently doing nothing (folded #54).
7. **mill-spawn skips hardlinks.** New worktrees lack `tasks.md` because `mill-spawn.py:197` reads `read_junctions` but not `read_hardlinks`. Hub's own `tasks.md` is also no longer a hardlink (filter-repo + idempotency-skip artefact).

This task delivers a coherent container layout where every worktree is treated symmetrically, working state lives on the task branch (recoverable via git history), the wiki shrinks to just the index, and every mill script respects cwd-as-hub.

**Why now:** wiki bloat is observable per task; downstream consumer hit several cwd-vs-toplevel symptoms; subsequent tasks (migrate-to-uv #18, mill-autofix-bugs #16) want to land on a stable layout, not chase moving paths.

## Scope

**In:**

- New container layout. `<container>/wts/<repo>/` (main worktree), `<container>/wts/<slug>/` (task worktrees), `<container>/portals/`, `<container>/wiki/`, `<container>/codeguide/`.
- New hub-form detection. `_sibling.resolve_path` switches from `repo_root.name == "hub"` to `repo_root.parent.name == "wts"`. Identical-twin update propagated to `plugins/codeguide/scripts/_sibling.py`.
- Per-worktree `.others` junction. Target: `<container>/portals/`. `.active` junction retargeted to `<container>/portals/<SLUG>/`.
- Working state moves out of wiki. `status.md`, `discussion.md`, `plan/`, `reviews/` live at the root of the task worktree on the task branch.
- mill-merge teardown rewrite. Cleanup commit → squash-merge → archive tag → worktree remove → branch delete → portal remove.
- gitignore split. New helper `_gitignore.upsert_split(repo_root_gitignore, hub_gitignore, glob_entries, anchored_entries)`.
- cwd-as-hub everywhere. New helper `_paths.resolve_hub_relative_path(worktree_root, hub_subpath)` populated from `.millhouse/config.local.yaml` `hub_relative_path:`. Every script that touches per-worktree state uses it.
- mill-spawn writes hardlinks. New worktrees get `tasks.md` (and any other `wiki/config.yaml` `hardlinks:` entry).
- Cross-worktree consumers updated. `mill-status`, `mill-list`, `mill-terminal`, `mill-vscode`, `mill-cleanup`, `mill-resume`, `mill-self-report`, `mill-inspect`, `mill-merge`, `mill-merge-in` read state from worktrees, not wiki.
- Junctions semantic unified. All entries in `wiki/config.yaml` `junctions:` are created in every worktree (main + tasks). `<SLUG>` parameterizes target, not scope.
- One-shot migration tool. `plugins/mill/scripts/millpy-migrate-layout.py` performs `hub/` → `wts/<repo>/`, `worktrees/` → `wts/`, populates `portals/`. `--dry-run` flag.
- Worktree-relative review templates. `wiki/config.yaml` `paths.discussion_file: discussion.md`, `paths.plan_dir: plan/`, `paths.reviews_dir: reviews/`. New helper `_paths.resolve_active_worktree(container_path, slug)`.
- Documentation. `CLAUDE.md` updated for the new layout; mill-setup SKILL.md verify-phase updated; mill-merge SKILL.md teardown sequence updated.

**Out:**

- `mill-spawn --inplace` flag (separate task; `mill-claim` already covers in-place flow).
- Cross-machine workflow / `mill-checkpoint` push command (separate task).
- mill-add slug-vs-repo-name collision validation (small follow-up; not gating).
- New review-flow features (covered by tasks 9/10).
- Codeguide-seed run (task 4).

## Decisions

### hub-form-detection

- **Decision:** `_sibling.resolve_path(role, repo_root)` checks `repo_root.parent.name == "wts"` to decide container-form vs prefix-form. Container-form returns `parent.parent / role` because the main worktree now sits one level deeper than in the old hub-form. Full body:

  ```python
  def resolve_path(role: str, repo_root: Path) -> Path:
      parent = repo_root.parent
      if parent.name == "wts":
          # Container-form: main worktree is <container>/wts/<repo-name>;
          # siblings live next to wts/, not next to <repo-name>.
          return parent.parent / role
      # Prefix-form: <container>/<repo-name>; siblings carry repo-name prefix.
      return parent / f"{repo_root.name}.{role}"
  ```

  Verification:
  - `resolve_path("wiki", <container>/wts/millhouse)` → `<container>/wiki/` ✓
  - `resolve_path("wts",  <container>/wts/millhouse)` → `<container>/wts/`  ✓ (`parent.parent / "wts"` = `<container>/wts/`)
  - `resolve_path("codeguide", <container>/wts/millhouse)` → `<container>/codeguide/` ✓
- **Rationale:** New layout puts every worktree (main + task) under `<container>/wts/`. The parent directory becomes the structural invariant; the worktree name itself is now variable (`millhouse/`, `bug-X/`). Pure function, no git subprocess.
- **Old hub-form (`<container>/hub/`) is intentionally no longer recognised.** A repo with `hub/` falls through to prefix-form (`hub.wiki/`, `hub.worktrees/` etc.). The migration script renames `hub/` → `wts/<repo>/`, so old hub-form ceases to exist after migration. Repos that have not migrated lose hub-form recognition — by design, since they are now in an unsupported intermediate state and the migration script is mandatory.
- **Rejected:** `repo_root.name == remote_repo_name` (requires git subprocess; breaks for repos without a remote); explicit `layout: container` config key (yet another setup decision; opt-in surprises); preserving old hub-form alongside container-form (forks the function and creates an ambiguous `<container>/hub/wts/<x>` case).

### state-files-location

- **Decision:** Working state lives at the **worktree root** on the task branch: `<wts>/<slug>/status.md`, `<wts>/<slug>/discussion.md`, `<wts>/<slug>/plan/`, `<wts>/<slug>/reviews/`.
- **Rationale:** Visible in the IDE sidebar without extra navigation; tracked by git on the task branch (so `.millhouse/` is unsuitable — it's gitignored by design); cleanup-commit `git rm -r reviews/ discussion.md plan/ status.md` is a one-line operation.
- **Rejected:** A dedicated `task-state/` subdir (extra path level for no real benefit); under `.millhouse/` (gitignored, can't be tracked).

### task-branch-teardown

- **Decision:** mill-merge finalize sequence:
  1. On the task branch: `git rm -r reviews/ discussion.md plan/ status.md`, then `git commit -m "chore: pre-merge cleanup"`.
  2. Switch to parent branch and `git merge --squash <task-branch>`; squash commit message authored as today.
  3. `git tag archive/<slug> <task-branch>` (tag the cleanup-commit tip).
  4. `git worktree remove <container>/wts/<slug>`.
  5. `git branch -D <task-branch>`.
  6. Remove portal junction `<container>/portals/<slug>`.
  7. Remove legacy `<wiki>/active/<slug>/` directory if it exists.
- **Rationale:** Cleanup commit is reviewable in `git log`; archive tag is cheap and persistent; worktree + branch + portal removal are independent steps that all need to happen for a clean teardown.
- **Rejected:** Path-filtered squash (couples cleanup logic to merge step); hard delete without tag (loses history we just spent effort preserving).

### portals-and-others-junctions

- **Decision:**
  - `<container>/portals/<slug>` is a directory junction → `<container>/wts/<slug>`. Created by mill-spawn (per task) and mill-setup (for the main worktree). Removed by mill-cleanup / mill-merge.
  - `<worktree>/.others` is a directory junction → `<container>/portals/`. Created in every worktree (main + tasks) so every worktree gets cross-worktree visibility via `.others/<slug>/...`.
  - `<worktree>/.active` retargeted: junction template becomes `<CONTAINER_PATH>/portals/<SLUG>/`.
- **Rationale:** Single portal entry point per worktree gives cross-worktree visibility without per-pair junctions. `.active` keeps its user-facing semantic ("this task's working dir") even though the dir now lives in the worktree, not the wiki.
- **Rejected:** Self-referential `.active → worktree_root` (awkward); drop `.active` entirely (breaks muscle-memory and SKILL.md prose patterns).

### junctions-block-semantic

- **Decision:** All entries in `wiki/config.yaml` `junctions:` are created in every worktree (main + tasks). `<SLUG>` parameterizes the target, not the scope. mill-spawn iterates the full block; mill-setup does the same for the main worktree. Implementation: a shared helper `_setup.create_hub_links(target_root, wiki_path, tokens)` used by both mill-setup phase 4.5 and mill-spawn.
- **Token-scope contract:** `create_hub_links` silently SKIPS any entry whose target template references a token not present in the supplied `tokens` dict. mill-setup passes a token map WITHOUT `<SLUG>` → entries containing `<SLUG>` (`.active`) are skipped for the main worktree. mill-spawn passes a slug-bearing token map → all entries are created. This treats `<SLUG>` as a scope filter: entries needing a slug only exist in worktrees that have one. The main worktree never holds an active task, so `.active` there would be meaningless. Implementation note: `create_hub_links` scans the target template for `<TOKEN>` references with a regex, intersects with the supplied dict, and skips an entry if any required token is absent. `_junction.resolve_target`'s strict `ValueError` behaviour stays unchanged — the filtering happens BEFORE the call. Same scope-filter rule applies symmetrically to hardlinks.
- **Rationale:** Unifies main-vs-worktree junction handling. Today's split — mill-setup handles non-`<SLUG>` and mill-spawn handles `<SLUG>`-only — is the bug behind ".others would only exist in worktrees" and "mill-spawn skips hardlinks". One creator, all junctions, all hardlinks, every worktree.
- **Rejected:** Separate `worktree_junctions:` block (config bloat, dual source of truth); sentinel placeholder slug for main worktree (would create a junction at `<container>/portals/__main__/` which doesn't exist).

### gitignore-split

- **Decision:** New helper `_gitignore.upsert_split(repo_root_gitignore, hub_gitignore, glob_entries, anchored_entries)`. When the two paths are equal, it writes a single combined marker block. When different, it writes two marker blocks (one per file).
  - **`GLOB_ENTRIES`** (always at repo root): `**/.millhouse/`, `**/.scratch/`, `**/wts/`, `**/portals/`.
  - **`ANCHORED_ENTRIES`** (at hub): `/.active`, `/.others`, plus every entry from `wiki/config.yaml` `hardlinks:` (e.g. `/tasks.md`).
- **Rationale:** Anchored entries only ignore files at the same level as the gitignore. When hub is a subfolder, root-anchored entries in the toplevel gitignore silently do nothing (folded #54). Split puts each entry where it can take effect.
- **Rejected:** Single-call `upsert(path, all_entries)` (the original bug); per-call `upsert(path, ...)` with target-dir parameter (no protection against double-writing the same file when hub == repo root).

### cwd-as-hub-everywhere

- **Decision:**
  - mill-setup writes `hub_relative_path: <subpath>` (or `.` for typical case where hub == repo root) into `.millhouse/config.local.yaml` at setup time. `<subpath>` is computed from `cwd.relative_to(git_toplevel)`.
  - New helper `_paths.resolve_hub_relative_path(worktree_root: Path, hub_subpath: str) -> Path` returns `worktree_root / hub_subpath` (or just `worktree_root` for `.`).
  - Every script that places per-worktree state — `mill-spawn`, `mill-claim`, `mill-cleanup`, `mill-merge`, `mill-merge-in`, `mill-status`, `mill-list`, `mill-inspect`, `mill-vscode`, `mill-terminal` — routes through this helper instead of using `git rev-parse --show-toplevel` directly.
- **Rationale:** Single source of truth for "where is the hub inside this worktree". Setup-time decision (written to config) is more stable than runtime cwd inference (which depends on slash-command invocation context).
- **Rejected:** Runtime cwd-derivation (cwd at slash-command invocation isn't always the hub).

### review-template-paths

- **Decision:** `wiki/config.yaml` `paths:` block becomes worktree-relative:
  ```yaml
  paths:
    discussion_file: discussion.md
    plan_dir:        plan/
    reviews_dir:     reviews/
  ```
  No `<SLUG>` substitution in templates. New helper `_paths.resolve_active_worktree(container_path: Path, slug: str) -> Path` scans `<container>/wts/<slug>/` (verifies `.millhouse/active.slug.md` matches the slug). `_review_common.resolve_path(slug, key)` returns `<active_worktree>/<template>`. The function derives `container_path` internally via `_paths.resolve_main_worktree_root(Path.cwd()).parent` — same entry point shape that the three review CLI scripts (`millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py`) already use today (`project_root = Path.cwd()` at `millpy-review-discussion.py:27`). Callers pass slug + key only; no new explicit parameters at the CLI boundary.
- **Rationale:** Slug picks the worktree, not a path within it. Removes redundant `<SLUG>` token from the templates.
- **Rejected:** Keep `<SLUG>` in templates (redundant); pass worktree root as explicit parameter to every review-script invocation (verbose; doesn't compose with SKILL.md prose).

### worktrees-dir-default-role

- **Decision:** `_paths.resolve_worktrees_dir` fallback expression becomes `main_root.parent` (direct), replacing the previous `_sibling.resolve_path("worktrees", main_root)`. Both the role-string and the helper-call go away — in container-form `wts/` IS the parent directory, not a sibling reachable through `_sibling`. Existing users with `spawn.worktrees_dir:` config overrides keep their override unchanged.
- **Rationale:** Direct expression matches the structural invariant ("main worktree's parent is the worktrees container") that the new hub-form rule relies on. `_sibling.resolve_path("wts", main_root)` would technically return the right path under the corrected `_sibling` body (`parent.parent / "wts"` = `main_root.parent`), but the indirection obscures intent — `wts/` is not conceptually a peer of `<repo>/`, it's the container.
- **Rejected:** `_sibling.resolve_path("wts", main_root)` (works arithmetically but reads as if `wts/` were a sibling, which it isn't).

### codeguide-sibling-twin

- **Decision:** `plugins/codeguide/scripts/_sibling.py` is updated to byte-match the new mill `_sibling.py` in the same task.
- **Rationale:** The identical-twin rule is documented in both files. Skipping the codeguide update breaks the invariant immediately and silently.

### codeguide-clone-location

- **Decision:** `<container>/codeguide/` stays in place — sibling of `wts/`, not under it.
- **Rationale:** Codeguide has its own repo lifecycle and is not a mill-managed worktree of the project. Same-level as `wiki/`.

### migration-strategy

- **Decision:** Standalone `plugins/mill/scripts/millpy-migrate-layout.py`, invoked manually once per existing clone. Halts if any task is in flight (any `wiki/active/<slug>/` with `phase` not in `{done, abandoned}`). Migration steps:
  1. `mkdir <container>/wts`.
  2. For each existing worktree under `<container>/worktrees/<slug>`: `git worktree move <old> <container>/wts/<slug>` (run from hub).
  3. Move main worktree: plain `mv <container>/hub <container>/wts/<repo>` (where `<repo>` is the repo name from origin URL); then `cd <container>/wts/<repo> && git worktree repair` to fix child `.git` references.
  4. Remove now-empty `<container>/worktrees/`.
  5. `mkdir <container>/portals`. For each `wts/<slug>` (including the main `wts/<repo>`): create `<container>/portals/<slug>` junction → `<container>/wts/<slug>`.
  6. Re-run `mill-setup` from inside `<container>/wts/<repo>` to refresh junctions/hardlinks/gitignore for the new layout (idempotency carries the rest).
  Migration script supports `--dry-run` (prints planned operations without executing).
- **Rationale:** One-shot, easy to read, easy to verify. mill-setup auto-migration is too much surface area for an idempotent setup tool.
- **Rejected:** mill-setup auto-detect-and-migrate (bloats setup with one-shot logic); halt+manual instructions only (too easy to corrupt git refs).
- **Operator constraint:** `mill-setup` MUST NOT be run standalone between deploying the new mill code and completing `millpy-migrate-layout.py`. The new `_gitignore.py` writes `**/wts/` (replacing `**/worktrees/`); a setup run on the still-existing old layout therefore leaves `worktrees/` un-gitignored. Step 6 of the migration is the correct place for the post-migration mill-setup invocation. Migration-script entry banner reminds the operator of this constraint.

### in-flight-tasks-during-migration

- **Decision:** Migration halts if any in-flight task exists. User must merge or abandon all tasks (including this one) before running `millpy-migrate-layout.py`.
- **Rationale:** Single-developer workflow today, one task in flight (this one). Cleanest cutover. Avoids per-branch git operations to relocate state mid-flight.

### inplace-spawn-scope

- **Decision:** `mill-spawn --inplace` is **out of scope**. mill-claim already supports the in-place flow.
- **Rationale:** Orthogonal to layout; multiple unresolved sub-questions (uncommitted-changes handling, mill-merge teardown without a worktree). Filed as a separate task if the need recurs.

## Technical context

### Modules touched

| Module | What changes |
|---|---|
| `plugins/mill/scripts/_sibling.py` | New rule: `repo_root.parent.name == "wts"` (replaces `name == "hub"`). |
| `plugins/codeguide/scripts/_sibling.py` | Byte-for-byte twin update of mill's. |
| `plugins/mill/scripts/_paths.py` | Default `_sibling` role for `resolve_worktrees_dir` becomes `"wts"`. New `resolve_hub_relative_path(worktree_root, hub_subpath)`. New `resolve_active_worktree(container_path, slug)`. |
| `plugins/mill/scripts/_gitignore.py` | New `upsert_split` function. `STANDARD_ENTRIES` split into `GLOB_ENTRIES` + `ANCHORED_ENTRIES`. |
| `plugins/mill/scripts/_junction.py` | Unchanged (`<CONTAINER_PATH>` and `<SLUG>` token resolution already there). |
| `plugins/mill/scripts/_wiki.py` | Unchanged (`read_junctions` and `read_hardlinks` already exist; mill-spawn callsite changes). |
| `plugins/mill/scripts/_setup.py` (new) | Shared `create_hub_links(target_root, wiki_path, tokens)` used by mill-setup phase 4.5 and mill-spawn. Iterates both `read_junctions` and `read_hardlinks`. |
| `plugins/mill/scripts/_spawn_core.py` | `write_initial_status` writes to worktree root, not wiki. `recreate_active_junction(slug, mill_dir, container_path)` retargets `.active` from `wiki_path/active/slug` to `<container_path>/portals/<slug>/`; signature drops the `wiki_path` parameter. Uses the same template-substitution path as mill-spawn so both code paths stay symmetric. |
| `plugins/mill/scripts/millpy-spawn.py` | Junction loop unified (every entry created, `<SLUG>` parameterizes target). Hardlinks created. Status path → worktree root. Portal entry created. `.others` junction created. cwd-as-hub. |
| `plugins/mill/scripts/millpy-claim.py` | Idempotent portal entry creation `<container>/portals/<slug>` → current worktree (mirrors mill-spawn step). Skip if junction is already correct, recreate if it points elsewhere. Update `recreate_active_junction` callsite for the new signature. cwd-as-hub for `.millhouse/` placement. |
| `plugins/mill/scripts/millpy-cleanup.py` | Remove portal entry. cwd-as-hub for `.millhouse/` placement. Read state from worktree, not wiki. |
| `plugins/mill/scripts/millpy-status.py`, `millpy-list.py`, `millpy-terminal.py`, `millpy-vscode.py`, `millpy-inspect.py` | Discover via `<container>/wts/*/.millhouse/active.slug.md`. Read state from `wts/<slug>/status.md`. cwd-as-hub for opening VS Code / shell at the cwd-equivalent path. |
| `plugins/mill/scripts/_review_common.py` | Base path resolution: `<active_worktree>/<template>` instead of `<wiki>/<template>`. |
| `plugins/mill/scripts/millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py` | Output dir resolution updated through `_review_common`. |
| `plugins/mill/scripts/millpy-migrate-layout.py` (new) | One-shot migration script with `--dry-run`. |
| `plugins/mill/skills/mill-setup/SKILL.md` | Phase 4.5 unified through `_setup.create_hub_links`. New phase: create `<container>/portals/` + main-worktree portal entry. Verify phase covers `wts/`, `portals/`, `.others`. Writes `hub_relative_path` into `.millhouse/config.local.yaml`. |
| `plugins/mill/skills/mill-merge/SKILL.md` | Cleanup commit → squash-merge → archive tag → worktree remove → branch delete → portal remove sequence. |
| `plugins/mill/skills/mill-spawn/SKILL.md` | (Generated from script; regenerate with mill-skills-from-scripts.) |
| `plugins/mill/skills/mill-resume/SKILL.md`, `mill-self-report/SKILL.md` | Read state from worktree, not wiki. |
| `wiki/config.yaml` | `junctions:` block updated (`.others` entry, `.active` retargeted, `.millhouse/wiki` unchanged). `paths:` block becomes worktree-relative (no `<SLUG>` token). Header comment updated. |
| `CLAUDE.md` | New layout diagram; path invariants section updated; `## Path invariants` notes new `_paths` helpers. |
| `plugins/mill/templates/config.local.yaml` | Add `hub_relative_path: .` default (commented example). |
| `plugins/mill/unit_tests/*` | See Testing section. |

### Cross-machine implications

Cross-machine state visibility is intentionally lost. Previously, every state transition was committed to the wiki, so any clone could see it via `git pull`. After this lands, state lives on the task branch in the hub. To inspect another machine's worktree state, the user runs `git fetch && git checkout <branch>` (or `git log <branch>`) on the hub. This is acceptable for the single-developer workflow today; cross-machine `mill-checkpoint` is a separate follow-up task (proposal already references this).

### Junctions vs symlinks

`_junction.py` already abstracts Windows directory junctions (`mklink /J`) vs POSIX symlinks (`os.symlink`). No platform changes needed. New `.others` and `portals/<slug>` entries use the existing API. Windows hardlinks require source and target on the same volume — already enforced by mill-setup phase 4.5 with a clear error message; same applies to mill-spawn after the unification.

### Helper reuse

- `_wiki.read_junctions(wiki_path)` and `_wiki.read_hardlinks(wiki_path)` already exist and are used by mill-setup phase 4.5; mill-spawn currently uses only the former. Factoring into shared `_setup.create_hub_links` eliminates the missing-hardlink bug and prevents future drift between the two callers.
- `_active.read_slug(mill_dir)` and `_active.write(...)` are unchanged; the marker file location (`.millhouse/active.slug.md`) doesn't move.
- `_junction.resolve_target` already substitutes `<CONTAINER_PATH>`, `<SLUG>` — no token additions needed.

### git-worktree mechanics for migration

- `git worktree move <old> <new>` — supported for child worktrees, atomic, updates references in `.git/worktrees/<slug>/gitdir`.
- Main worktree move is **not** supported by `git worktree move`. Use plain `mv hub wts/<repo>` then run `git worktree repair` from inside the moved main worktree to fix child `.git` file references; `repair` updates absolute paths in `.git/worktrees/<slug>/gitdir` files automatically.
- After migration, junction recreation runs through normal mill-setup; old `.millhouse/wiki` and `.active` junctions are stale and must be removed before recreation. mill-setup's idempotency already handles this (`_junction.create` raises if a target exists; the migration script removes pre-existing junctions before re-running setup).

### Tokens

Existing tokens cover everything: `<HUB_PATH>`, `<CWD_PATH>`, `<CONTAINER_PATH>`, `<WIKI_PATH>`, `<REPO>`, `<SLUG>`. No new token needed for portals — `<CONTAINER_PATH>/portals/` reads fine and avoids token proliferation.

### `wiki/config.yaml` changes (final shape)

```yaml
junctions:
  .millhouse/wiki: <WIKI_PATH>
  .others: <CONTAINER_PATH>/portals/
  .active: <CONTAINER_PATH>/portals/<SLUG>/

hardlinks:
  tasks.md: <WIKI_PATH>/Home.md

paths:
  discussion_file: discussion.md
  plan_dir:        plan/
  reviews_dir:     reviews/
```

(Other top-level keys — `repo:`, `spawn:`, `llm:`, `implementers:`, `pipeline:`, `review:`, `notify:`, `groom:` — unchanged.)

## Constraints

- **Plugin scripts reference `${CLAUDE_PLUGIN_ROOT}`, never source repo paths.** All new code preserves this invariant.
- **Junctions are IDE/terminal convenience only.** Scripts always resolve to the real path through `_paths.*`. The new `.active`/`.others` entries follow this rule (resolution goes via `_paths.resolve_active_worktree`, never via the junction).
- **Identical-twin rule for `_sibling.py`.** Both copies updated in the same task.
- **All path resolution goes through `_paths.py`.** New helpers `resolve_hub_relative_path` and `resolve_active_worktree` live there, not scattered across `millpy-*.py`.
- **Scratch lives at `<cwd>/.scratch/`.** Migration script writes any debug/log artifacts to `.scratch/migrate-<timestamp>.log`, not `/tmp` or `$env:TEMP`.
- **mill-managed `.gitignore` block is regenerated by mill-setup.** Outside-marker content untouched. Both blocks (repo-root and hub-cwd) carry the same START/END markers.
- **YAML quoting in writers.** Per project convention (see `_yaml_writer.quote_scalar`), all status/active/marker writes use the helper — no raw f-string yaml.
- **Generated markdown uses fenced ```yaml metadata blocks**, not `---` frontmatter.

## Testing

### TDD candidates (write tests first)

- **`_sibling.resolve_path` new rule** — extend `plugins/mill/unit_tests/test-sibling.py`. Cases: `parent.name == "wts"` → bare names; `parent.name != "wts"` → prefixed names; old `name == "hub"` no longer triggers special-case; codeguide twin equivalence verified by file-byte-compare assertion.
- **`_gitignore.upsert_split`** — extend `test-gitignore-phase.py`. Cases: same path → single combined marker block; different paths → two marker blocks; idempotent re-run on either path; hardlink list expansion (anchored entries normalised with leading `/`); corrupt-marker error preserved.
- **`_paths.resolve_hub_relative_path(worktree_root, hub_subpath)`** — extend `test-paths.py`. Cases: `hub_subpath == "."` → returns `worktree_root` unchanged; `hub_subpath == "src/csharp/X"` → returns `worktree_root / "src" / "csharp" / "X"`; absolute `hub_subpath` rejected with clear error; trailing-slash normalised.
- **`_paths.resolve_active_worktree(container_path, slug)`** — extend `test-paths.py`. Cases: worktree exists at `<container>/wts/<slug>` with matching `.millhouse/active.slug.md` → returns it; missing dir → raises a typed error; mismatched slug in marker → raises; multiple matches not possible (filesystem invariant) but the test stub creates a fixture confirming single-match.

### Implement-then-test (integration fixtures)

- **`mill-spawn` end-to-end** — extend `test-millpy-spawn.py`. Verify after spawn: `status.md` written to worktree root (not wiki); portal entry created at `<container>/portals/<slug>`; `.others` junction created; `tasks.md` hardlink created (inode match); junctions block iterated for every entry (slug-or-not).
- **`mill-merge` teardown** — new `test-mill-merge-teardown.py` (or extend existing test-mill-merge-inplace). Verify: cleanup commit appended to task branch with the four `git rm` paths; squash-merge runs cleanly; archive tag created at task-branch tip; worktree removed; branch deleted; portal entry removed; legacy wiki/active dir removed if present.
- **Cross-worktree consumers** — extend `test-millpy-status.py`, `test-millpy-cleanup.py`, `test-millpy-terminal.py`, `test-millpy-vscode.py`, plus `test-millpy-list.py`, `test-millpy-spawn.py`. Discovery now via `<container>/wts/*/.millhouse/active.slug.md`. Status reads from `wts/<slug>/status.md` (worktree-tracked file).
- **Junction-block-semantic** — extend `test-millpy-spawn.py`. Verify all entries from `wiki/config.yaml` `junctions:` are created in every worktree, regardless of `<SLUG>` presence.
- **`_setup.create_hub_links`** — new `test-setup-hub-links.py`. Same fixture used by mill-setup-phase test (existing) and mill-spawn test (new) — verifies one helper, two callers.

### Manual verification

- **`millpy-migrate-layout.py`** — manual test on a copy of the millhouse repo under `.scratch/` first. `--dry-run` prints planned operations; live run executes them. Halt-on-in-flight verified manually with a fixture in-flight task. Live run on the actual millhouse repo only after `--dry-run` looks correct.
- **End-to-end smoke after migration** — run `mill-spawn` on a throwaway slug; verify the new worktree appears under `<container>/wts/`; `status.md` is at root; portal entry exists; `.others` junction exists; `tasks.md` hardlink exists; review-script output lands at `<wts>/<slug>/reviews/...`.
- **Codeguide twin** — manual `diff plugins/mill/scripts/_sibling.py plugins/codeguide/scripts/_sibling.py` should print only docstring differences.

### Out of scope for tests

- Cross-machine workflow (no automation today; manual `git fetch && git checkout`).
- Codeguide twin diff verification in CI (could be added in a follow-up).
- Performance regression tests (this task removes per-task wiki commits; throughput change is qualitative).

## Q&A log

- **Q:** New hub-form rule? **A:** `repo_root.parent.name == "wts"` (Q1.A).
- **Q:** Where do state files live in the worktree? **A:** Root level (Q2.A).
- **Q:** `--inplace` flag in scope? **A:** Out of scope (Q3.A).
- **Q:** How does mill-merge clean up before squash? **A:** Cleanup commit on task branch, then squash (Q4.A).
- **Q:** What happens to the task branch after squash? **A:** Archive tag at tip, worktree removed, branch deleted, portal removed (Q5.A); user noted that branch deletion ≠ worktree removal — both must happen.
- **Q:** Where does `.active` point after the change? **A:** `<CONTAINER_PATH>/portals/<SLUG>/` (Q6.A).
- **Q:** gitignore split helper shape? **A:** `_gitignore.upsert_split(repo_root_gitignore, hub_gitignore, glob_entries, anchored_entries)` — single function, internally handles same/different paths (Q7.B).
- **Q:** gitignore entry split? **A:** `GLOB_ENTRIES = ["**/.millhouse/", "**/.scratch/", "**/wts/", "**/portals/"]`, `ANCHORED_ENTRIES = ["/.active", "/.others", *hardlink_names]` (Q8). `.others` is a per-worktree junction created in every worktree, hence anchored at the hub root, not glob-form.
- **Q:** Codeguide `_sibling.py` twin updated in same task? **A:** Yes (Q9).
- **Q:** Codeguide clone moves under `wts/`? **A:** No, stays at `<container>/codeguide/` (Q10).
- **Q:** Migration script approach? **A:** Standalone `millpy-migrate-layout.py`, manual one-shot, `--dry-run` flag (Q11.A).
- **Q:** In-flight tasks during migration? **A:** Halt; require merged/abandoned first (Q12.A).
- **Q:** Review templates after the change? **A:** Worktree-relative; new `_paths.resolve_active_worktree(slug)` helper (Q13.A).
- **Q:** `worktrees_dir` default role? **A:** Change `_paths.resolve_worktrees_dir` fallback role from `"worktrees"` to `"wts"` (Q14.A).
- **Q:** New `<PORTALS_PATH>` token? **A:** No; use `<CONTAINER_PATH>/portals/` (Q15).
- **Q:** How do scripts know "which subdir is the hub"? **A:** `hub_relative_path` written into `.millhouse/config.local.yaml` at mill-setup time; `_paths.resolve_hub_relative_path` reads it (Q16.A).
- **Q:** Which modules get TDD vs integration testing? **A:** TDD pure functions in `_sibling.py`, `_gitignore.py`, `_paths.py`; integration-test mill-spawn / mill-merge / cross-worktree consumers (Q17).
- **Q:** How does `.others` get created in every worktree, including the main one? **A:** All `junctions:` entries created in every worktree. `<SLUG>` parameterizes target, not scope. Shared helper `_setup.create_hub_links` used by both mill-setup and mill-spawn. Token-scope filter: entries referencing tokens absent from the supplied dict are silently skipped (Q18.A).
- **Q:** Does the Home.md task entry need re-titling during this task? **A:** No — entry stays as the current title; it gets flipped to `[done]` post-merge (Q19).
- **Q:** Anything missing? **A:** No additional concerns surfaced (Q20).
