MILL_REVIEW_BEGIN
# Review: Unhandled exceptions in mill-go orchestration components should degrade gracefully — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-16
```

## Findings

### [BLOCKING] Card 3 gate `except Exception` misses SystemExit
**Location:** Batch 1, Card 3 (and Card 4 K5(vii))
**Issue:** `_paths.resolve_git_root(Path.cwd())` raises `SystemExit` (`_paths.py:130`, e.g. cwd outside a git worktree — the exact "resolution failure" the card names), but `SystemExit` subclasses `BaseException`, not `Exception`, so the card's prescribed `except Exception: pass` will NOT catch it — `cleanup_session` crashes instead of falling through, contradicting the task's graceful-degradation goal. The reference function `_get_via_psmux_flag` deliberately catches `except (Exception, SystemExit)` (`_llm_claude.py:114`); Card 3 drops `SystemExit`. Card 4's K5(vii) even mocks `resolve_git_root` with `side_effect=SystemExit(...)` expecting fall-through, so it would fail against Card 3 as written.
**Fix:** Change Card 3's gate wrapper to `except (Exception, SystemExit): pass` (mirroring `_get_via_psmux_flag`).

## Verdict

REQUEST_CHANGES
Card 3's `except Exception` cannot catch the `SystemExit` its own scenario and Card 4's test raise.
MILL_REVIEW_END
