# Discussion: script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo

```yaml
task: 'script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo'
slug: script-invocation-hygiene
status: discussing
parent: main
```

## Problem

Two related "wrong root" bugs leak through the mill plumbing. They are merged into a single task because the fix surface (`_paths.py`, `CLAUDE.md`, SKILL.md examples, `.gitignore`) overlaps and the diagnoses share a theme: *scripts and their invocation must know which root they belong to*.

**(A) cwd vs git-toplevel.** Eight call sites in six scripts construct paths to hub state (`.millhouse/`, `.vscode/`, `.scratch/`) by joining onto `git_root` (output of `git rev-parse --show-toplevel`). When mill is installed in a subdirectory of a larger repo (`<bigrepo>/src/Models/` is the hub, `<bigrepo>/` is the git root), `git_root != cwd` and the hub state ends up at the repo root instead of the actual hub. `mill-setup` already records `hub_relative_path:` in `.millhouse/config.local.yaml` for this case, and `mill-terminal` / `mill-vscode` already resolve correctly via `_paths.resolve_hub_relative_path`. The other entrypoints don't.

**(B) Source-repo vs plugin-cache.** Claude Code repeatedly invokes mill scripts as `python plugins/mill/scripts/...` (or even `uv run --project plugins/mill ...`) directly from the millhouse source tree. The repo *is the source code* of the plugin, not the plugin itself — the plugin lives at `~/.claude/plugins/cache/millhouse/<plugin>/<version>/` and gets refreshed on `update-plugins.ps1`. Concrete symptom: `plugins/mill/uv.lock` exists right now in the main worktree as untracked detritus (verified during exploration). Existing CLAUDE.md guidance about `${CLAUDE_PLUGIN_ROOT}` and `uv run` is correct in spirit but the rules-as-written are about `uv` vs `python` and "no hardcoded paths in plugin scripts" — neither of which directly bans `uv run --project plugins/mill ...` from a Bash command.

**Why now.** Both bugs are blockers for the next phase of work:

- Subfolder-install support is required by the downstream consumers that motivated `hub_relative_path:` in the first place. Half-done support (terminal/vscode work, claim/color/spawn/worktree don't) is worse than no support.
- The cache-vs-source confusion masks bugs in the cached plugin (changes to source don't take effect until `update-plugins.ps1` refreshes the cache; bugs that exist in the cached version are invisible during local development) and pollutes the source tree with `uv.lock` files that aren't valid artifacts in the source repo.

This is one of three Phase-1 critical-bug tasks per `Home.md`.

## Scope

**In:**

- **(A) Fix all 8 cwd-vs-git-root sites** in `millpy-claim.py`, `millpy-color.py`, `millpy-fetch-issues.py`, `millpy-spawn.py`, `millpy-worktree.py`, `_config.py`. Plus the `HUB_PATH` / `REPO` token mapping in `millpy-spawn._build_tokens`.
- **(A) Add `_paths.resolve_hub_path()` helper** as the single point of truth for "where is the hub from cwd". Implementation today returns `Path.cwd().resolve()`; documented assumption is "Claude Code's cwd is the hub when these scripts run". Future-proofs against changing that assumption (e.g. walk-up from cwd to find `.millhouse/`).
- **(A) Spawn / worktree dst handling for subfolder-install.** Read `hub_relative_path:` from the *source* `.millhouse/config.local.yaml`, then place the destination `.millhouse/`, `.vscode/`, hub junctions, and `_setup.create_hub_links` target_root at `worktree_path / hub_subpath / ...` so the new worktree mirrors the source layout. Portal junction target stays `worktree_path` (terminal/vscode adjust at launch).
- **(A) `_build_tokens` rebuilt for destination context.** When spawn calls `create_hub_links` for the *new* worktree, the tokens dict must reflect that worktree's hub: `HUB_PATH = worktree_path / hub_subpath`, `CWD_PATH = worktree_path / hub_subpath`. Build separate token dicts for source-side vs destination-side use, or rebuild before the second call.
- **(A) `_config.load_config` parameter rename.** Rename the third parameter from `git_root` to `worktree_root` (or `hub_dir`) to make intent explicit; update all call sites to pass `_paths.resolve_hub_path()` (current worktree) or the equivalent destination path.
- **(A) Unit tests** for `_config.load_config` with the renamed parameter; for `_paths.resolve_hub_path`; for `millpy-spawn`'s subfolder-install dst behavior (faked layout, assert `.millhouse/` lands at `worktree_path / hub_subpath / .millhouse`). Update existing `test-millpy-claim.py`, `test-millpy-color.py`, `test-millpy-spawn.py`, `test-millpy-worktree.py` for the new path semantics.
- **(B) CLAUDE.md tightening.** Add an explicit rule banning source-tree paths (`plugins/mill/...`, `plugins/codeguide/...`) in *operational* Bash commands. Tests are the only exception. Phrasing must distinguish "rule about uv vs python" from "rule about source vs cache". Include one wrong/right example pair.
- **(B) Wrong/right examples in `mill-add` and `mill-setup` SKILL.md.** Plus a one-shot verify pass over every other operational SKILL.md to confirm `${CLAUDE_PLUGIN_ROOT}` discipline and fix any stragglers (most are correct based on grep).
- **(B) `**/plugins/*/uv.lock` gitignore.** Add to repo-root `.gitignore` mill-managed block AND to `plugins/mill/templates/Home.md` template area / wherever external repos pick up gitignore conventions (verify whether `_gitignore.GLOB_ENTRIES` or `ANCHORED_ENTRIES` is the right home).
- **(B) Delete the stale `plugins/mill/uv.lock` in the main worktree** as part of the task's mill-merge cleanup so the main branch lands clean.

**Out:**

- **`.wiki` junction (post `rename-hub-junctions`).** That junction does not exist yet. The `rename-hub-junctions` Phase-4 task will introduce it; that task should adopt the cwd-as-hub principle from the start. We add a one-line note in CLAUDE.md `## Path invariants` so the future task picks up the convention.
- **`.millhouse/` shortcut wrappers (point 3 of proposal).** Already correct — `shortcut-wrapper.ps1` template forwards to cache via `uv run --project $latest`. The task `uv-wrapper-enforce` is the canonical home for any further wrapper hardening.
- **PreToolUse hook to block `plugins/mill/scripts/...` in operational Bash (point 5 of proposal).** Skipped per user direction — hooks are unreliable and add a maintenance surface. CLAUDE.md sharpening + gitignore + SKILL.md examples + `_codeguide` / lint guidance carry the load.
- **Lint script as a separate enforcement layer.** Same reasoning. Skip.
- **Refactoring `git_root` away from sites that legitimately need the git root** (e.g. `_paths.resolve_wiki_path(git_toplevel)` reads `git_toplevel / ".millhouse" / "config.local.yaml"` — that's also wrong in subfolder-install and IS in scope; but `git_root` for things like `_worktree.create(branch_name, worktree_path, cwd=git_root)` correctly identifies the source git checkout root and stays).
- **CC behavioral change**. The fix doesn't change the assumption "CC runs mill scripts from the hub directory". If CC navigates into a sub-subdirectory before invoking, behavior is undefined. Walk-up logic is left for a future iteration.

## Decisions

### Single helper over inline `Path.cwd()`

- **Decision:** Add `_paths.resolve_hub_path(cwd: Path | None = None) -> Path` returning `(cwd or Path.cwd()).resolve()`. Use it at all 8 sites and at every future "hub state path" construction.
- **Rationale:** Single point of truth. If the cwd-as-hub assumption is ever loosened (e.g. walk-up to find `.millhouse/`), one helper changes. Inline `Path.cwd()` would force a multi-file refactor when that day comes.
- **Rejected:** Inline `Path.cwd()` (minimal but doesn't centralize); pass `worktree_root` parameter through (just pushes the resolution to the caller, same total surface).

### Mirror `hub_subpath` in spawn / worktree dst

- **Decision:** Read `hub_relative_path:` from the source `.millhouse/config.local.yaml` at spawn time. Compute `dest_hub = worktree_path / hub_subpath`. Place `.millhouse/`, `.vscode/`, hub junctions, `create_hub_links` `target_root`, and `tokens["HUB_PATH"]` / `tokens["CWD_PATH"]` at `dest_hub`. Portal entry stays at `worktree_path`.
- **Rationale:** The new worktree is a fresh git checkout of the same repo, so its internal layout mirrors the source. Putting hub state at the wrong place inside the new worktree would break every script the next time it ran from the new worktree. Doing the proposal's literal swap (src=cwd, dst unchanged) ships a half-done fix that breaks the moment subfolder-install is exercised.
- **Rejected:** Proposal-literal swap (only fix src). Falsely advertises subfolder-install support.

### `_config.load_config` parameter rename, not signature change

- **Decision:** Rename the third parameter from `git_root` to `worktree_root`. Keep its position. Callers pass `_paths.resolve_hub_path()` (or the spawn destination's hub path, in mill-spawn's destination-side call).
- **Rationale:** Position-stable rename has zero ABI cost; the parameter name documents intent. Adding a new keyword would dilute the call sites. Keeping the old name (`git_root`) lying about its semantics defeats the purpose of the fix.
- **Rejected:** Keep parameter name (semantics drift); add a new function `load_config_at` (two functions doing the same job).

### Skip hooks; rely on prose + gitignore

- **Decision:** No PreToolUse hook. CLAUDE.md tightening, `.gitignore` update, SKILL.md wrong/right examples, and the `_codeguide`-maintained source carry the enforcement load.
- **Rationale:** User-stated lack of trust in hook reliability ("Jeg stoler ikke på hooks. De funker av og til. Stort sett ikke."). Adding an unreliable enforcement layer gives false confidence and adds a maintenance surface for the same problem CLAUDE.md already addresses.
- **Rejected:** PreToolUse hook (unreliable per user); ship-but-don't-install hook (worse — same maintenance, none of the enforcement); separate task to design the hook (still adds the maintenance surface eventually).

### Delete stale `plugins/mill/uv.lock` as part of merge cleanup

- **Decision:** Include `plugins/mill/uv.lock` deletion in the mill-merge cleanup commit. Verify no commit on the task branch ever added it.
- **Rationale:** A leaked artifact from prior accidents. Leaving it post-fix is aesthetically and technically incoherent — the gitignore rule will silence future accidents, but the existing leak should still be removed.
- **Rejected:** Leave it (rejected — incoherent); remove it pre-fix as a separate commit (rejected — bundles cleanly with the fix).

### Add CLAUDE.md note about `.wiki` for `rename-hub-junctions`

- **Decision:** Add a one-line note to CLAUDE.md `## Path invariants` stating "future `.wiki` junction (introduced by `rename-hub-junctions`) follows the same `cwd / ".wiki"` convention". Don't write code for `.wiki` now.
- **Rationale:** The future task lands the junction; this task lands the convention. Coupling them in code would force `rename-hub-junctions` to merge before this one or vice versa, defeating the parallel-safe phasing.
- **Rejected:** Touch `.wiki` paths now (file doesn't exist, can't test); leave nothing (the convention drifts back).

## Technical context

### Affected files

| File | Lines | Bug |
|---|---|---|
| `plugins/mill/scripts/millpy-claim.py` | 127, 168 | `git_root / ".vscode/settings.json"`, `git_root / ".millhouse"` |
| `plugins/mill/scripts/millpy-color.py` | 80, 94 | `git_root / ".vscode/settings.json"`, `git_root / ".millhouse"` |
| `plugins/mill/scripts/millpy-fetch-issues.py` | 62 | `git_root / ".scratch/issues.json"` |
| `plugins/mill/scripts/millpy-spawn.py` | 75, 79, 155, 190, 206, 214, 220 | tokens HUB_PATH/REPO, `_build_tokens` call, `src` for copy, `target_root`, `.vscode/` target, `.millhouse/` marker target |
| `plugins/mill/scripts/millpy-worktree.py` | 94 (and the analogous block — verify) | `src` for copy, plus the destination targets analogous to spawn |
| `plugins/mill/scripts/_config.py` | 23 (signature), 42 (body) | parameter rename + path swap |
| `plugins/mill/scripts/_paths.py` | new | add `resolve_hub_path()` |
| `plugins/mill/scripts/_paths.py` | `resolve_wiki_path` line 303 | `git_toplevel / ".millhouse" / "config.local.yaml"` — also subfolder-install bug |

### Relevant existing helpers

- [`_paths.resolve_hub_relative_path(worktree_root, hub_subpath)`](plugins/mill/scripts/_paths.py#L204-L233) — translates `hub_relative_path` value to an absolute path. Reused by `millpy-terminal.py` and `millpy-vscode.py` (the correct-pattern reference). New code should call this for source→destination hub mirroring.
- [`_paths.resolve_main_worktree_root(git_root)`](plugins/mill/scripts/_paths.py#L92-L120) — walks up to the main worktree from a child. Already used inside `resolve_wiki_path`.
- [`_config.load_config(wiki_path, git_root)`](plugins/mill/scripts/_config.py#L23-L46) — the function being renamed.
- [`_setup.create_hub_links(target_root, wiki_path, tokens)`](plugins/mill/scripts/_setup.py) — used by both mill-setup (for hub) and mill-spawn (for new worktree). `target_root` is where the junctions/hardlinks are *created* — that's the hub of the receiving side. In subfolder-install the new worktree's hub is `worktree_path / hub_subpath`.
- [`_vscode.write_settings(color_hex, target, ...)`](plugins/mill/scripts/_vscode.py) — `target` is the absolute `.vscode/settings.json` path. Today spawn passes `worktree_path / ".vscode/settings.json"`; subfolder-install needs `worktree_path / hub_subpath / ".vscode/settings.json"`.
- [`_spawn_core.write_active_marker(mill_dir, ...)`](plugins/mill/scripts/_spawn_core.py) — `mill_dir` is `worktree_path / ".millhouse"` today; should be `worktree_path / hub_subpath / ".millhouse"`.

### Reference correct pattern

[`millpy-terminal.py:80-89`](plugins/mill/scripts/millpy-terminal.py#L80-L89):

```python
# Load per-worktree config to honour hub_relative_path.
if wiki_path is not None:
    try:
        worktree_cfg = _load_config(wiki_path, selected_path)
    except SystemExit:
        worktree_cfg = {}
else:
    worktree_cfg = {}
hub_subpath = worktree_cfg.get("hub_relative_path", ".")
launch_path = resolve_hub_relative_path(selected_path, hub_subpath)
```

This is the shape of the destination-side resolution mill-spawn / mill-worktree need: load the source's local config (which has `hub_relative_path` baked in by mill-setup), then use `resolve_hub_relative_path` to compute the matching destination path inside the new worktree.

### CLAUDE.md current state

[CLAUDE.md:48](CLAUDE.md#L48) says: *"`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths. Never hardcode `plugins/mill/...` — external repos have no millhouse source checkout."* This rule is correct but is about *intra-plugin* path references inside scripts/skills/templates — not about Bash commands typed at the agent level. CC reads it and concludes "scripts shouldn't say `plugins/mill`" — then types `uv run --project plugins/mill ...` in a Bash call without violating the rule as written.

[CLAUDE.md:94](CLAUDE.md#L94) says: *"Mill scripts are invoked via `uv run`, not `python`."* This is about the verb (`uv` vs `python`), not the project root. CC reads it, switches `python` to `uv run`, and still uses the source tree as `--project`.

The new rule needs to be unambiguous: *"In operational Bash commands, never reference `plugins/mill/...` or `plugins/codeguide/...` source-tree paths. Use `${CLAUDE_PLUGIN_ROOT}` (which resolves to the cache). Tests are the sole exception, and only when invoked from a test runner."* Pair it with one wrong/right example.

### gitignore mechanics

`_gitignore.py` exposes `GLOB_ENTRIES` and `ANCHORED_ENTRIES` lists used by `mill-setup` Phase 4.5b to maintain the marker block. Adding `**/plugins/*/uv.lock` to `GLOB_ENTRIES` propagates it to every mill-managed `.gitignore` (the repo's own and any external-repo `.gitignore` mill-setup writes into). Verify by inspecting `_gitignore.py` source and the existing `.gitignore` mill-managed block (lines 40-48 today).

### Test fixtures

Existing tests under `plugins/mill/unit_tests/`:

- `test-config.py` — covers `load_config`. Update to pass renamed parameter; add a test asserting the function reads from the *passed* directory, not the test's git root (subfolder-install assertion).
- `test-paths.py` — add tests for `resolve_hub_path()`.
- `test-millpy-claim.py`, `test-millpy-color.py`, `test-millpy-spawn.py`, `test-millpy-worktree.py` — update fixture layouts to exercise subfolder-install (place `.millhouse/` at `<fake-cwd>/.millhouse` while `<fake-git-root>` is two levels up). Assert the resulting writes land at the cwd-relative path.
- `test-millpy-spawn.py` — add a destination-side assertion: when source has `hub_relative_path: "src/Models"`, the new worktree's `.millhouse/`, `.vscode/`, and hub junctions land at `<worktree>/src/Models/...`.

Tests use in-memory / `tempfile` fixtures per [unit_tests/README.md](plugins/mill/unit_tests/README.md) — no real git, no real LLM. The subfolder-install test simply constructs a tempdir layout that simulates `<bigrepo>/src/Models/` as the hub.

### CLAUDE.md / SKILL.md verify pass

Grep result for `plugins/mill/scripts` outside test dirs:

- `plugins/mill/skills/mill-add/SKILL.md` — line 8 (descriptive prose, OK to keep), line 122/151 (in scaffolding-task example body — OK as illustrative content).
- `plugins/mill/skills/mill-resume/SKILL.md` — line 127 (descriptive cross-reference, OK).
- `plugins/mill/skills/mill-skills-index/SKILL.md` — line 20 (operational invocation pattern, but already prefixed with `${CLAUDE_PLUGIN_ROOT}` in the actual command on the next line — verify line 20 isn't itself an invocation).

The verify pass: re-grep, classify each hit as descriptive (keep) vs operational (fix), commit fixes.

## Constraints

- **Path invariants from CLAUDE.md must hold.** Junctions remain IDE/terminal convenience only. New code resolves real paths via `_paths.py`. The `resolve_hub_path()` helper does not consult any junction.
- **`${CLAUDE_PLUGIN_ROOT}` discipline preserved.** Nothing in this fix references the source repo from runnable code. CLAUDE.md sharpening makes the rule explicit, not new.
- **Existing tests must keep passing.** The signature rename in `_config.load_config` is the only ABI change; every call site is in this repo and gets updated atomically.
- **Test isolation.** All test fixtures use `tempfile`; no real git operations. Subfolder-install simulation is purely path arithmetic on a tempdir tree.
- **mill-merge cleanup must remove stale `plugins/mill/uv.lock`.** Verify the cleanup commit catches it; add to mill-merge's expected-untracked list if necessary.
- **No CONSTRAINTS.md present.** Confirmed via `ls` of repo root.
- **Cross-task coordination.** Phase-1 critical bugs (8 / mill-go SKILL.md, review-subsystem-fixes, this) are declared parallel-safe in `Home.md`. Verify that none of those tasks touches the same files. Cursory check: 8 is mill-go SKILL.md; review-subsystem-fixes targets review code. No overlap with the eight script files in this task. **Confirm during plan review.**

## Testing

### `_paths.resolve_hub_path()`

- **TDD candidate:** new function, tiny surface.
- **Cases:** no argument → returns `Path.cwd().resolve()`; explicit cwd argument → returns `cwd.resolve()`; relative cwd → resolved to absolute.

### `_config.load_config(wiki_path, worktree_root)` (renamed parameter)

- **TDD candidate:** signature change + behavior change.
- **Cases:** worktree_root has `.millhouse/config.local.yaml` → loaded and merged on top of wiki config; worktree_root has no `.millhouse/config.local.yaml` → falls back to wiki config alone; subfolder-install simulation → caller passes `<fake-cwd>` distinct from `<fake-git-root>`, function reads from `<fake-cwd>/.millhouse/config.local.yaml`.

### `millpy-claim.py`, `millpy-color.py`, `millpy-fetch-issues.py`

- **Cases:** for each, given a fake layout where `cwd != git_root`, assert the script reads/writes to `cwd / ".millhouse"`, `cwd / ".vscode"`, `cwd / ".scratch"` respectively. Existing happy-path tests must keep passing.

### `millpy-spawn.py` — destination-side hub mirroring

- **TDD candidate:** central regression risk.
- **Cases:**
  1. `hub_relative_path = "."` (the existing default) → `.millhouse/`, `.vscode/`, hub junctions, `create_hub_links` target_root, `_build_tokens` HUB_PATH/CWD_PATH all at `worktree_path`. (Regression test for the standard layout.)
  2. `hub_relative_path = "src/Models"` → all of the above at `worktree_path / "src/Models"`. (Subfolder-install assertion.)
  3. Portal junction in container/portals/<slug>/ points at `worktree_path` regardless of `hub_relative_path`. (Confirms terminal/vscode launch path remains correct.)

### `millpy-worktree.py` — same shape as spawn

- Mirror the spawn cases for the worktree create subcommand path.

### `.gitignore` mill-managed block

- Existing `test-gitignore-phase.py` covers the marker-block management. Add a case asserting `**/plugins/*/uv.lock` is in the rendered output.

### CLAUDE.md / SKILL.md changes

- No automated test. Manual review during the plan review pass.

### Integration smoke

- After all unit tests pass, run `plugins/mill/integration_tests/...` (whatever exists there) end-to-end to confirm spawn produces a working child worktree in the standard (cwd == git_root) layout.

## Q&A log

- **Q:** How wide should the (A) fix go — proposal-literal swap or full subfolder-install support? **A:** Full subfolder-install support (mirror hub_subpath in spawn / worktree dst, including `create_hub_links` target_root, `.vscode/` target, `.millhouse/` marker, and `_build_tokens` HUB_PATH/CWD_PATH).
- **Q:** Helper or inline `Path.cwd()`? **A:** `_paths.resolve_hub_path()` helper.
- **Q:** PreToolUse hook for source-tree paths? **A:** No. User does not trust hook reliability. Skip entirely.
- **Q:** `**/plugins/*/uv.lock` gitignore — repo-only or repo + template? **A:** Both (via `_gitignore.GLOB_ENTRIES`).
- **Q:** SKILL.md sharpening scope? **A:** mill-add + mill-setup explicit wrong/right examples, plus a one-shot verify pass over every operational SKILL.md to fix stragglers.
- **Q:** Touch `.wiki` paths now? **A:** No — that junction is introduced by the `rename-hub-junctions` Phase-4 task. Add a one-line note in CLAUDE.md so the future task adopts the convention from the start.
- **Q:** Stale `plugins/mill/uv.lock` already in main worktree — remove? **A:** Yes, as part of the mill-merge cleanup commit.
- **Q:** Was the proposal table exhaustive? **A:** No. Three additional sites discovered during exploration (millpy-claim.py:127, millpy-color.py:80, millpy-fetch-issues.py:62). Same fix pattern. Plus `_build_tokens` HUB_PATH/REPO and `_paths.resolve_wiki_path`'s line 303 `.millhouse/config.local.yaml` read. All silently in scope.
