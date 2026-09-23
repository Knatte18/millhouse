MILL_REVIEW_BEGIN
# Review: mill-setup/wiki/docs/build-env: misc small bugs, round 3

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-23
```

## Findings

### [BLOCKING:design] json.dumps() fix trades an occasional bug for a guaranteed one
**Section:** Decisions > 1113-investigation-in-plan
**Issue:** `mill-triage-to-tasks/SKILL.md` Step 5's `python -c "..."` block is itself one bash double-quoted string end-to-end (the fenced command opens with `"$MILL_PYTHON" -c "` and closes with a bare `"` after the Python source). The decision's fix — substitute `json.dumps(title)`'s literal output for `'<title>'` — inserts real, unescaped `"` characters into that outer bash string on every call (json.dumps always double-quotes), terminating the bash string early and exposing the rest of the line to unquoted-bash interpretation (word-splitting, `$()`/backtick command substitution). The apostrophe bug it replaces only fired conditionally, on apostrophe-containing titles, and broke Python parsing, not bash; this fix fires unconditionally and breaks bash, which is a command-injection surface for adversarial title text, not just a syntax error.
**Fix:** Either bash-escape every `"` and `\` the json.dumps() output contains before inline substitution, or stop embedding dynamic text inside a bash-double-quoted `python -c` source string entirely (env var or stdin read, never printed into the source).

## Verdict
REQUEST_CHANGES
The chosen #1113 fix mechanism introduces a worse, always-triggered bash-quoting break; the decision needs to address the outer bash-quote layer.
MILL_REVIEW_END
