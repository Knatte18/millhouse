# Review: codeguide sibling-mode + unified sibling-path convention — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnet-4-6 (via Agent tool)
reviewed_file: specs/component/00-plan/
date: 2026-04-23
```

## Findings

### [BLOCKING] `mill-setup.py` does not exist
**Location:** Batch mill-integration / Card 9; plan's "All Files Touched" list
**Issue:** Card 9 modifies `plugins/mill/scripts/mill-setup.py`, but no such file exists — only `mill-spawn.py`, `mill-add.py`, `mill-list.py`, `mill-review-*.py`, and `mill-skills-index.py` are present. The card already hedges ("if mill-setup's implementation does NOT currently carry a wiki_path default… this card is a no-op"), but a no-op card against a non-existent file misleads the implementer and silently skips a real behaviour gap.
**Fix:** Either confirm `mill-setup.py` does not exist (remove the card and document where the wiki-path default actually lives — likely in mill-spawn or a helper — so the spec's intent is still covered), or create the script as a prerequisite card.

### [BLOCKING] `resolve.py` on-disk path diverges from every plan/skill reference
**Location:** Batch codeguide-plugin / Cards 3, 4, 6; Batch docs / Card 13
**Issue:** The file on disk is `plugins/codeguide/scripts/resolve.py`. Every existing skill (`codeguide-setup`, `codeguide-update`, `codeguide-generate`, `codeguide-maintain`) invokes it as `${CLAUDE_PLUGIN_ROOT}/scripts/millpy/codeguide/resolve.py`. The plan creates `codeguide_commit.py` alongside it at `plugins/codeguide/scripts/millpy/codeguide/codeguide_commit.py` — a directory that does not exist. Running any skill today would fail at that `python` call. The plan must reconcile this: either move/copy `resolve.py` to `scripts/millpy/codeguide/` (making the skills correct) or update all skill references to `scripts/resolve.py`. This also affects Card 3's import path for `_sibling.py` from the codeguide plugin.
**Fix:** Add a Card 0 (or first card of codeguide-plugin batch) that moves `resolve.py` to `plugins/codeguide/scripts/millpy/codeguide/resolve.py` and creates the `millpy/codeguide/` package. All downstream cards then write to a real path. Alternatively, flatten: keep `resolve.py` at `scripts/` and place `codeguide_commit.py` there too, and fix all skill references in the same card.

### [BLOCKING] Cross-plugin import in Card 3 is not `${CLAUDE_PLUGIN_ROOT}`-safe
**Location:** Batch codeguide-plugin / Card 3
**Issue:** Card 3 requires `resolve.py` to import `_sibling.py` via `${CLAUDE_PLUGIN_ROOT}/../mill/scripts/_sibling.py` — a relative navigation from the codeguide plugin root into the mill plugin. The spec's own hard rule ("All plugin scripts reference `${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths. Never assume millhouse source is cloned.") means `../mill/` is only valid if both plugins always install in sibling directories. Plugin install location is not guaranteed. The spec calls `_sibling.py` "consumed by… codeguide `resolve.py`" but gives no safe cross-plugin call convention.
**Fix:** Instead of importing `_sibling.py` directly, have `resolve.py` call `python ${MILL_PLUGIN_ROOT}/scripts/_sibling.py` as a subprocess (role + repo-root as CLI args), or expose `_sibling`'s logic as a tiny inline fallback function in `resolve.py` that duplicates the three-line rule (acceptable since it is pure arithmetic with no future divergence risk). Document which approach is chosen.

### [NIT] Card 5 writes `mode:` into Overview.md frontmatter — not in spec decisions
**Location:** Batch codeguide-plugin / Card 5
**Issue:** "Mode the skill writes into the overview's frontmatter: `mode: inline | sibling`. Resolve.py reads this as a cross-check." This field does not appear anywhere in the spec's decisions. The spec's resolve chain is deterministic from the file-system walk; it needs no stored mode flag.
**Fix:** Drop the frontmatter requirement unless the implementer has a concrete reason to store it. If kept, add a spec decision entry explaining the cross-check purpose and what happens when the stored value disagrees with the walk result.

### [NIT] `codeguide-setup` SKILL.md uses `---` YAML frontmatter — plan must preserve it
**Location:** Batch codeguide-plugin / Card 5
**Issue:** The existing `codeguide-setup/SKILL.md` has `---` frontmatter (confirmed on disk). The markdown skill convention only forbids `---` in *generated* docs; `SKILL.md` files are explicitly allowed to use it. The card says "rewrite" — ensure the implementer preserves the `---` block and only edits the body.
**Fix:** Add a bullet to Card 5 requirements: "Preserve the existing `---` YAML frontmatter header (`name:`, `description:`, `argument-hint:`). Update `argument-hint:` to include `[--sibling] [--from-url <git-url>]`."

## Verdict

REQUEST_CHANGES
Two path-grounding BLOCKINGs (missing `mill-setup.py`, wrong `resolve.py` directory) and one design-safety BLOCKING (cross-plugin import) must be resolved before implementation.
