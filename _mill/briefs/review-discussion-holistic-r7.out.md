MILL_REVIEW_BEGIN
# Review: millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact minor version not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:consistency] Stale "no reader exists" claim contradicts its own correction
**Section:** `## Technical context`, `_status.py` bullet (append_phase/timeline line). **Issue:** This bullet still reads "the phase timeline (`append_phase`, line 429; consumed nowhere currently -- no reader exists) is the available signal instead" -- verbatim the premise Decision `956-timeline-reader-already-exists` explicitly says was "factually wrong, caught on review" because `_status.read_full` already exists and is the established reader. The Technical Context bullet was never updated after that correction, so the artefact now contradicts itself. **Fix:** Update the Technical Context bullet to say the timeline is read via `_status.read_full` (already confirmed used elsewhere, e.g. `mill-go-base/SKILL.md:107-113`), removing the superseded "no reader exists" phrase.

### [BLOCKING:design] Testing candidate (b) can't prove what it claims for 3 of 4 call sites
**Section:** `## Testing`, `_implementer_common.py (#954)` TDD candidate (b); also Decision `954-commit-baseline-write-before-dirty-check`'s "all four call sites" sub-bullet. **Issue:** Verified in `_implementer_common.py`: `_in_scope_dirty_stuck` is called exactly once in the whole file, at line 1975, only inside the explicit-JSON-success branch that starts its gate call at line 1865. The three "no-JSON-inference" branches (gate calls at 2091, 2201, 2311) never call `_in_scope_dirty_stuck` at all -- their own inline dirty checks run *before* `_run_verify_gates`, and nothing downstream of those three calls re-checks tree cleanliness. So the specific self-trip mechanism #954 describes structurally cannot occur via those three paths, and driving test (b) through any of them and asserting "success, not stuck/logic" would pass whether or not `git_name`/`git_email` were threaded to that call site -- it does not prove threading occurred. **Fix:** Either drop the "proves threading to all four sites" framing for test (b) and replace it with an assertion that actually discriminates (e.g. status.md is committed / no working-tree diff remains after the corroboration branch fires on a no-JSON-inference path), or explicitly note in the discussion that sites 2/3/4 are fixed for uncommitted-write hygiene (avoiding a later, separate mill-go terminal-cleanliness false-positive) rather than for the identical #954 self-trip.

## Verdict

REQUEST_CHANGES
Two blocking issues: a stale self-contradicted claim, and a non-discriminating test premise for 3 of 4 gate call sites.
MILL_REVIEW_END
