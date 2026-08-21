MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: Phase Plan Review gate, convergence, and DAG-validation correctness bugs

```yaml
duration_s: 315.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (Sonnet 5 generation, "sonnethigh"-class)
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Findings

### [BLOCKING:design] #887's `batch_creates` key space is unspecified and likely wrong
**Section:** `### #887 — new validator check: cross-batch Creates: reference requires a depends-on edge`
**Issue:** `_compute_transitive_ancestors` returns a dict keyed by batch `entry["name"]` (the human `<batch-name>` field), not by file stem — confirmed by `_check_parallel_modifies_overlap`'s own `batch_name_to_path` mapping step, which exists specifically to bridge name-keyed ancestors to stem-derived per-file parsing. `plan-overview.md`'s template shows `name:` and `file: NN-<batch-slug>.md` are distinct strings (stem carries the `NN` prefix, name does not). The decision says only "Build `batch_creates: dict[str, set[str]]`... via `_parse_creates_only`" (naturally stem-keyed if built by iterating `batch_files`) and then indexes `ancestors[B]` directly with `C not in ancestors[B]` — a silent key-space mismatch unless the same name→path bridging step is carried over.
**Fix:** Explicitly specify that `batch_creates` (and the per-batch Context:/Edits: scan) must be keyed by `entry["name"]`, mirroring `_check_parallel_modifies_overlap`'s `batch_name_to_path` mapping, not by file stem.

### [NIT:consistency] #896's Testing claim asserts a nonexistent Python test target
**Demoted-from:** BLOCKING
**Section:** `## Testing` — `**#896**`
**Issue:** Claims a unit test can assert "`_status.append_phase` is called with `plan-review-r{N}` exactly once per round dispatch regardless of which of 4a/4b/4c/4d verdict branch is taken — TDD candidate, mechanically-testable." No Python module implements this branching (`grep` for `plan-review-r|plan-fix-r` across `scripts/` hits only a docstring example in `_status.py`) — the entire 4a-4d dispatch is SKILL.md prose interpreted by the orchestrating LLM, exactly the "SKILL.md-level behavior... not independently unit-testable" case #902's own Testing entry correctly carves out for the identical class of problem.
**Fix:** Reword #896's Testing entry to match #902's hedge — no unit test exists for the branch-dispatch behavior itself; note it as SKILL.md-level/manually-verified, or explicitly decide to extract the round-append logic into a testable helper (and add that extraction to the Decision, not just Testing).

### [NIT:consistency] #895 omits the established template-comment sync for new pipeline keys
**Section:** `### #895 — entry-gate wait grace window for transient blocked`
**Issue:** The sibling keys `pipeline.entry_wait` / `pipeline.entry_wait_timeout_minutes` are both documented with inline comments in `plugins/mill/templates/mill-config.yaml` (lines 127-128). The new `pipeline.entry_wait_blocked_grace_s` key has no equivalent template-sync step in the decision, unlike #861 which explicitly calls out syncing `mill-config.yaml`/template per CLAUDE.md's "hub file and plugin template must stay in sync" rule.
**Fix:** Add a template-comment line for `pipeline.entry_wait_blocked_grace_s` alongside its two siblings.

## Verdict

REQUEST_CHANGES
Fix #887's keying gap and #896's testing-claim mismatch before plan writing.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 1._
MILL_REVIEW_END
