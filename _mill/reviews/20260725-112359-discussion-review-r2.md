MILL_REVIEW_BEGIN
# Review: Wiki daemon error-log leak and stale plugin-cache config validation produce misleading noise

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

## Findings

### [GAP] load_config wrapper's missing-source check mechanism unspecified
**Section:** Decisions > review-common-load-config-dedup / Technical context (`_review_common.py:1842-1912`)
**Issue:** `_config.load_config` never raises and always returns a dict — even `{}` for a legitimately-present-but-empty template/config (verified: `yaml.safe_load(...) or {}` at `_config.py:215`, no signal of "source found" is returned). The decision commits to preserving "raise `ReviewError` when neither the plugin template nor a repo-layer config exists at all" but doesn't say how the wrapper determines that post-delegation; Technical context only spells out the analogous peek for the stale-`review:`-key check, not this one.
**Fix:** State explicitly that the wrapper re-checks existence itself via the already-imported `resolve_plugin_template_path`/`resolve_repo_config_path` (both still imported at `_review_common.py:71-72`, unused once the duplicate merge logic is deleted) rather than inferring "missing" from an empty return dict — the latter would misfire on legitimately-empty-but-present sources.

### [GAP] daemon-logger-consolidation injection mechanism left as an open either/or
**Section:** Decisions > daemon-logger-consolidation
**Issue:** Decision text says `DaemonBase` "should accept a logger (or a logger-name hook)" — two structurally different options, neither chosen, and no "Rejected" entry weighs them (inconsistent with every other decision in this doc). Verified via `wiki/_server.py:58-85`: `WikiServer.__init__` calls `super().__init__("wiki", ...)` *before* building its own `"wiki-server"` logger/handler — injecting an actual `Logger` object would require reordering that constructor, whereas passing just the logger name (e.g. `super().__init__("wiki-server", ...)`, reusing the existing `name` param) works unmodified today because `logging.getLogger(name)` returns the same process-wide singleton regardless of configuration order, and nothing else references `getLogger("wiki")` by name (grep confirmed, repo-wide).
**Fix:** Pick one mechanism now; note the minimal option (rename the literal passed to the existing `name` param, no `DaemonBase.__init__` signature change) as a candidate/rejected-or-accepted alternative.

### [NOTE] Windows stdio-redirection propagation through `cmd /c start` not verified
**Section:** Decisions > daemon-stdio-redirection / Technical context (`wiki/_client.py:666-694`)
**Issue:** The POSIX branch's `subprocess.Popen(cmd, stdout=DEVNULL, ...)` unambiguously redirects the daemon. The Windows branch wraps the real command in `cmd /c start "" /B /MIN <cmd>`; whether `stdout=`/`stderr=DEVNULL` on the outer `Popen` call actually reaches the process `start` launches (vs. being reset by `start`'s own console/handle handling) isn't confirmed by any repro, unlike the exception-classification decision which explicitly flags its own unverified repro.
**Fix:** Note this as an assumption to verify manually on Windows post-implementation, or downgrade the Testing plan's Windows-branch assertion to "kwargs passed" (already what's proposed) without claiming behavior parity with POSIX.

### [NOTE] `run()`'s root `logging.basicConfig` call becomes vestigial post-consolidation, disposition unaddressed
**Section:** Decisions > daemon-logger-consolidation / Technical context (`_daemon.py:62-65`)
**Issue:** `DaemonBase.run()` unconditionally calls `logging.basicConfig(...)` when root has no handlers. Once the connection-level logger is consolidated onto `"wiki-server"`'s `propagate=False` file handler, this call no longer affects anything reachable — but the decision doesn't say whether to remove it or keep it as a fallback for a future `DaemonBase` subclass that doesn't wire in a dedicated logger.
**Fix:** State whether `basicConfig` stays (as a default for future non-wiki subclasses) or is deleted as dead code.

## Verdict

GAPS_FOUND
Two unresolved implementation-mechanism gaps in the config-dedup and logger-consolidation decisions risk incorrect or inconsistent implementation.
MILL_REVIEW_END
