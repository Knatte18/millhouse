MILL_REVIEW_BEGIN
# Review: Migrate mill's generic skills to the shared scribe plugin

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: /home/knatte/Code/millhouse/wts/scribe-migration/_mill/discussion.md
date: 2026-09-29
```

## Findings

### [BLOCKING:scope] Scribe release tagging for a versioned dependency is unaddressed
**Section:** scribe-language-skills, scribe-dependency **Issue:** mill declares `"version": "^1.1.0"` on scribe, but the scribe batch only bumps manifests and pushes; if Claude Code resolves version ranges against release tags on the dependency's repo (unverified here, and the scribe repo has a single untagged commit), the range cannot resolve and the dependency fails or silently degrades. **Fix:** Decide now whether the scribe batch also creates and pushes a release tag, and state the outcome for the case where ranges need tags but none exist (bare `scribe@scribe` fallback vs tagging).

### [NIT:design] Minimum-version source in scribe-refresh step 2 is underspecified
**Section:** scribe-refresh **Issue:** the script reads the minimum "from the manifest", but the value is a range (`^1.1.0`), and the bare-string fallback in scribe-dependency carries no version at all. **Fix:** State how the inline Python derives the minimum from a range, and what step 2 does when the dependency is unversioned.

### [NIT:consistency] "Scribe's File writing rule covers both" overstates the match
**Section:** mill-layer-content (Task-state and scratch locations) **Issue:** mill's rule is `.scratch/` in the repo root; scribe's `conversation` says `.scratch/` under the current working directory, "never the repo root". Dropping mill's line changes behaviour for sessions whose cwd is a subdirectory, and `.scratch/prompt.md` in mill-conventions assumes the root. **Fix:** Either keep the repo-root default in `mill:conventions` or state that the cwd rule is accepted as settled drift.

### [NIT:scope] "Repo-agnostic" is defined by a grep that misses project-specific examples
**Section:** scribe-language-skills **Issue:** `python-build` contains `from solgt.timeseries import ...` and `utils_config` examples; the final `grep -nE "mill|millhouse|_mill|plugins/|@code:"` passes over them. **Fix:** Add a disposition for the `solgt`-specific example (keep, genericise) or widen the check.

### [NIT:scope] Forbidden-name guard enumerates only SKILL.md within skill dirs
**Section:** load-directive-test **Issue:** other files shipped under `plugins/*/skills/` (e.g. `mill-go-base/holistic-review.md`) are outside the listed surface, so the tree-walk cannot catch stale names there. **Fix:** Scan all `*.md` under `plugins/` and `.claude/skills/`, not only `SKILL.md`.

## Verdict

REQUEST_CHANGES
Versioned cross-marketplace dependency has no stated scribe release/tag disposition; remaining points are NITs.
MILL_REVIEW_END
