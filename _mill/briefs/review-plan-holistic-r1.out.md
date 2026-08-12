MILL_REVIEW_BEGIN
# Review: CLAUDE_PLUGIN_ROOT environment variable not exported to Bash tool — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: plan/
date: 2026-08-12
```

## Findings

### [BLOCKING:scope] Card 3 Requirements name `_claude_settings` identifiers absent from its Context
**Location:** Batch 01, Card 3 **Issue:** The Phase 4.8 replacement block Requirements literally reproduces `_claude_settings.merge_permission_allowlist(...)` and `_claude_settings.MILL_SUBAGENT_TOOLS`, but Card 3's `Context:` lists only `_config.py` and its `Edits:` lists only `SKILL.md` — `_claude_settings.py` (the file these names live in) is not in either list. **Fix:** Add `plugins/mill/scripts/_claude_settings.py` to Card 3's `Context:`, or note explicitly that the block is reproduced verbatim/unchanged so no exploration of that file is needed.

### [NIT:consistency] New helper omitted from `__all__` and from the (already-incomplete) Exports docstring convention
**Location:** Batch 01, Card 1 **Issue:** `_config.py`'s `__all__` (lines 31-41) lists `resolve_plugin_template_path` but the module's top-of-file "Exports" docstring block (lines 3-9) already omits both `resolve_plugin_template_path` and `resolve_repo_config_path` — so Card 1's instruction to "add one line ... following that block's existing one-line-per-export convention" cites a convention that's only partially followed by its own model function, and the card never asks for a corresponding `__all__` entry for the new public helper. **Fix:** Add `resolve_plugin_root_from_syspath` to `__all__` explicitly in Card 1's Requirements (functionally harmless today since call sites use `_config.<name>`, but leaves the export surface inconsistent).

### [NIT:consistency] Card 3 commit message covers only one of the two edited snippets
**Location:** Batch 01, Card 3 **Issue:** The commit `fix(mill-setup): resolve plugin root via sys.path scan in Phase 4.8` covers both the Phase 4.8 write block and the separate Phase 8 verify one-liner, but the message mentions only Phase 4.8. **Fix:** Broaden the message, e.g. `fix(mill-setup): resolve plugin root via sys.path scan in Phase 4.8 write + Phase 8 verify`.

## Verdict

REQUEST_CHANGES
One BLOCKING context-completeness gap in Card 3; two consistency NITs, none of which change plan direction.
MILL_REVIEW_END
