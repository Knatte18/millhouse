# Review: 4 (A) — mill-setup: --from-url for separate wiki repo — 02-skill-and-template

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-skill-and-template
date: 2026-05-06
```

## Findings

### [BLOCKING] Phase 3.2 writes to .millhouse/ before it exists

**Step:** Card 5, Phase 3.2
**Issue:** Phase 3.2 is inserted after Phase 3.1 and before Phase 3.7. On a first-run with `--from-url`, `.millhouse/` is not created until Phase 4 (`create_hub_links` creates the `.millhouse/wiki` junction and must create the parent directory first). The Phase 3.2 invocation calls `_config.set_local_wiki_overrides(cfg_path=Path('.millhouse/config.local.yaml'), ...)` without any prior `mkdir`, so it fails with `FileNotFoundError` on every fresh install.
**Fix:** Either require that `set_local_wiki_overrides` calls `cfg_path.parent.mkdir(parents=True, exist_ok=True)` before writing (note this in Card 5's requirements so batch 01 implementers know it), or add an explicit `Path('.millhouse').mkdir(exist_ok=True)` in the Phase 3.2 SKILL.md invocation before the helper call.

### [NIT] argument-hint position instruction contradicts reference file

**Step:** Card 5, frontmatter section
**Issue:** The instruction says to place `argument-hint:` "between `name:` and `description:`", but codeguide-setup's SKILL.md (the named reference) places it after `description:`, not between the two.
**Fix:** Change the instruction to "after `description:`" to match the actual position in the reference file.

### [NIT] WikiPushError from pull path described too narrowly

**Step:** Card 5, Phase 3
**Issue:** The plan directs the SKILL.md to document that `WikiPushError` from the pull path "means the wiki has unmerged local commits". In `_wiki.py`, `WikiPushError` is raised for any `git pull --ff-only` failure including network errors and auth failures, not exclusively merge conflicts.
**Fix:** Change the documentation to "git pull failed — check network, credentials, or resolve any local divergence manually."

## Verdict

REQUEST_CHANGES
One blocking sequencing bug: `.millhouse/` directory is guaranteed absent on first run when Phase 3.2 fires.