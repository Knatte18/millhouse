MILL_REVIEW_BEGIN
# Review: mill-go2: opt-in skill scaffold cloned from mill-go (no fork yet)

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:consistency] "no hook anywhere" test spec contradicts byte-for-byte move
**Section:** Decision `override-point-terminology` + Testing "TDD candidate" scenario ("The word `hook` does not appear in any of the three files"). **Issue:** `mill-go/SKILL.md` already contains the literal word "hook" twice today — line 500 ("At the hook point, run all of:") and line 554 ("this mode has no separate finalize call to hook before") — both incidental English usage unrelated to override points. Technical Context states this whole file "moves byte-for-byte" to the base, so the literal no-`hook`-anywhere test will fail on day one unless someone silently rewords source text the discussion elsewhere guarantees is untouched. **Fix:** Either scope the test to the override-point section headers/directives only, or explicitly call out these two pre-existing occurrences as an exception to "byte-for-byte."

### [BLOCKING:design] Parameterization enumeration is undercounted/self-inconsistent
**Section:** Technical Context, "What is parameterized in the base." **Issue:** Grep against `mill-go/SKILL.md` finds 26 `commit -m "mill-go: ...` literals, not the 20 claimed (missing lines 1232, 1234, 1240, 1284, 1306, 1360); the `_notify.notify("mill-go...` line list is headed "7" but enumerates 8 line numbers (774/839/876/1162/1171/1182/1184/1371), and neither interpretation (8 call sites, or 5 distinct event names) equals 7. **Fix:** Regenerate the parameterization list via a scripted grep rather than manual enumeration before the plan writer uses it as the literal work inventory — an undercount here means mill-go2 silently keeps `mill-go:`-prefixed commits/notify events at the missed sites, defeating `variant-label-in-logs`.

### [BLOCKING:decision] Disposition of pre-`## Entry` preamble (title/banner/role text) unstated
**Section:** Technical Context, "The file being split" + Scope's "~25 lines" thin-variant description. **Issue:** The enumerated "Top-level sections" that move to the base start at `## Entry`; lines 1-16 (the `# mill-go` title, the "> Wiki access: never `cd .wiki/`" banner, and the "You are the **Builder**" role paragraph) are never assigned to either the base or the thin variant. This matters concretely: line 8's banner is the *only* line in the whole file matching `_WIKI_CWD_PATTERNS`, which is why `mill-go/SKILL.md` is in `test-guards.py`'s `_WIKI_CWD_ALLOWLIST` today — and the Technical Context itself hedges "whether the mill-go entry is then removed depends on whether any such pattern remains in the thin variant file — it should not" without stating where that banner text actually lives post-split. **Fix:** State explicitly whether the pre-Entry preamble moves to the base (resolving the allowlist question) or is reproduced per thin variant.

## Verdict

REQUEST_CHANGES
Fix the self-contradicting hook/enumeration counts and the unstated preamble disposition before planning.
MILL_REVIEW_END
