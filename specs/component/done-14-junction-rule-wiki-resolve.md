# Junction-rule enforcement + `_paths.py` consolidation

```yaml
type: refactor (mill plugin) + CLAUDE.md rule + .scratch relocation
layer: bookkeeping / Layer 01 consolidation
v1_ref: none — cleanup of mill-v2 scripts
status: done — merged to main 2026-04-24 (branch impl/14-junction-rule-wiki-resolve)
priority: low — no functional bug, but the invariant is documented in wiki/config.yaml and silently violated by three scripts; keeps getting forgotten
```

**Implementation notes:** `plugins/mill/scripts/_paths.py` now owns `resolve_git_root` + `resolve_wiki_path`, and re-exports `resolve_path` from `_sibling` (identical-twin rule with codeguide preserved). `resolve_wiki_path` reads `paths.wiki:` from `.millhouse/config.local.yaml` if present, otherwise delegates to the sibling default; it never touches the `.millhouse/wiki` junction. `mill-add.py`, `mill-spawn.py`, `mill-list.py` all migrated — three private `_resolve_wiki_path` + three `_resolve_git_root` copies deleted. Error text now names the override key explicitly: "Wiki not found at {path}. Run /mill-setup to create it, or set paths.wiki: in .millhouse/config.local.yaml." Scratch moved from `.millhouse/scratch/` to `<cwd>/.scratch/` — 9 integration tests + 4 SKILL.md files + 2 active specs + `mill-merge` lock location + `.gitignore` + `_worktree.copy_millhouse` all updated. `test-worktree.py` repurposed to assert junction-alias exclusion. CLAUDE.md gained a `## Path invariants` section documenting the junction rule, `_paths.py` as the single resolver surface, and the scratch relocation. Full verify (17 unit tests + 4 integration tests) passes.

## Problem

Three scripts resolve the wiki via the `.millhouse/wiki` junction:

- [plugins/mill/scripts/mill-add.py:59-66](plugins/mill/scripts/mill-add.py#L59-L66)
- [plugins/mill/scripts/mill-spawn.py:178-186](plugins/mill/scripts/mill-spawn.py#L178-L186)
- [plugins/mill/scripts/mill-list.py:30-38](plugins/mill/scripts/mill-list.py#L30-L38)

Each copy has a private `_resolve_wiki_path()` that does `Path(".millhouse/wiki").resolve()` — identical logic, duplicated three ways, all treating the junction as the authoritative source. Each also has a duplicate `_resolve_git_root()` (`git rev-parse --show-toplevel`).

This violates the invariant documented in `wiki/config.yaml`:

> Junctions are IDE/terminal convenience. Scripts MUST resolve to the real wiki repo (`<WIKI_PATH>`-token value) and never treat the junction path as authoritative.

The rule is not in `CLAUDE.md`, so every new script reaches for `.millhouse/wiki` because it is the obvious discovery mechanism.

Relatedly: `.millhouse/scratch/` is the documented scratch location, but it is (a) copied past `.millhouse/` boundary on worktree-propagation logic (`copy_millhouse` excludes `scratch` by name — fragile), and (b) invisible to other plugins the engineer uses that default to a top-level `.scratch/` as their scrap-book. Promoting `.scratch/` to cwd-root solves both.

## Scope

Four deliverables, landing in one PR:

1. **`_paths.py` module in mill plugin** — single home for path resolution. Contents:
   - `resolve_path(role, repo_root)` — re-exported from `_sibling.py` (identical-twin rule for codeguide preserved; mill callers get a single import surface).
   - `resolve_git_root() -> Path` — wraps `git rev-parse --show-toplevel`.
   - `resolve_wiki_path(git_toplevel) -> Path` — reads `.millhouse/config.local.yaml` for `paths.wiki:` override; falls back to `resolve_path("wiki", git_toplevel)`. Never touches `.millhouse/wiki`.
   - Raises `PathResolutionError` (or re-uses `SystemExit` with improved message that names the override path explicitly).
2. **Call-site migration** — replace the three private `_resolve_wiki_path()` and three `_resolve_git_root()` copies in `mill-add.py`, `mill-spawn.py`, `mill-list.py` with imports from `_paths`. Update docstrings so the next reader knows the junction is pure IDE.
3. **`.scratch/` relocation** — move `.millhouse/scratch/` → `.scratch/` at cwd-root. Updates: `.gitignore`, CLAUDE.md rule text, `plugins/mill/skills/conversation/SKILL.md`, every integration test's `SCRATCH = HUB / ".millhouse" / "scratch"` constant, `_worktree.copy_millhouse`'s `scratch` exclusion (removable — no longer inside `.millhouse/`), and the corresponding `test-worktree.py` assertion.
4. **`CLAUDE.md` gains a `## Path invariants` section** — new section (not a bullet under existing conventions) so path rules have a dedicated home to grow in. Contents: junction rule + pointer to `_paths.py` + scratch location rule.

Tests: `mill-spawn` and `mill-merge` integration tests exercise the real wiki path end-to-end; a new unit test `test-paths.py` covers the override + default branches of `resolve_wiki_path`.

## Decisions (locked)

- **D1 — `_paths.py` in `plugins/mill/scripts/`.** Single module; imports `resolve_path` from the existing `_sibling.py` rather than duplicating, so the codeguide identical-twin rule stays intact.
- **D2 — `paths:` block in `.millhouse/config.local.yaml`.** `paths.wiki:` lives in config.local.yaml ONLY (avoids bootstrap circularity — can't put wiki-path override inside the wiki). Other path overrides (`paths.worktrees:`, `paths.codeguide:`) MAY be added in `wiki/config.yaml` in the future for team-shared defaults; not implemented in this spec.
- **D3 — `resolve_git_root` extracted to `_paths.py`.** Same rationale as wiki-path; three identical copies today.
- **D4 — error message names the override path.** New text: `"Wiki not found at <resolved-path>. Run /mill-setup to create it, or set paths.wiki: in .millhouse/config.local.yaml."`.
- **D5 — `.wiki` junction stays at `.millhouse/wiki/`** (IDE convenience preserved — one sidebar folder, not four top-level junctions). **`.scratch/` moves to cwd-root** because (a) other plugins the engineer uses default to a top-level `.scratch/`, and (b) it decouples "scratch" from "the millhouse-propagated subset" entirely.
- **CLAUDE.md organisation.** New `## Path invariants` section — path rules keep being forgotten; giving them a dedicated section makes them easier to spot and accumulate.

## Out of scope

- Moving `.wiki` / `.active` junctions out of their current locations (decided against for IDE clutter reasons).
- Moving `active.slug.md` (stays in `.millhouse/` as a worktree-marker; propagated via `copy_millhouse`).
- Any change to `_junction.py`'s Windows/POSIX abstraction.
- Any change to the `junctions:` block in `wiki/config.yaml` (the junction-creation side — still correct).
- `paths.worktrees:` / `paths.codeguide:` as config keys in `wiki/config.yaml` (deferred; wait for concrete demand).
- Mill-codeguide seed (spec 13) — still gated on mill-v2 self-sufficiency, independent of this work.
