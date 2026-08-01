MILL_REVIEW_BEGIN
# Review: Non-interactive pipeline: only mill-start's interview may prompt the operator — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not directly knowable to me)
reviewed_file: plan/
date: 2026-08-01
```

## Findings

### [BLOCKING] Card 9 scope-violations self-resolve can't reach its own halt path, risks destructive delete
**Location:** batch 04-mill-go-handoff-gates, Card 9
**Issue:** The self-resolve step classifies every `blocking_paths` entry with a strict binary rule — "matches a planned target" → `git add`+commit, "matches neither" → `git clean -f` (irreversible delete). No third "cannot classify with confidence" branch is described, yet the fallback halt text explicitly says "(a path could not be classified with confidence against the plan)". As written, every path is forcibly resolved (committed or permanently deleted) each pass, so `blocking_paths` will always come back empty and the halt is unreachable — or, if an implementer instead applies best-effort judgment for the "uncertain" case, the described binary rule gives no guidance on what to do (add/clean/leave alone), and a wrong guess in the cruft direction destroys real, uncommitted work with no recovery.
**Fix:** Add an explicit third branch: when a path cannot be confidently matched to a planned target or confidently identified as a known-cruft pattern, leave it untouched (neither `add` nor `clean`) so it correctly re-appears in the re-run's `blocking_paths` and triggers the existing halt.

### [BLOCKING] Card 10 (mill-merge stale-worktree self-resolve) omits the status.md audit-trail append required by Decision `audit-trail-via-status-timeline`
**Location:** batch 05-mill-merge-self-resolve, Card 10
**Issue:** The Shared Decision `audit-trail-via-status-timeline` states every self-resolve action appends a `_status.append_phase`-style row, and explicitly lists `mill-merge-self-resolve` in its `Applies to:`. Card 10's git-state investigation (choosing `mode = 'inplace'` or `mode = 'worktree'` in place of the removed `prompt_stale_worktree` call) is exactly this kind of brand-new self-resolve mechanism with no pre-existing status.md footprint — the same category as Cards 8 and 9 in batch 04, both of which DO add an explicit `_status.append_phase(status_path, "self-resolved-...", ...)` call. Card 10 has no equivalent append for either the `inplace` or `worktree` resolution outcome — only the inconclusive halt path is described, and even that halt doesn't append a status row.
**Fix:** Add `_status.append_phase(status_path, f"self-resolved-stale-worktree-{mode}", timestamp)` (or similar) when the git-state investigation resolves the ambiguity, matching the pattern already used in Cards 8/9.

### [NIT] Card 8's "genuinely ambiguous" halt framing doesn't match its unconditional-commit self-resolve step
**Location:** batch 04-mill-go-handoff-gates, Card 8
**Issue:** The self-resolve step commits ALL of `in_scope_dirt` unconditionally (no distinction between "clearly in-scope" and "ambiguous" dirt), yet the fallback halt's parenthetical says "(e.g. the dirt is genuinely ambiguous — neither clearly in-scope work nor clearly discardable)" — implying a judgment step that isn't actually present. `compute_terminal_dirt` already scopes to tracked, task-owned files only, so the unconditional-commit approach is safe, but the halt's own rationale doesn't match the mechanic that precedes it (likely a race/failure case, not "ambiguity").
**Fix:** Reword the parenthetical to reflect the real cause (e.g. "the commit or re-check itself failed, or new dirt appeared concurrently") rather than "ambiguous."

### [NIT] Card 10's "entry present/current/branch matches → worktree" branch may be logically unreachable
**Location:** batch 05-mill-merge-self-resolve, Card 10
**Issue:** The trigger condition for this whole edge case already establishes that cwd is on the active task's branch (via `_marker.task_data` success in Entry Step 1). Git does not allow the same branch to be checked out in two worktrees simultaneously, so a `git worktree list --porcelain` entry showing that same branch registered at `<worktrees-dir>/<slug>/` while cwd also has it checked out seems contradictory — this branch of the new logic may never actually fire. (Low confidence: "the branch matches" in the original trigger text was already ambiguous about which branch is being compared, and this ambiguity is carried over unchanged rather than introduced by this batch.)
**Fix:** Clarify what "the branch matches" refers to at the trigger condition, and confirm via a quick worktree-topology sanity check whether the `mode='worktree'` resolution branch is reachable in practice.

## Verdict

REQUEST_CHANGES
Card 9's destructive-delete gap and Card 10's missing audit-trail append need fixing before approval.
MILL_REVIEW_END
