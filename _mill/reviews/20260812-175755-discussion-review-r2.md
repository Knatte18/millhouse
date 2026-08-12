MILL_REVIEW_BEGIN
# Review: CLAUDE_PLUGIN_ROOT environment variable not exported to Bash tool

```yaml
duration_s: 128.0
verdict: APPROVE
reviewer_model: sonnet
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [NIT:consistency] Field-report platform left unspecified vs. Windows-only prior doc
**Section:** Problem
**Issue:** `cli/SKILL.md:40` (verified) flags `$CLAUDE_PLUGIN_ROOT` empty in Bash subshell specifically "on Windows," but the Problem section never states which OS #811/#813 ran on, and this session's Linux repro showed the var populated correctly.
**Fix:** Note the reporters' platform if known, or explicitly state it's unconfirmed — doesn't block since the chosen fix (sys.path scan) is platform-agnostic regardless.

### [NIT:design] Scan-collision test case not enumerated
**Section:** Testing
**Issue:** TDD candidate (3) tests a third-party path prepended *ahead of* the real `scripts` entry being found by the scan, but no candidate tests a false-positive: an unrelated, earlier `scripts`-named directory being matched instead of the plugin's own.
**Fix:** Add a TDD candidate asserting first-match-wins semantics are documented/acceptable, or confirm (via sys.path ordering) this can't realistically occur for `-c` invocations.

## Verdict

APPROVE
Round-1's factual flaw is corrected and verified; scope, decisions, and technical claims check out against source.
MILL_REVIEW_END
