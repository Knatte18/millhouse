MILL_REVIEW_BEGIN
# Review: Unhandled exceptions in mill-go orchestration components should degrade gracefully — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-16
```

## Findings

No findings. Verified all 8 cards across both batches against source:

- Card 1 (`_psmux.py:138-139`): `except FileNotFoundError: return []` added as sibling clause to `except PsmuxError as e:`, exactly as specified; no other function in the file touched.
- Card 2 (`test-psmux-driver.py:192-197`): new block mocks `_subprocess_util.run` with `FileNotFoundError`, asserts `result == []`, prints the exact required message.
- Card 3 (`_llm_claude.py:541-550`): new gate uses local `import _paths`/`import _config`, `_agent_dispatch` referenced from module scope (not re-imported), wrapped in `except (Exception, SystemExit): pass` with fall-through (not `return`) on resolution failure — matches the deliberate inverse-of-`_get_via_psmux_flag` contract called out in the card. Existing psmux-cleanup block below is untouched.
- Card 4 (`test-llm-claude.py`): K5(i)-(iv) correctly re-wrapped with the two-mock `load_config`/`resolve_git_root` pattern; K5(v)/(vi)/(vii) added exactly as specified, including the `SystemExit`-fall-through proof case. `import _paths` hoisted to module level (line 25) with no redundant local import remaining in Test 11.
- Card 5 (`mill-go/SKILL.md:184-195, 535-542`): both `cleanup_session` bash blocks now close with a bare `"`; no `|| true` remains anywhere in the file (confirmed via grep).
- Card 6 (`_daemon.py:141-153`): inner `try/except json.JSONDecodeError` wraps only the `json.loads` call, logs at `debug` with `len(msg_text)`, returns immediately; outer `except Exception as exc:` block (auth/server-error response + `error`-level log) untouched.
- Card 7 (`test-wiki-daemon.py:643-683`): blocks (w) and (x) added in the correct location with the exact recv-mocking and four-assertion pattern specified.
- Card 8 (`wiki/_client.py:630-651`): redundant bare-connect probe and outer `except OSError:` removed; replaced block is byte-for-byte the plan's proposed replacement; `import socket` retained (still used by `wait_for_socket_reachable`/`_is_stale`).

No out-of-plan files present; all files in "All Files Touched" are accounted for by a card. No shared-decision deviations. The intentional duplication of the dispatch-mode-resolution chain between `_get_via_psmux_flag()` and `cleanup_session()`'s new gate is explicitly mandated by Card 3 (the two have different error-handling contracts: return-False-on-error vs. fall-through-on-error), not an accidental reimplementation — not flagged.

## Verdict

APPROVE
Both batches match their plan cards precisely; tests cover happy/error paths; no out-of-plan files or shared-decision deviations.
MILL_REVIEW_END
