MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: entry, phase-gate, finalize, and re-entry path gaps

```yaml
duration_s: 299.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-13
```

## Findings

### [BLOCKING:design] `blocked` re-entry row ignores `--revise`'s reviews-subdir namespace
**Section:** Decisions — "Max-rounds block: add a `blocked` re-entry row (#832)"
**Issue:** The new `blocked` row inline-derives `reviews_dir` via the bare expression at SKILL.md:263, but omits the very next paragraph in that same "Path Setup (Plan Review)" section (SKILL.md:266-270), which reassigns `reviews_dir = reviews_dir / f"revise-{N+1}"` whenever a `--revise` session is active. `--revise`'s own pre-check (line 56-60) explicitly falls through into the ordinary Phase: Plan Review loop, which can itself hit step 6's max-rounds escape and write the same `"max-rounds exhausted"` `blocked_reason` — so this is a live, reachable combination, not a hypothetical.
Worse: `revise_requested` is derived only from `$ARGUMENTS` each invocation, never persisted in `status.md`, and the `--revise` pre-check's own condition requires `phase == "planned"` — which is false once `phase: blocked` — so an operator cannot re-supply `--revise` to recover the correct namespace when resuming. `discover_round` run against the un-namespaced `reviews_dir` will scan the wrong directory (finding 0 or stale pre-revise files), silently deriving a wrong round number and never re-arming `--reviews-subdir` for the resumed dispatch — losing continuity with the revise session's actual review history.
**Fix:** Have the `blocked` row's `reviews_dir` derivation reuse Path Setup (Plan Review)'s full logic, including the `revise-N` subdir probe (scan for existing `revise-<N>` subdirs and use the highest, rather than assuming none exists), and thread `--reviews-subdir` into the resumed dispatch when one is found — or explicitly decide and document that a max-rounds block occurring mid-`--revise` is an unsupported/hard-stop case distinct from the ordinary blocked row.

## Verdict

REQUEST_CHANGES
The #832 blocked-row fix has an unaddressed interaction with the pre-existing `--revise` reviews-subdir namespace.
MILL_REVIEW_END
