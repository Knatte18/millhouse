# Discussion: Fix plan validator Moves-target gap, code-review backtick parser, and mill-start encoding crash

```yaml
task: Fix plan validator Moves-target gap, code-review backtick parser, and mill-start encoding crash
slug: mill-plan-and-start-gaps
status: discussing
parent: main
```

## Problem

Three independent, small documentation/code bugs were filed against mill-plan and mill-start tooling, all discovered during real task runs on the `loomyard` repo:

1. **#584 / #585 (duplicate, same fix) — `all-files-touched-mismatch` validator vs. docs mismatch.** `_plan_validate.py`'s `_check_all_files_touched_mismatch` (plugins/mill/scripts/_plan_validate.py:1144) requires the overview's `## All Files Touched` section to include `Moves:` **target** paths (it unions `Edits:` + `Creates:` + Move targets — see lines 1170-1182, which cite issue #494 and a "move-endpoint-accounting Shared Decision"). But `plugins/mill/templates/plan-overview.md` (line 76) and `plugins/mill/skills/mill-plan/SKILL.md`'s Step 1.5 fix-table row for `all-files-touched-mismatch` (line 133) both describe the required set as "union of every `Creates:` / `Edits:`" only — no mention of Moves targets. An orchestrator following the documented fix-table row literally will not add the Moves targets, the validator error persists, and the plan can hit the two-pass validator cap. This was hit twice independently (rename-heavy plans on two different branches).

2. **#580 — phantom ref tokens from prose backticks break holistic code review.** `_review_common.parse_batch_refs` (plugins/mill/scripts/_review_common.py:494) extracts ref tokens from `Context:`/`Edits:`/`Creates:`/`Deletes:` sub-bullet lines. For the multi-line bullet form, the sub-bullet loop (lines 533-542) runs `re.findall(r"`([^`]+)`", rest)` and `extend`s **every** backtick span found on the line — not just the path. A scope sub-bullet like `` - `cmd/lyx/main_test.go` (batch 3 routed `boardcli`'s dir through `paths.Resolve` ...) `` yields phantom tokens `boardcli` and `paths.Resolve` alongside the real path. `resolve_ref_paths` then hard-fails on the phantom token (not on disk, not in creates/deletes union), producing a top-level `verdict: ERROR` that blocks the **entire** holistic code review — not just a finding, a full review outage.

   **Reconciliation with plan-validate Check 6:** `_plan_validate.py`'s `_check_ref_not_backtick_path` (`reads-not-backtick-path`, lines 1054-1110) already rejects exactly this sub-bullet shape — `len(bt_matches) > 1` on a sub-bullet line raises "sub-bullet contains multiple backtick paths". This check, however, runs **once**, at `--stage prepare` / plan-review time, before a batch is approved and implemented. `_mill/plan/*.md` batch files remain mutable working state on the task branch after that gate — the #580 repro explicitly notes the offending bullet was "a verify-backstop scope note the implementer added," i.e. appended *after* the batch passed Check 6 and during/after implementation. Code review reads the batch files' current on-disk content at review time, not a frozen post-validation snapshot, so a phantom-backtick sub-bullet introduced post-approval reaches `parse_batch_refs` unchecked by Check 6. Hardening `parse_batch_refs` is therefore deliberate defense-in-depth on the consuming side for a real, already-demonstrated escape path — not a workaround masking a validator hole. Check 6 remains correct and is not changed by this task; no new re-validation-on-every-code-review mechanism is introduced (that would be new scope, not a bug fix).

3. **#583 — `mill-start` Phase: Select snippet crashes on Windows cp1252 consoles.** The documented `get_task` Python snippet (plugins/mill/skills/mill-start/SKILL.md, Phase: Select, lines 72-87) prints `task.get('body', '')` and `task.get('brief', '')` without forcing UTF-8 output. On a Windows console using the cp1252 codepage, any non-cp1252 character in the task body (e.g. `→`, common in rename/refactor task titles) raises `UnicodeEncodeError` and the subprocess exits 1 immediately after the `STATUS:` line — silently breaking the autonomous/agent dispatch path, since there's no operator watching to notice the truncated output.

**Why now:** all three were filed today (2026-06-30) from real task runs on `loomyard`, each with a clean repro. They are small, independent, well-bounded bug fixes — no design exploration needed beyond confirming the correct fix locus for each (doc vs. code).

## Scope

**In:**
- Update `plugins/mill/templates/plan-overview.md`'s `## All Files Touched` description (line 76) to state the union includes Moves **targets** (not sources).
- Update `plugins/mill/skills/mill-plan/SKILL.md`'s Step 1.5 fix-table row for `all-files-touched-mismatch` (line 133) to match — instruct fixing the overview to the union of Edits + Creates + Move targets.
- Fix `_review_common.parse_batch_refs`'s multi-line sub-bullet extraction (plugins/mill/scripts/_review_common.py, the `j` loop around line 533-542) to take only the **leading** backtick token per sub-bullet line, discarding any further backtick-wrapped tokens on the same line (prose parentheticals).
- Add/extend a unit test in `plugins/mill/unit_tests/test-review-common.py` pinning the phantom-token regression: a sub-bullet line with a real path token followed by parenthetical prose containing extra backticks must yield only the leading path.
- Add/extend a test for `_check_ref_not_backtick_path` (Check 6, `reads-not-backtick-path`) asserting the same repro sub-bullet shape is independently flagged at plan-validate time, documenting the two parsers as intentionally layered defenses rather than leaving the relationship implicit.
- Fix `plugins/mill/skills/mill-start/SKILL.md`'s Phase: Select `get_task` Bash snippet to prepend `PYTHONIOENCODING=utf-8` to the invocation, preventing `UnicodeEncodeError` on non-cp1252 task body/brief content.
- Add a short parenthetical to Phase: Explore's prose pointing back at the UTF-8-safe invocation, so a reader reconstructing the explore-phase re-call doesn't drop the env prefix.
- Re-run the full unit test suite (`run-all.py`) to confirm no regressions across all three changes.

**Out:**
- No change to `_check_all_files_touched_mismatch`'s validator logic itself — its behavior (requiring Move targets) is the deliberate, already-shipped design from issue #494; only the docs that describe it are wrong.
- No change to `parse_batch_refs`'s single-line inline form (`- **Edits:** \`a\`, \`b\``) — multiple comma/backtick-separated tokens on one line is an established, tested, legitimate convention, untouched by this bug and outside the #580 repro.
- No change to `parse_moves` or `_RE_MOVE_PAIR` — Moves: bullets are already excluded from `parse_batch_refs` by header-type dispatch; unaffected by this fix.
- No broader audit of other skills for the same unguarded-print anti-pattern — grepped `plugins/mill/skills/` for `print(task.get('brief'|'body'` and confirmed `mill-start/SKILL.md` is the only hit. Scope stays exactly as filed in #583.
- No change to `sys.stdout.reconfigure` approach — using the `PYTHONIOENCODING=utf-8` env-var prefix instead, matching the existing repo-wide convention in `_subprocess_util.py`.

## Decisions

### moves-target-docs-not-validator

- Decision: Fix #584/#585 by updating documentation (template + SKILL fix-table) to state the All Files Touched union includes Move targets. Do not touch the validator.
- Rationale: `_check_all_files_touched_mismatch` already implements Move-target inclusion intentionally — the code explicitly cites issue #494 and a "move-endpoint-accounting Shared Decision" (git blame: commit `2eed551c`, "Add first-class Moves/Renames field to plan cards for rename-heavy batches"). The bug is that the docs never caught up to that decision, not that the validator is wrong.
- Rejected: Changing the validator to exclude Move targets — would silently regress the #494 decision and reopen the original problem it solved (Move targets behave like Creates: new files appear post-rename and reviewers need them in All Files Touched).

### backtick-leading-token-only

- Decision: Fix #580 by restricting the multi-line sub-bullet extraction in `parse_batch_refs` to the leading backtick token per line. Leave the single-line inline form untouched.
- Rationale: The multi-line sub-bullet form is documented and tested as one-path-per-bullet (`test-review-common.py`'s "multi-line bullet form returns both paths" test uses exactly one backtick token per sub-bullet line). The existing Moves-exclusion regression test's comment already states the implicit design intent: sub-bullets are expected to carry ≤1 backtick path ("rejects >1 backtick per sub-bullet when processed by parse_batch_refs"). Taking the leading token only formalizes that intent and eliminates the phantom-token failure mode without affecting any passing test. This is defense-in-depth alongside (not a replacement for) plan-validate Check 6 `_check_ref_not_backtick_path`, which already rejects the same multi-backtick sub-bullet shape at `--stage prepare` time but cannot catch edits made to batch files after that one-time gate (see Problem #2's reconciliation note) — `parse_batch_refs` is the only check still in a position to act once a batch file has been edited post-approval.
- Rejected: Filtering to "path-like" tokens (containing `/` or a known extension) — more fragile (extension allowlist drifts, bare filenames like `Makefile` or `Dockerfile` would need special-casing) and not needed since the simpler leading-token rule already satisfies every known case, including the bug repro.

### pythonioencoding-prefix

- Decision: Fix #583 by prepending `PYTHONIOENCODING=utf-8` to the documented Bash invocation in Phase: Select, rather than editing the `-c` script body.
- Rationale: Matches the established repo-wide convention — `_subprocess_util.py` always injects `PYTHONIOENCODING=utf-8` into the child environment for exactly this class of problem (lines 103, 323). A one-line env-var prefix is also the minimal-diff fix consistent with the documented script being copy-pasted verbatim by an orchestrator.
- Rejected: `sys.stdout.reconfigure(encoding='utf-8')` inside the snippet — works but adds a line to a script meant to stay short and copy-pasteable; the env-var approach is simpler and matches existing precedent.

## Technical context

- `_plan_validate.py:_check_all_files_touched_mismatch` (line 1144) is the validator; `compute_moves_union` (referenced line 1181) is the existing helper that already separates Move sources from targets — no new helper needed, this confirms the validator's behavior is correct and only docs need to change.
- `plugins/mill/templates/plan-overview.md` line 76 is the only line needing a wording change in that file (the section heading and bullet-list format stay the same).
- `plugins/mill/skills/mill-plan/SKILL.md` line 133 is the single fix-table row to update.
- `_review_common.py:494-548` is `parse_batch_refs`; the bug is localized to the `while j < len(lines)` sub-bullet loop, specifically the `bt = re.findall(...)` / `tokens.extend(bt)` pair (lines 539-541). Changing this to take only the first match (e.g. `bt = re.findall(...)`, then `if bt: tokens.append(bt[0])`) is sufficient — `_RE_REFS_SUB = re.compile(r"^\s+-\s*(.+)$")` already captures the full sub-bullet line into `rest`, unchanged.
- Existing regression test at `test-review-common.py:3260` ("parse_batch_refs must NOT return tokens from Moves: bullets") already documents the design expectation that sub-bullets carry ≤1 backtick path; the fix is consistent with, not contradictory to, that comment.
- `plugins/mill/skills/mill-start/SKILL.md` Phase: Select snippet is at lines 68-89; Phase: Explore prose (no code block) is at lines 95-97.
- Existing convention for forcing UTF-8 subprocess I/O lives in `plugins/mill/scripts/_subprocess_util.py` (`child_env["PYTHONIOENCODING"] = "utf-8"`, lines 103 and 323) — the fix mirrors this pattern, applied at the Bash-invocation layer instead of inside `_subprocess_util` since this call isn't routed through that helper.

## Testing

- **`_check_all_files_touched_mismatch` / templates:** doc-only change, no new automated test — verify by inspection that the updated template/SKILL wording matches the validator's actual `cards_set` computation (Edits + Creates + Move targets).
- **`parse_batch_refs` (TDD candidate):** add a unit test in `test-review-common.py` reproducing the #580 repro exactly — a sub-bullet line with a leading path token followed by a parenthetical containing extra backtick-wrapped non-path text — asserting only the leading token is returned. Run alongside the existing sub-bullet, inline, and Moves-exclusion tests to confirm no regression (all must still pass unchanged: "multi-line bullet form returns both paths", "single-line form returns both paths", "mixed single-line and multi-line fields", Moves-exclusion regression).
- **Cross-check with plan-validate Check 6 (layered-defense note):** also add or extend a `_check_ref_not_backtick_path` test in `test-plan-validate.py` (or wherever its existing tests live) asserting the *same* repro sub-bullet is flagged with a `reads-not-backtick-path` error at plan-validate time. This documents explicitly, in the test suite, that the two parsers are intentionally layered — Check 6 catches the shape at first approval, `parse_batch_refs` catches it again if the batch file is edited afterward — rather than leaving that relationship implicit.
- **mill-start UTF-8 fix:** documentation-only change (no executable script under test in the unit suite covers SKILL.md prose); verification is inspection that the invocation line now reads `PYTHONIOENCODING=utf-8 PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "..."` and that Phase: Explore's prose references the same invocation.
- Run the full unit suite (`run-all.py` per `mill:python-testing` conventions) after all three changes to confirm zero regressions repo-wide.

## Q&A log

- **Q:** Issue #584/#585 (Moves-target gap) — fix via docs only vs. change the validator to exclude Moves targets? **A:** [auto-pick] docs only (update template + SKILL fix-table). **Why:** the validator's Move-target inclusion is a deliberate prior decision (cites issue #494 / "move-endpoint-accounting Shared Decision", shipped in commit 2eed551c); the docs never caught up.
- **Q:** Issue #580 (phantom backtick refs) — fix strategy for the sub-bullet extraction: leading-token-only vs. path-like-token filtering vs. other? **A:** [auto-pick] leading token only. **Why:** matches the established one-path-per-sub-bullet convention already implied by an existing regression test's comment; simpler than an extension allowlist and has zero false negatives against current tests.
- **Q:** Should the leading-token restriction also apply to the single-line inline form? **A:** [auto-pick] No, leave inline form untouched. **Why:** an existing passing unit test explicitly covers multi-token inline lines as legitimate; not implicated in the #580 repro.
- **Q:** Issue #583 (cp1252 crash) — fix via `PYTHONIOENCODING=utf-8` env prefix vs. `sys.stdout.reconfigure` inside the snippet? **A:** [auto-pick] env-var prefix. **Why:** matches the existing repo-wide convention in `_subprocess_util.py`; minimal one-line diff.
- **Q:** Should the #583 fix touch only the Phase: Select code block, or also the Phase: Explore prose? **A:** [auto-pick] both. **Why:** Phase: Explore re-describes the same call in prose; a parenthetical cross-reference prevents a reader from dropping the env prefix when reconstructing it.
