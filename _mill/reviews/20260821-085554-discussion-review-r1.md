MILL_REVIEW_BEGIN
# Review: mill-go2: fork-based dispatch reliability, shared-skill preloading, and catalog accuracy

```yaml
duration_s: 221.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Findings

### [NIT:consistency] "Recovery machinery works reliably" contradicts base skill's own caveat
**Demoted-from:** BLOCKING
**Section:** Out-of-scope / "warm-resume-then-cold-fallback unchanged" Decision
**Issue:** The Decision asserts the existing recovery "already works reliably as a safety net" and "resolved 100% of the observed cases," but `mill-go-base/SKILL.md`'s own "Why not fork?" (line 435) states fork's crash-resume path is explicitly *unverified* re: agentId/notification shape. Worse, the described zero-commit failure mode (0-1 tool calls, no JSON) classifies as `stuck_type: logic` (line 317), not `incomplete` — its escalation (lines 833-837) self-resolves ONCE by re-firing the implementer, which mill-go2's own override forks again ("Fork every fresh attempt ... Stuck-escalation verify/logic self-resolve re-fire"), with no cold fallback defined for that branch (mill-go2/SKILL.md's "Cold fallback, once per batch" is scoped only to the already-retried-`transient` path). A repeat of the same identity-confusion bug on the self-resolve retry blocks the batch entirely rather than recovering.
**Fix:** Confirm whether the logic-stuck self-resolve retry should also cold-fallback, or soften the "already works reliably"/"100%" framing to match the base skill's documented uncertainty.

### [NIT:consistency] Preload decision contradicts the "lean Builder" invariant
**Demoted-from:** BLOCKING
**Section:** Decisions → "shared-skill preload scope"
**Issue:** Preloading requires the Builder itself to load `code-quality`, `markdown`, plus up to 3 skills per detected language into its own context (fork inherits the parent's context) before the first fork dispatch. `mill-go-base/SKILL.md` states "You are the Builder — a lean orchestrator ... Keeping your context lean is the whole point — Builder cost is a rounding error" and Principles: "Lean Builder ... Your context stays small by design." The discussion never acknowledges this tension or bounds acceptable preload size.
**Fix:** Explicitly justify/accept the Builder-context growth in the rationale, or reconsider whether preload belongs in the Builder's own context.

### [NIT:consistency] Preload placement option risks leaking into plain /mill-go
**Demoted-from:** BLOCKING
**Section:** Scope → In: shared-skill preload ("mill-go-base if the override point is cleaner there — mill-plan decides placement")
**Issue:** `mill-go-base/SKILL.md` is loaded unconditionally by both `/mill-go` and `/mill-go2` (frontmatter, line 3). `/mill-go` never forks, so it gains zero benefit from preloading but — if mill-plan picks the mill-go-base placement without a gate — would pay the same token cost. This contradicts the catalog description's own "otherwise identical to /mill-go" premise and Out-of-scope's "mill-go-base ... unaffected by this task" statement.
**Fix:** Either fix placement at mill-go2 now (removing the ambiguity), or state explicitly that any mill-go-base placement must be gated on `VARIANT_LABEL == mill-go2` (or equivalent fork-usage check).

## Verdict

APPROVE
Recovery-reliability premise and preload-placement/context-cost tradeoffs need explicit reconciliation before plan writing.
_Note: 3 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
