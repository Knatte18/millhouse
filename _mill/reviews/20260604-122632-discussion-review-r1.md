Review: millpy-bg-and-implement-fixes

  verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file:_mill/discussion.md
  date: 2026-06-04

  Findings

  [NOTE] Staged files left uncommitted when commit is skipped

  Section: § Skip duplicate "start batch" commit on re-fire (#412)
  Issue: The decision says "skip the commit+push step", but git add (staging status.md + snapshot) runs unconditionally before the check. On re-fire the skip leaves two staged-but-uncommitted files in
  the working tree when the implementer session starts.
  Fix: Clarify whether git add is also skipped on re-fire, or explicitly state that staged files are intentionally left for the implementer's first commit.

  [NOTE] start_sha = None unguarded in millpy-fix.py commits_made path

  Section: § commits_made in stuck JSON — Technical context: millpy-fix.py
  Issue: millpy-fix.py line 281 assigns start_sha = None when git rev-parse HEAD returns non-zero; git rev-list --count None..HEAD would then fail, potentially suppressing the stuck JSON entirely.
  Fix: Specify that commits_made should default to 0 (or be omitted) when start_sha is None, rather than letting git rev-list raise.

  Verdict

  APPROVE
  Two implementation-detail notes; no blocking gaps; plan writing can proceed.