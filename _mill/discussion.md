# Discussion: Silence verbose review log lines cluttering orchestrator output

```yaml
task: Silence verbose review log lines cluttering orchestrator output
slug: review-log-noise
status: discussing
parent: main
```

## Problem

When mill-go (or mill-start/mill-plan) polls a bg-review log and the background process exits, the orchestrator reads back far more than the single JSON verdict line it needs. Three sources compound this noise:

1. **Poll extraction**: The SKILL.md wording ("read the log and extract the JSON summary line") is vague enough that the orchestrator LLM uses `tail -30` or `cat <log-path>` after detecting `[mill-bg] EXIT`, dumping up to 30 lines of log context into its window. The fix is to instruct `grep '^{' <log-path> | tail -1` — one line in, one line out.

2. **Unconditional info prints in `_llm_claude.py` and review backends**: `_llm_claude` emits "starting..." before every LLM call and "returned N chars in Xs" after it. `_review_code` emits slug/round/scope on entry and "wrote <file> verdict=<v>" on completion. `_review_discussion` has identical entry and completion prints. Task 64 silenced `_subprocess_util`, but not these modules. Every review invocation appends 2–4 noisy lines to the bg log.

3. **Psmux-keepalive branch**: Was spawned from task 58's merge base and lacked task 64's `_subprocess_util` fix. This has since been resolved — the branch was squash-merged to main (commit `ab339f9`) and the merge includes task 64 (`9b6dfae`) in its ancestry. No action needed.

## Scope

**In:**
- `plugins/mill/scripts/_llm_claude.py` — remove the unconditional "starting..." and "returned N chars" print lines (two code paths: psmux and non-psmux)
- `plugins/mill/scripts/_review_code.py` — remove the `[_review_code] slug= round= scope=` entry print and the `[_review_code] wrote ... verdict=...` completion print
- `plugins/mill/scripts/_review_discussion.py` — remove the `[_review_discussion] slug= round=` entry print and the `[_review_discussion] wrote ... verdict=...` completion print (same pattern as _review_code)
- `plugins/mill/skills/mill-go/SKILL.md` — update all 5 poll-extraction instructions to specify `grep '^{' <log-path> | tail -1`
- `plugins/mill/skills/mill-start/SKILL.md` — update 2 poll-extraction instructions similarly
- `plugins/mill/skills/mill-plan/SKILL.md` — update 3 poll-extraction instructions similarly

**Out:**
- `_review_plan.py` log lines — not in task scope; limit to what the task description explicitly calls out plus `_review_discussion` by direct analogy
- Error, warning, and rate-limit prints in any module — keep all; only unconditional informational prints are removed
- `_subprocess_util.py` — already fixed in task 64
- Psmux-keepalive rebase — already resolved by merge
- Logging framework / debug-flag infrastructure — simple line removal, no new abstraction needed

## Decisions

### include-review-discussion

- Decision: Include `_review_discussion.py` in the noise cleanup alongside `_review_code.py`.
- Rationale: It has identical entry and completion prints that appear in the bg-log that mill-start polls. Excluding it leaves the same noise for every discussion review.
- Rejected: Limiting strictly to the two modules named in the task description (`_llm_claude`, `_review_code`).

### exclude-review-plan

- Decision: Do not clean up `_review_plan.py` log lines in this task.
- Rationale: YAGNI — the task description is explicit about scope; `_review_plan`'s lines ("running holistic review", rounds=0 stubs) are one-shot per review rather than per-LLM-call and represent less volume.
- Rejected: Cleaning up all review modules for consistency.

### skill-extraction-command

- Decision: Use bash `grep '^{' <log-path> | tail -1` to extract the JSON line in SKILL.md.
- Rationale: SKILL.md files already use bash-style shell syntax; the Bash tool is available to every orchestrator session. The pattern is unambiguous: JSON objects start with `{`, and `tail -1` is defensive for the (non-occurring) case of multiple matches.
- Rejected: PowerShell `Select-String` — inconsistent with existing SKILL.md style.

### update-all-three-skills

- Decision: Update all three SKILL.md files — mill-go, mill-start, and mill-plan.
- Rationale: All three have the same vague poll-extraction wording and the same noise problem. Fixing only mill-go would leave the problem active for plan-writing and discussion-review sessions.
- Rejected: Updating only mill-go.

### how-to-silence

- Decision: Remove the print lines entirely. No debug flag, no log level.
- Rationale: The model set by `_subprocess_util.py` in task 64: only emit to stderr on error. The "starting" and "returned N chars" lines are pure progress noise with no diagnostic value that error lines don't already cover.
- Rejected: Adding a debug/verbose flag (adds complexity; debug mode would still flood the log since reviewers run as subprocesses).

## Technical context

### `_llm_claude.py` — lines to remove

Two code paths both start the same "starting..." print (line 300) and each have their own "returned N chars" print:

- **Print to remove (both paths share this):** line 299–302 — `[_llm_claude] claude {model} ({mode_label}{mode_suffix}){sess_label} starting...`
- **Psmux path:** lines 340–344 — `[_llm_claude] claude {model} returned {len(text)} chars in {dt:.1f}s session={sid_log}`
- **Non-psmux path:** lines 395–399 — same format

Lines to **keep** (error/diagnostic only):
- Line 235–237: warning for unparseable stream-json line
- Lines 371–373: fast-fail retry log (fires only on error)
- Lines 544–546: cleanup_session killed psmux session (fires only when a session exists and is killed)

### `_review_code.py` — lines to remove

- Lines 217–220: `[_review_code] slug={slug!r} round={round_n} scope={scope_label}` — fires on every review entry
- Lines 444–447: `[_review_code] wrote {path.name} verdict={verdict}` — fires on every review completion

Lines to **keep**:
- Line 203 (rounds=0 disabled stub): fires only when review is disabled
- Lines 242–247 (warning: start_sha): fires only when sha is missing or unreadable
- Lines 271–275 (warning: no source files): fires only when scope resolves empty
- Line 387 (NEED_CONTEXT retry): fires only on the special retry path
- Line 465 (parse_verdict failed): error path

### `_review_discussion.py` — lines to remove

- Lines 81–84: `[_review_discussion] slug={slug!r} round={round_n}` — fires on every review entry
- Lines 168–171: `[_review_discussion] wrote {review_file.name} verdict={verdict}` — fires on every review completion

Lines to **keep**:
- Lines 65–68 (rounds=0 disabled): fires only when review is disabled

### SKILL.md — poll-extraction pattern

Current wording (varies slightly across files):
> "Once it does, read the log and extract the JSON summary line (the last non-empty, non-sentinel line in the log)."

Replacement:
> "Once it does, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line."

This covers all occurrences. The `<log-path>` placeholder in each file is already an absolute path variable (e.g., `<abs-path>` from the `pid=<N> log=<abs-path>` return). Mill-plan's SKILL.md uses slightly different wording in its occurrences — update all to the same grep pattern.

**All occurrences to update:**
- `plugins/mill/skills/mill-go/SKILL.md` lines 179, 236, 253, 270, 454
- `plugins/mill/skills/mill-start/SKILL.md` lines 120, 136
- `plugins/mill/skills/mill-plan/SKILL.md` lines 98, 133, 155

Note: some occurrences omit the parenthetical "(the last non-empty, non-sentinel line in the log)" — standardize all to the grep form; drop the parenthetical entirely.

## Testing

No existing unit tests assert on the stderr lines being removed (tests use `sys.stderr` for FAIL output only; they do not capture the modules' own stderr). No test changes are needed.

After implementing:
1. Run `uv run --project plugins/mill python unit_tests/run-all.py` from the hub worktree to confirm nothing broke.
2. Spot-check one SKILL.md occurrence is updated correctly per file (visual inspection).

The SKILL.md extraction change is behavioral (instructs the LLM) and is not unit-testable; correctness is verified by reading the changed text.

## Q&A log

- **Q:** Should `_review_discussion.py`'s entry and completion log lines be silenced alongside `_review_code.py`? **A:** [auto-pick] Yes, include them. **Why:** Same pattern, same bg-log context (mill-start polls), same fix. Excluding would leave identical noise for discussion reviews.
- **Q:** Should `_review_plan.py`'s log lines also be silenced? **A:** [auto-pick] No, limit scope to what the task explicitly identifies (_llm_claude, _review_code) plus _review_discussion by analogy. **Why:** YAGNI; _review_plan lines are one-shot per review, less volume; task description doesn't call them out.
- **Q:** What command for SKILL.md JSON extraction: bash `grep '^{' | tail -1` or PowerShell? **A:** [auto-pick] Bash `grep '^{' <log-path> | tail -1`. **Why:** Consistent with existing SKILL.md bash-style syntax; Bash tool is available to every orchestrator.
- **Q:** Update all three SKILL.md files or just mill-go? **A:** [auto-pick] All three (mill-go, mill-start, mill-plan). **Why:** All share the same vague extraction wording and the same noise problem.
