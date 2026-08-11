MILL_REVIEW_BEGIN
# Review: mill-go2: fork-based implementer dispatch

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (best-effort self-assessment)
reviewed_file: _mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:design] fork-fallback phase marker can break resume routing
**Section:** Decision `fork-fallback-status-marker`. **Issue:** the marker calls `_status.append_phase(status_path, f"fork-fallback-{batch_name}", ...)`, but `_status.append_phase` overwrites the top-level `phase:` yaml field (`_status.py:431`, `phase: {quote_scalar(phase)}`) — the exact field Entry's phase-table lookup reads (`mill-go-base/SKILL.md:109`). Existing mid-execution phase values written this way (`self-resolved-verify-logic`, `approved-{batch_name}` via `^approved-.*$`) are explicitly added to the widened phase-gate matching set (`SKILL.md:125-155`); `fork-fallback-{batch_name}` is not, and matches none of its literals or regexes. A crash/interrupt between this commit and the cold retry's own next phase write leaves `status.md` at an unrecognized phase, which the Entry table's "any other" row surfaces + halts rather than resumes. **Fix:** either route this event through the audit-trail `## Timeline` only (not the `phase:` field), or add `^fork-fallback-.*$` to the widened-matching regex set alongside `^approved-.*$`.

### [BLOCKING:consistency] "six per-tier agent-definition files" is stale
**Section:** Decision `model-and-effort-loss-is-documentation-only`. **Issue:** the rationale states "each of the six per-tier agent-definition files under `plugins/mill/agents/` pins a fixed `effort:`" (quoting `mill-go-base/SKILL.md:255`'s own stale comment, which names only medium/high/max). `_agent_dispatch.EFFORT_TIERED_SUBAGENT_TYPES` (`_agent_dispatch.py:68`) is actually `{low, medium, high, xhigh, max}` — 5 tiers — and `plugins/mill/agents/` contains 10 tiered files (`mill-implementer-{low,medium,high,xhigh,max}.md` + reviewer equivalents), confirmed by directory listing and `mill-implementer-low.md`'s frontmatter (`effort: low`). This task's variant documentation would carry the same superseded count forward. **Fix:** correct the number/enumeration to 5 tiers / 10 files (or state it generically without a stale count) before this lands in `mill-go2/SKILL.md`.

### [NIT:design] fork's agentId/notification contract is asserted, not confirmed
**Section:** Decision `fork-dispatch-shape`. **Issue:** "A fork returns an `agentId` and delivers a completion `<task-notification>` exactly as a cold agent does" is stated as fact, but no spike or doc confirms it — contrast with the two-notification-shape claim elsewhere in the base, explicitly marked "confirmed by a live spike... not assumed" (`SKILL.md:182`). Only indirect precedent exists: `mill-start/SKILL.md:184` shows `SendMessage` addressing a fork, implying some handle exists. **Fix:** note in the variant file (or run a cheap spike) confirming the fork notification/`agentId` shape before relying on steps 4/6.5 unmodified.

### [NIT:consistency] citation drift for the initial-implement dispatch point
**Section:** Decision `which-dispatch-points-fork` / Technical context. **Issue:** cites `### 1. Implement` at `mill-go-base/SKILL.md:572`; the heading itself is at line 553 (572 is mid-section, the agent-mode dispatch trigger line). **Fix:** cite line 553, or the range 553-572.

## Verdict

REQUEST_CHANGES
Two BLOCKING findings: an unrecognized status phase can break resume, and a stale tier-file count would ship into docs.
MILL_REVIEW_END
