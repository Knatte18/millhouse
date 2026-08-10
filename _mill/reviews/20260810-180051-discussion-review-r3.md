MILL_REVIEW_BEGIN
# Review: mill-go/mill-plan SKILL.md: undocumented mutation sequences, precondition bugs, and non-portable cross-references

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: /home/hanf/Code/millhouse/wts/mill-go-skilldoc-accuracy-gaps/_mill/discussion.md
date: 2026-08-10
```

## Findings

### [NIT:consistency] 810 rationale mischaracterizes 1187/1190/1195's literal call shape
**Section:** `### 810-mutation-sequence`, second Rejected bullet
**Issue:** The bullet says the rejected two-call pattern "match[es] 1187/1190/1195's literal wording" as `append_phase`+`update_field`. Source (SKILL.md:1187/1190/1195) actually reads `set batch state -> blocked, blocked_reason: "..."` + `_status.append_phase(...)` — mirroring lines 625-626's literal `_status.set_batch_field(status_path, batch_name, "state"/"blocked_reason", ...)` calls, not `update_field`. No `batch_name` exists in holistic scope, so this reused per-batch prose is itself an unflagged, unrelated latent ambiguity in those sibling lines.
**Fix:** Correct the Rejected bullet to say the sibling lines use `set_batch_field`-shaped prose (not `update_field`); the underlying decision to use `set_blocked` is unaffected either way.

## Verdict

APPROVE
Source-grounding checks (line numbers, helper signatures, precedent citations, verify-command counts) all confirmed accurate; only a minor rationale-wording nit remains.
MILL_REVIEW_END
