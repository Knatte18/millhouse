# Review: script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo — 04-docs-gitignore

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 04-docs-gitignore
date: 2026-05-04
```

## Findings

### [NIT] Existing tests already cover new GLOB_ENTRIES entry implicitly
**Step:** Card 15 — test assertion
**Issue:** The existing same-path test iterates `for entry in GLOB_ENTRIES + ANCHORED_ENTRIES` and fails if any entry is missing from written content. Adding `**/plugins/*/uv.lock` to `GLOB_ENTRIES` means the existing loop already exercises it; the dedicated `render_block` assertion the plan calls for duplicates that coverage.
**Fix:** Keep the dedicated assertion — it is clearer and more direct as a regression anchor. Note that `render_block` is not currently imported in `test-gitignore-phase.py`; the implementer must add it to the `from _gitignore import (...)` block.

### [NIT] mill-skills-index/SKILL.md in Modifies but verify pass likely yields no-change
**Step:** Card 14 — verify pass classification
**Issue:** Line 20 of `mill-skills-index/SKILL.md` reads `v2's flat-layout entrypoint is plugins/mill/scripts/millpy-skills-index.py` — descriptive prose, not an invocation. The operational command below it already uses `${CLAUDE_PLUGIN_ROOT}`. The card's "if so, fix" qualifier handles this correctly, but the file appearing in Modifies may prompt an unnecessary edit.
**Fix:** No fix needed in the plan; the card's classification logic is correct. The implementer should confirm no-change after verification and leave the file untouched.

## Verdict

APPROVE — no BLOCKINGs; both NITs are implementation-clarity notes, not correctness defects.