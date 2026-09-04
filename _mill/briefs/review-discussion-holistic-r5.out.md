MILL_REVIEW_BEGIN
# Review: millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (best-effort self-assessment)
reviewed_file: /home/knatte/Code/millhouse/wts/millpy-implement-fix-stuck-type-false-positives/_mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] self-resolved-dead-parent wrongly treated as a re-fire marker
**Section:** Decisions / `956-fresh-session-after-self-resolve`
**Issue:** The fresh-mint trigger set is `{self-resolved-verify-logic, self-resolved-dead-parent}`, but per `mill-go-base/SKILL.md:704-716` (and the identical pattern in `handoff.md:55-62`), `self-resolved-dead-parent` is appended during the *success*-report cleanliness-gate's parent-branch auto-rebind — processing continues in the same session/finalize flow, it never precedes a "re-fire the implementer fresh" step the way `self-resolved-verify-logic` does (`SKILL.md:924-925`, explicit "Then re-fire the implementer fresh for this batch"). Batch state stays `running` right after this marker is recorded, so a genuinely legitimate transient-retry re-fire immediately following a dead-parent rebind would be misclassified as a self-resolve-after-stuck event, forcing a needless fresh mint — reintroducing exactly the session-churn/double-commit regression (#625/#635/#643) the `_prepare_reuse_entry` heuristic exists to prevent.
**Fix:** Drop `self-resolved-dead-parent` from the trigger set (or cite an actual re-fire code path that follows it, if one exists elsewhere not yet read) — only `self-resolved-verify-logic` is documented as preceding a fresh re-dispatch.

### [NIT:decision] Heartbeat thread's log-file handle sharing left unspecified
**Section:** Decisions / `955-heartbeat-for-diagnosability`
**Issue:** `_worker_main` (`millpy-bg.py:34-89`) opens `log_path` once (`open(log_path, "w", ..., buffering=1)`) and passes that handle as `subprocess.run`'s `stdout`; the decision doesn't say whether the heartbeat thread writes through that same `log_f` handle or opens its own append handle, a distinction this codebase has hit real Windows file-locking bugs over before (per recent merged commit `1c61b831`).
**Fix:** State explicitly that the heartbeat thread reuses the existing `log_f` handle (matching the worker's only-one-open-handle pattern) rather than opening a second one.

## Verdict

REQUEST_CHANGES
#956's dead-parent trigger inclusion rests on a false premise about SKILL.md's documented re-fire flow.
MILL_REVIEW_END
