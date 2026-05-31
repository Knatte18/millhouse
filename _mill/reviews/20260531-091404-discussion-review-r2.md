# Review: haiku-implementer-reliability

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-31
```

## Findings

### [NOTE] Subprocess vs. pygit2 in compute_scope_violations
**Section:** Decisions — scope-violations detection / Testing
**Issue:** The decision says `compute_scope_violations` "runs `git -C <worktree> status --porcelain --untracked-files=normal`" (subprocess), but `_cleanliness.py` uses `_pygit2_util.status_porcelain` throughout; the testing section then prescribes "real git init fixture" which is only necessary for a subprocess implementation.
**Fix:** Clarify whether the new function should use `_pygit2_util.status_porcelain(worktree, include_untracked=True)` (consistent with module pattern, mock-testable) or a subprocess (requires real git fixture); the existing `_pygit2_util` already filters ignored files and returns `?? ` lines, so the module pattern is the natural choice.

### [NOTE] Unknown-key warning rationale is wrong
**Section:** Decisions — per-reviewer timeout override / Out
**Issue:** "unknown extra keys in the agent spec already emit a stderr warning rather than hard-failing" — this warning fires only for local-overlay entries overriding template entries (`_reviewers.py` L190–199); adding `timeout` to the template itself emits no warning, it is silently accepted.
**Fix:** Correct to: `_validate_and_return` only checks required fields (`type`, `provider`, `model`) and does not reject extra keys, so `timeout` in the template passes without any warning or error.

### [NOTE] scope_violations unspecified for fallback path
**Section:** Decisions — scope-violations detection
**Issue:** The decision specifies `scope_violations` behavior for the explicit-JSON path and the inferred-success path but is silent on the third branch — the final `{"status":"stuck","stuck_type":"logic","reason":"no structured report"}` fallback.
**Fix:** Clarify whether `scope_violations` should be merged into that fallback JSON when violations exist (likely yes, since the operator needs full context).

### [NOTE] mill-config.yaml template not in sync scope
**Section:** Scope — mill-config.yaml (hub config)
**Issue:** `max_implementer_prompt_chars: 0` is scoped to the hub config only; `plugins/mill/templates/mill-config.yaml` is not listed, but CLAUDE.md requires hub file and plugin template to stay in sync.
**Fix:** Add `plugins/mill/templates/mill-config.yaml` to the in-scope list for the `max_implementer_prompt_chars` default.

## Verdict

APPROVE
Four NOTEs, zero GAPs; core requirements and decisions are clear and source-verified.