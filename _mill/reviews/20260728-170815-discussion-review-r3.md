MILL_REVIEW_BEGIN
# Review: Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-28
```

## Findings

### [GAP] Finalize gate may reintroduce the just-fixed agent-output FileNotFoundError
**Section:** Decisions/merge-in-marker-verification (#713)
**Issue:** The Decision has `main()` read+`html.unescape` `args.agent_output` itself (to extract self-reported status before gating) before deciding whether to call `finalize_from_output` unchanged, but never says the new pre-read must replicate `finalize_from_output`'s existing `is_file()` guard (`_implementer_common.py` ~1296-1307, comment: "Guard against a raw, unhandled FileNotFoundError... crashing the implementer/fixer/merge-in CLI"). A literal `Path(args.agent_output).read_text(...)` in the new `main()` gate code, run before ever reaching `finalize_from_output`'s guard, reintroduces exactly the raw-crash class the repo's own last commit (8eb2cb05) fixed — but only for conflicts-mode finalize, since that guard is bypassed for the gate-fail branch and only reached via the gate-pass branch's later call.
**Fix:** State explicitly that the new pre-read in `main()` must reuse or replicate the `is_file()` -> actionable-stderr -> `return 1` guard before extracting status/running the marker gate, and add a Testing bullet for "missing `--agent-output` at `stage=finalize`, `mode=conflicts` still returns 1 with the actionable message, not a traceback."

### [GAP] Cache-lag YAML-guard's fallback control-flow (break vs. continue) unspecified
**Section:** Decisions/config-yaml-crash-fallback (#706), case 2 (line 229)
**Issue:** The line-229 loop tries `worktree_root`'s candidate template first, then `hub_root`'s, `break`-ing on the first that `.exists()` and differs from the resolved template (`_config.py:224-231`). The Decision says a caught `yaml.YAMLError` should "skip that source's contribution... and continue" but doesn't say whether the loop should still `break` after the failed candidate (abandoning cache-lag augmentation entirely) or fall through to try the next tuple entry. This isn't a rare corner case: it's exactly this task's own trigger shape — a task worktree mid-merge-conflict (markers in its copy of the source-tree template) while the hub's copy on a clean branch parses fine.
**Fix:** State explicitly whether a parse failure on the first matching candidate should fall through to try the remaining candidate(s), or unconditionally stop once any matching candidate is found regardless of parse success.

## Verdict

GAPS_FOUND
Two gaps: finalize-gate may reintroduce fixed FileNotFoundError; cache-lag YAML-guard fallback control-flow (break vs continue) unspecified.
MILL_REVIEW_END
