# Review: V3 wiki adoption follow-up bugs

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-27
```

## Findings

### [GAP] #382 health-exchange timeout mechanism unspecified
**Section:** Decisions § #382 / Q&A log
**Issue:** Q&A decides the health exchange must use a 1.0s timeout, but the pseudocode calls `_connect_send_recv(host, port, req)` which has a hardcoded 10.0s socket timeout (verified: `_client.py:537`). The discussion gives no guidance on whether to add an optional `timeout` parameter to `_connect_send_recv`, inline a custom socket, or some other approach — leaving the plan writer unable to write concrete implementation steps.
**Fix:** Specify the implementation mechanism (e.g., "add an optional `timeout` parameter to `_connect_send_recv` defaulting to 10.0, pass 1.0 from the health-exchange call site in `_ensure_daemon`").

### [NOTE] #366 chmod value inconsistent between prose and code snippet
**Section:** Decisions § #366 / Technical Context § #366
**Issue:** The Decision text says `os.chmod(path, 0o777)`; the Technical Context code snippet says `os.chmod(path, stat.S_IWRITE)`. These are different values (`stat.S_IWRITE` = `0o200`); an implementer will have to pick one.
**Fix:** Resolve to a single value (on Windows clearing the read-only bit, `stat.S_IWRITE` is sufficient and the conventional choice; `0o777` is over-broad but harmless on Windows).

### [NOTE] #382 spawn-loop bare TCP not explicitly exempted
**Section:** Technical Context § _ensure_daemon flow (#382)
**Issue:** The post-spawn polling loop (`_client.py:476–488`) also uses a bare `socket.create_connection` rather than an `OP_HEALTH` exchange. The discussion explicitly exempts `_is_stale` but is silent on the spawn loop. The risk is lower there (freshly spawned daemon owns the state file) but the omission leaves ambiguity about whether this was intentional.
**Fix:** Add one sentence: "The spawn-loop TCP connect (lines 476–488) is also exempt — we spawned the daemon and it writes the state file, so the port is ours."

## Verdict

GAPS_FOUND
One GAP: health-exchange 1.0s timeout mechanism unspecified given `_connect_send_recv` hardcodes 10.0s.