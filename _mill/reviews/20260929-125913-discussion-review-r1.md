# Review: Migrate mill's generic skills to the shared scribe plugin

```yaml
verdict: REQUEST_CHANGES
reviewer_model: orchestrator
reviewed_file: _mill/discussion.md
date: 2026-09-29
```

## Findings

### [BLOCKING:design] No step brings the installed scribe cache to 1.1.0
**Section:** Decisions / scribe-language-skills, scribe-dependency; Scope "Out" ("Running `./update-plugins.sh` or refreshing any plugin cache").
**Issue:** scribe is installed from the GitHub marketplace, and `installed_plugins.json` pins `scribe@scribe` at `1.0.0` (cache `~/.claude/plugins/cache/scribe/scribe/1.0.0`, commit `5e5179f`).
`update-plugins.sh` only rsyncs millhouse's own `plugins/<name>` into the millhouse cache, so it never touches scribe.
After merge and `./update-plugins.sh`, mill's implementer directive and agent files name `scribe:python-comments` / `scribe:csharp-*`, which do not exist in the installed scribe.
Once the operator follows the new orphan hint and uninstalls `python@millhouse`, Python/C# conventions exist nowhere on that machine.
The manifest `dependencies` entry does not help either: mill reaches the cache through rsync, not an install/update that would resolve dependencies.
**Suggested fix:** Make the scribe refresh part of the migration.
Have `update-plugins.{sh,ps1}` run `claude plugin marketplace update scribe` then `claude plugin update scribe@scribe` when `scribe@scribe` is installed, or at minimum warn when its installed version is below the version mill's `dependencies` requires.
State the post-merge operator sequence in the discussion: refresh scribe, run `./update-plugins.sh`, then uninstall the orphans.

### [NIT:consistency] `mdreflow.py` path reference not covered
**Section:** referential-rewrites.
**Issue:** `plugins/mill/scripts/tools/mdreflow/mdreflow.py` line 5 cites the file path `plugins/mill/skills/prose/SKILL.md`, not only the `mill:prose` name the discussion rewrites.
The forbidden-name guard matches `mill:<name>` and so misses this path.
**Suggested fix:** Rewrite that line to "the `scribe:prose` skill's Line breaks section", mirroring the `pydocreflow.py` decision.
Optionally extend the guard to forbid `plugins/mill/skills/(prose|conversation|code-quality|code-comments|testing|handoff)` and `plugins/(python|csharp|golang)/` paths.

### [NIT:design] The dependency must not break mill installs on machines without the scribe marketplace
**Section:** scribe-dependency.
**Issue:** The plan says it will fetch the docs page, but the discussion does not say what happens when a mill install cannot resolve a cross-marketplace dependency, for example in an external repo on a machine that has not added `Knatte18/scribe`.
**Suggested fix:** While confirming the field names from the docs, also confirm the failure behaviour (hard install failure vs warning), and make sure the `mill-setup` precondition text matches it.

## Verdict

REQUEST_CHANGES
The design is sound and well-grounded; the one gap is that nothing moves the installed scribe from 1.0.0 to 1.1.0, so the scribe-qualified Python/C# skill names would resolve to nothing after merge.
