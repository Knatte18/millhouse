MILL_REVIEW_BEGIN
# Review: Skill doc/table accuracy gaps across mill-groom, mill-start/mill-plan, and implementer-brief — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-07-25
```

## Findings

### [BLOCKING] Card 3 introduces a duplicate `discussed` status append + redundant commit
**Location:** Batch 1 / Card 3, edit 1 (interactive step 4b) and edit 2 (Auto mode restatement)
**Issue:** Edit 1 adds `_status.append_phase(status_path, "discussed", ...)` to step 4b's commit, but the wording "Push. Break loop → Handoff." is kept verbatim, so `### Phase: Handoff` (unchanged) still runs unconditionally right after and itself calls `_status.append_phase(status_path, "discussed", timestamp)` followed by its own separate `git commit -m "mill-start: handoff {slug}"`. `_status.append_phase` (`plugins/mill/scripts/_status.py`) is unconditional — it appends a new Timeline row and overwrites `phase:` on every call, with no dedup — so every normal (non-crash) run through 4b now produces two consecutive `discussed` Timeline rows and two back-to-back commits instead of one clean transition. Edit 2 (Auto mode) inherits the same bug since it delegates to 4b's sequence and also retains "break loop → Handoff."
**Fix:** Card 3 must also update `### Phase: Handoff` to make its `_status.append_phase(status_path, "discussed", ...)` + commit conditional/idempotent (e.g. skip if the timeline's last phase is already `discussed`), or have 4b's break route around Handoff's redundant append+commit entirely.

### [NIT] Card 4's Batch Tests verification step needs a file not in Card 4's Context
**Location:** Batch 1 / Batch Tests, Card 4 line
**Issue:** The verification instruction for Card 4 says to confirm the new CLAUDE.md bullet "does not contradict `python-build/SKILL.md`'s generic (non-`uv`-specific) guidance," but Card 4's `Context:` is `none` and `python-build/SKILL.md` (`plugins/python/skills/python-build/SKILL.md`) is not listed anywhere in the card. (Content checked: it is indeed generic/ruff-only with no `uv` mention, so the claim itself is accurate — only the missing Context pointer is the gap.)
**Fix:** Add `plugins/python/skills/python-build/SKILL.md` to Card 4's `Context:` so the verification step isn't a cold-start lookup.

## Verdict

REQUEST_CHANGES
Card 3's status-append fix duplicates the `discussed` Timeline entry via unmodified Phase: Handoff; must be closed.
MILL_REVIEW_END
