# Junction-rule enforcement + `resolve_wiki_path` extraction

```yaml
type: refactor (mill plugin) + CLAUDE.md rule
layer: bookkeeping / Layer 01 consolidation
v1_ref: none — cleanup of mill-v2 scripts
status: starting point — needs grilling before plan
priority: low — no functional bug, but the rule is documented in wiki/config.yaml and silently violated by three scripts; keeps getting forgotten
```

## Problem

Three scripts resolve the wiki via the `.millhouse/wiki` junction:

- [plugins/mill/scripts/mill-add.py:59-66](plugins/mill/scripts/mill-add.py#L59-L66)
- [plugins/mill/scripts/mill-spawn.py:178-186](plugins/mill/scripts/mill-spawn.py#L178-L186)
- [plugins/mill/scripts/mill-list.py:30-38](plugins/mill/scripts/mill-list.py#L30-L38)

Each copy has a private `_resolve_wiki_path()` that does `Path(".millhouse/wiki").resolve()` — identical logic, duplicated three ways, and all three treat the junction as the authoritative source.

This violates the invariant already documented in `wiki/config.yaml`:

> Junctions are IDE/terminal convenience. Scripts MUST resolve to the real wiki repo (`<WIKI_PATH>`-token value) and never treat the junction path as authoritative.

The rule is not in `CLAUDE.md`, so every new script writer independently reaches for `.millhouse/wiki` because it is the obvious discovery mechanism.

## Scope

Three deliverables, to land in one PR:

1. **Single-source `resolve_wiki_path(git_toplevel) -> Path`** — lives in `_wiki.py` (most natural home; it is where the read/commit/push helpers already live). Resolution order:
   1. `.millhouse/config.local.yaml` `wiki_path:` override (absolute path).
   2. `_sibling.resolve_path("wiki", git_toplevel)` — the convention already shipped in spec 00.
   The function does NOT look at `.millhouse/wiki` at all.
2. **Replace three call-sites** with `_wiki.resolve_wiki_path(_resolve_git_root())`. Delete the three private copies. Update their docstrings so the next reader knows the junction is pure UI.
3. **Add the rule to `CLAUDE.md`** under "Conventions worth carrying":
   > **Junctions are IDE/terminal convenience only.** Scripts MUST resolve to the real wiki repo via `_wiki.resolve_wiki_path(...)`, never by treating `.millhouse/wiki` (or any other junction) as a path. Junctions exist so the operator can type shorter paths in a shell / see the wiki tree in the sidebar — they are not a code contract.

Tests: `mill-spawn` and `mill-merge` integration tests already exercise the real wiki path end-to-end; a unit test around `resolve_wiki_path` covers the override + default branches.

## Decisions pending discussion

These need to be grilled out before the plan is written:

- **D1 — home for the helper.** Is `_wiki.py` right? Alternative: new `_paths.py` collecting `_sibling`, `resolve_wiki_path`, and future sibling-like resolvers. Lean: `_wiki.py` for now, move to `_paths.py` if/when the count grows beyond two.
- **D2 — override source.** `config.local.yaml`'s `wiki_path:` — does it remain a top-level key (as today) or move under a `paths:` block? Affects one line in the config template.
- **D3 — git-root discovery.** Each of the three scripts already has its own `_resolve_git_root()` (identical `git rev-parse --show-toplevel` call). Extract that too, or punt? Pure cleanup, but irrelevant if we later move to a `_paths.py` module anyway.
- **D4 — error surface.** Current private copies raise `SystemExit` with a "run /mill-setup" hint. Should the new helper raise a dedicated `WikiResolutionError`, or keep `SystemExit` for CLI-call-site ergonomics?
- **D5 — bigger layout question (parked).** Henrik floated moving junctions out of `.millhouse/` so `.millhouse/` only carries `config.local.yaml` + `active.slug.md`. That is a separate refactor with its own blast radius (`_worktree.copy_millhouse`, `.gitignore`, CLAUDE.md scratch rule). This spec does NOT touch that — decide in a follow-up.

## Out of scope

- Layout move of `.millhouse/wiki` → `.wiki`, `.active` placement, `scratch/` location. (Parked as D5.)
- Any change to `_junction.py`'s Windows/POSIX abstraction.
- Any change to the `junctions:` block in `wiki/config.yaml`.
- Migrating plugin-code junction references (codeguide/) — they are already sibling-aware via spec 00; no junction dependency.
