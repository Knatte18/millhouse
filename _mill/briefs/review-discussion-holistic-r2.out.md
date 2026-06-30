I have verified all load-bearing claims against source. Every ALLOWLIST entry is confirmed an identifier-tail match (`status_path.exists()`, `env_block.get(`, `ref_ts_str.strip(`, `file_path.stat()`, etc.) — none is a standalone `_module.func(`, so emptying ALLOWLIST is safe and Card 1 stays green on `main`. The regex, mill-go:738, mill-start Phase boundaries, and `get_task` returning `body`/`brief` all check out.

MILL_REVIEW_BEGIN
# Review: Fix drift-guard false positive and mill-start missing task body/brief

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-30
```

## Findings

### [NOTE] Explore data flow: re-fetch vs reuse Select output
**Section:** Decisions / millstart-fetch-body-brief
**Issue:** Each bash call is a fresh subprocess, so the `task` variable from Phase: Select does not persist; the discussion does not state whether Phase: Explore re-calls `get_task` or consumes Select's printed `body`/`brief` from scrollback.
**Fix:** Have the plan name the source of truth for Explore (re-fetch vs reuse the Select printout) so the data flow is unambiguous.

### [NOTE] Select printout delimiting vs status gate parse
**Section:** Decisions / millstart-fetch-body-brief
**Issue:** Printing a multi-section `body` (the ~6KB harden-path-invariant case) right after `status` in the Select snippet can interleave lines and complicate the existing "status must be active" single-line parse.
**Fix:** Specify labeled delimiters (or print status on its own first line) so the status gate stays unambiguous when `body` spans many lines.

## Verdict

APPROVE
Round-1 substring/lock GAP is resolved; claims verify against source; only minor implementation NOTEs remain.
MILL_REVIEW_END
