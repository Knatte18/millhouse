MILL_REVIEW_BEGIN
# Review: Migrate mill's generic skills to the shared scribe plugin

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: /home/knatte/Code/millhouse/wts/scribe-migration/_mill/discussion.md
date: 2026-09-29
```

## Findings

### [BLOCKING:consistency] update-plugins.ps1 has no inline Python to reuse
**Section:** Testing (`update-plugins.{sh,ps1}` bullet); scribe-refresh; remove-language-plugins **Issue:** Testing says to "keep the new version-comparison and orphan-detection logic in the inline Python the scripts already use", but `update-plugins.ps1` is pure PowerShell (`ConvertFrom-Json`, `robocopy`) with no Python call; only the `.sh` has inline `python3 -c`. **Fix:** State that the `.ps1` reimplements JSON reads, range-operator stripping, tuple comparison and orphan detection natively in PowerShell, and name how that logic is verified, since "side-by-side reading" is the only check for it.

### [NIT:decision] `installed_plugins.json` value shape
**Section:** Technical context; scribe-refresh step 2 **Issue:** The file is described as an object keyed `name@marketplace`, but each value is a list of per-scope entries (`installPath`, `version`), so "the installed scribe version" is ambiguous when several scopes exist. **Fix:** Say which entry supplies the version (e.g. the lowest, or any) for the min-version warning and for orphan detection.

### [NIT:consistency] Final grep cannot return "none outside `_mill/`"
**Section:** Testing, last bullet **Issue:** The pattern `(python|csharp|golang):` matches `mill_python:` in `plugins/mill/scripts/_shortcuts.py`, `update-plugins.sh` and `mill-setup/SKILL.md`, so the stated zero-hit outcome is false. **Fix:** Anchor the pattern (e.g. word-boundary or `[@ `]` prefix) or state the known false positives.

### [NIT:scope] Some stale references have no stated rewrite and no guard
**Section:** load-order; referential-rewrites; load-directive-test **Issue:** `mill-go2` line 16 also names `python:python-build`, `csharp:...` and `golang:...` trios but the decision only covers `mill:code-quality`/`mill:prose`; `templates/review-output.schema.md` line 68 cites a bare `` `prose` `` that the forbidden-name guard (which matches only `mill:<name>`) will not catch. **Fix:** List the `mill-go2` language trio explicitly and decide the disposition of the bare `prose` mention.

### [NIT:decision] Mill version bump not addressed
**Section:** scribe-dependency; remove-language-plugins **Issue:** mill's `plugin.json`/`marketplace.json` change (new `dependencies`, description) with version left at `2.0.0`; `claude plugin update mill` is version-gated and will not pick this up on machines that do not use `update-plugins`. **Fix:** State whether mill's version is bumped or deliberately left.

### [NIT:design] Load-directive test scope for rule 2 is unspecified
**Section:** load-directive-test **Issue:** Only rule 3 lists its file set; the retained tree-walk covers `plugins/*/skills/**/SKILL.md` and templates and explicitly excludes `.claude/skills/`, yet `.claude/skills/mill-pool/SKILL.md` is a named load-order site. **Fix:** State whether the order check (rules 1-2) walks `.claude/skills/` too.

## Verdict

REQUEST_CHANGES
The `.ps1` twin cannot follow the stated inline-Python approach; its implementation and verification need a decision.
MILL_REVIEW_END
