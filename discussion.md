# Discussion: 19 (A) — mill-go + scripts infra fixes

```yaml
task: 19 (A) — mill-go + scripts infra fixes
slug: mill-go-infra-fixes
status: discussing
parent: main
```

## Problem

Five independently observed production failures in the mill-go pipeline and supporting infrastructure:

**(A)** No clean pause path in mill-go — if the user interrupts mid-run, `_builder_lock` stays held. A fresh `/mill-go` hits `LockBusy`. The Python-only lock API also has no CLI wrapper, making manual recovery error-prone.

**(B)** Sonnet 4.6 occasionally wraps its final JSON report in a `\`\`\`json ... \`\`\`` fenced block. `millpy-implement.py`'s `_forward_output()` scans lines in reverse for a raw JSON line — if the closing fence is the last non-empty line, the scan currently skips it by accident and finds the JSON second. This is fragile and has caused two false-positive-stuck events on real tasks.

**(C)** mill-go approves a batch and dispatches code review with no `git status` cleanliness check. An implementer that commits partially lets uncommitted edits leak into the next batch's diff, where they surface as BLOCKING review findings on the wrong batch, exhausting review rounds unnecessarily.

**(D)** mill-cleanup treats `phase: done` as safe to remove, but `done` is set by mill-go at implementation end — mill-merge hasn't run yet. `dispatch-cli-and-resume` had 14 unmerged commits and `status.md: done`; cleanup stripped its junctions before the permission-denied guard stopped deletion by accident.

**(E)** CLAUDE.md line 103 claims "PYTHONPATH is set globally as a Windows user environment variable by mill-setup Phase 4.7; CC inherits it automatically — no per-session export needed." At least two sessions in different repos failed with `ModuleNotFoundError` because the Bash tool subshell did not inherit the variable. The claim conflates "new sessions after setup" (correct) with "same session" (incorrect).

## Scope

**In:**
- `plugins/mill/scripts/millpy-builder-lock.py` — new CLI wrapping `_builder_lock.py`
- `plugins/mill/skills/mill-go/SKILL.md` — use CLI for lock ops; add pause/resume note; add cleanliness gate step
- `plugins/mill/scripts/millpy-implement.py` — harden `_forward_output()` with regex JSON extraction
- `plugins/mill/templates/implementer-brief.md` — add explicit "do NOT wrap in a code block" instruction
- `plugins/mill/scripts/millpy-cleanup.py` — add unmerged-commits guard in `build_plan()` before adding to `to_remove_done`
- `CLAUDE.md` — fix PYTHONPATH claim in Conventions section
- Relevant SKILL.md files that repeat the PYTHONPATH claim (audit and update as needed)
- Unit tests for the parser hardening and the cleanup guard

**Out:**
- mill-merge SKILL.md — no `merged` phase introduced; option A (git log check) removes that need
- `_builder_lock.py` — no changes; the stale-self-lock logic is already correct
- mill-setup SKILL.md — no functional changes to how PYTHONPATH is set; docs-only
- Any other mill-go pipeline changes not listed above

## Decisions

### A: builder-lock CLI

- **Decision:** Add `millpy-builder-lock.py` with subcommands `acquire <slug>`, `release`, `read`. Update mill-go SKILL.md to call these CLI commands instead of describing the Python API. Add a note that re-running `/mill-go` on the same task auto-reclaims the lock (stale-self-lock detection already present in `_builder_lock.acquire()`).
- **Rationale:** The Python API requires `uv run python -c "..."` plumbing that bypasses `LockBusy` detection if hand-written (as issue #128 shows happened). A CLI wrapper is the same pattern as `millpy-implement.py` and `millpy-cleanup.py` — the SKILL.md calls a script, not inline Python.
- **Rejected:** Document-only fix (operator still has to hand-roll Python to reclaim lock after crash); dedicated `/mill-pause` skill (extra machinery for a problem already solved by stale-self-lock detection).

### B: JSON parser hardening

- **Decision:** (1) Harden `_forward_output()` in `millpy-implement.py` to extract the last JSON object containing a `"status"` key from the full output using regex, rather than scanning raw lines. (2) Update `implementer-brief.md` to explicitly say the JSON must NOT be wrapped in a code block.
- **Rationale:** The template fix reduces future occurrences; the parser fix handles them when they happen anyway. Regex approach (`re.findall`) is simpler than fence-aware line parsing and handles edge cases like blank lines between fence and JSON.
- **Rejected:** Fence-aware line parser (fragile — depends on exact spacing); parser-only fix without template change (doesn't reduce model misbehavior).
- **Parser implementation:** Use `re.findall(r'\{[^{}]*"status"[^{}]*\}', output)` — take the last match. If found, emit it. If not found, emit the stuck/logic sentinel. This handles flat (non-nested) JSON objects; the implementer report schema is always flat (`{"status":..., "commit_sha":..., "session_id":...}`).

### C: cleanliness gate placement

- **Decision:** Add cleanliness check in mill-go SKILL.md between the "Implement" and "Code Review" steps: after `millpy-implement.py` returns `status: success`, run `git -C <worktree> status --porcelain`. Non-empty output → set batch state → `blocked`, `blocked_reason: "uncommitted working tree after implementer report"`, commit and push, go to Blocked flow.
- **Rationale:** The CLI (`millpy-implement.py`) owns dispatch and output; the orchestrator (mill-go) owns the state-machine decision about whether to proceed. Adding it in the CLI would conflate the two concerns.
- **Rejected:** Gate at "APPROVE" transition (too late — dirty state already pollutes the review); check inside `millpy-implement.py` (blurs CLI vs orchestrator boundary).

### D: done-vs-merged guard in mill-cleanup

- **Decision:** In `build_plan()`, before adding a `phase: done` worktree to `to_remove_done`, run `git -C <hub_root> log --oneline <parent_branch>..<task_branch>`. Non-empty output (unmerged commits exist) → add to `to_report` with message "phase=done but has unmerged commits — run mill-merge first" instead of `to_remove_done`.
- **Rationale:** After mill-merge squash-merges, it removes the worktree itself — cleanup won't encounter it. The only `done` worktrees cleanup sees are pre-merge ones. The git log check is a definitive "has mill-merge run?" signal. No mill-merge changes needed.
- **Rejected:** Introducing a `merged` phase (requires mill-merge SKILL.md changes and a new phase string; more moving parts for the same outcome).
- **Parent branch source:** Read from `status.md` via `_status.read_parent_branch(status_path)`. Already used elsewhere in `millpy-cleanup.py`.
- **`build_plan()` side-effect note:** The function docstring says "side-effect-free w.r.t. git and wiki writes". A read-only git subprocess is acceptable to add; update the docstring to "no git or wiki writes (read-only git queries are permitted)".

### E: PYTHONPATH documentation fix

- **Decision:** Update CLAUDE.md line 103 to accurately describe when PYTHONPATH is available: "takes effect in new shell sessions opened after mill-setup; within the same session, Bash tool subshells may not inherit it." Also audit SKILL.md files that repeat this claim and update them.
- **Rationale:** The incorrect claim causes silent failures when operators follow the documented pattern. The fix is docs-only because the underlying mechanic (Windows User env var) is correct — the claim just overstates its scope.
- **Rejected:** Functional change requiring all SKILL.md inline Python calls to carry an explicit `PYTHONPATH=...` prefix — unnecessary if `uv run --project` is used correctly (as it should be per CLAUDE.md); also makes every example harder to read.
- **CLAUDE_PLUGIN_ROOT note:** Issue #110 also reported `${CLAUDE_PLUGIN_ROOT}` being empty in the shell. This is a separate issue — the substitution is a CC template expansion (happens when a SKILL.md command fires), not a shell variable. Inline Bash commands typed in the conversation that use `${CLAUDE_PLUGIN_ROOT}` won't have it substituted. The discussion.md scope does not fix this; it was already addressed as part of the mill-go SKILL.md rewrite in 5e36e1a. No change needed here beyond acknowledging it in the CLAUDE.md note.

## Technical context

### `_builder_lock.py`
Location: `plugins/mill/scripts/_builder_lock.py`

Already correct. `acquire(mill_dir, slug)` handles:
- No lock → write and return.
- Same slug → refresh timestamp (stale-self-lock detection). This is why re-running mill-go already works.
- Different slug, stale → overwrite.
- Different slug, fresh → raise `LockBusy`.

`millpy-builder-lock.py` is a thin CLI shell: `acquire` exits 0 on success, 1 with a message on `LockBusy`; `release` is idempotent; `read` prints YAML or exits 1 if free. The CLI derives `mill_dir = Path.cwd() / '.millhouse'`; it must be invoked from the worktree root, consistent with every other millpy script.

### `millpy-implement.py` — `_forward_output()`
Location: `plugins/mill/scripts/millpy-implement.py` lines 42–58

Replace the current line-by-line reverse scan with:
```python
import re
matches = re.findall(r'\{[^{}]*"status"[^{}]*\}', output)
if matches:
    last = matches[-1]
    try:
        json.loads(last)
        print(last)
        return 0
    except json.JSONDecodeError:
        pass
print(json.dumps({"status": "stuck", "stuck_type": "logic", "reason": "no structured report"}))
return 0
```

The implementer report is always a flat JSON object — no nested braces. The regex `[^{}]*` safely matches across whitespace/newlines within the object.

### `implementer-brief.md` Report section
Location: `plugins/mill/templates/implementer-brief.md` lines 63–84

The JSON examples are in fenced blocks for readability. Add a bold warning after each of the two fenced JSON blocks (success and stuck):
> **Do not wrap the JSON in a code block. Output it as a bare line — no backticks, no fence. Anything other than a bare JSON line is treated as `stuck_type: logic`.**

### mill-go SKILL.md — cleanliness gate placement
Location: `plugins/mill/skills/mill-go/SKILL.md`

Add a new step between "1. Implement" and "2. Parse implementer report" — or more precisely, after Parse (since we need `status: success` first) and before "3. Code Review loop". The gate reads:

> After a `success` report: run `git -C <worktree> status --porcelain`. If non-empty → `_status.set_batch_field(status_path, batch_name, "state", "blocked")` + `_status.set_batch_field(..., "blocked_reason", "uncommitted working tree after implementer report")` + `_status.append_phase(...)` + commit + push → go to Blocked.

### mill-go SKILL.md — lock CLI update
Replace Entry step 4 from:
```
_builder_lock.acquire(Path(".millhouse"), slug)
```
To:
```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" acquire <slug>
```

Replace Blocked step and Handoff step 4 `release` calls similarly:
```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
```

Add pause note at end of Entry:
> "If mill-go is interrupted mid-run, re-run `/mill-go` — it will auto-reclaim the builder lock for the same task (stale-self-lock detection is built in)."

### `millpy-cleanup.py` — `build_plan()`
Location: `plugins/mill/scripts/millpy-cleanup.py` lines 136–137

Current:
```python
if phase == "done":
    to_remove_done.append(record)
```

Replace with:
```python
if phase == "done":
    parent_branch = _status.read_parent_branch(wt_path / "status.md")
    if parent_branch and record.branch:
        result = _subprocess_util.run(
            ["git", "-C", str(hub_root), "log", "--oneline",
             f"{parent_branch}..{record.branch}"]
        )
        if result.returncode == 0 and result.stdout.strip():
            to_report.append(
                f"{slug} — phase=done but has unmerged commits relative to "
                f"{parent_branch!r}; run mill-merge first"
            )
            continue
    to_remove_done.append(record)
```

### CLAUDE.md — PYTHONPATH claim
Location: `CLAUDE.md` line 103, within the "Conventions worth carrying" section.

Current:
> "PYTHONPATH is set globally as a Windows user environment variable by `mill-setup` Phase 4.7; CC inherits it automatically — no per-session export needed."

Replace with:
> "PYTHONPATH is set globally as a Windows user environment variable by `mill-setup` Phase 4.7. This takes effect in **new shell sessions opened after mill-setup completes**. Within the same session, and on some Windows configurations, the Bash tool subshell may not inherit it — prefix inline `uv run python -c` calls with `PYTHONPATH=\"${CLAUDE_PLUGIN_ROOT}/scripts\"` if you see `ModuleNotFoundError`."

Search for other files that repeat the "CC inherits it automatically" claim:
- `plugins/mill/skills/mill-setup/SKILL.md` — likely has Phase 4.7 description
- Any other SKILL.md that mentions PYTHONPATH

## Constraints

- No changes to `_builder_lock.py` internals — the lock logic is correct.
- `build_plan()` must remain side-effect-free for git/wiki **writes**; read-only git subprocess is acceptable.
- Regex in `_forward_output()` must handle flat JSON only (no nested `{}`). The implementer report schema is flat — this is a documented constraint in `implementer-brief.md`.
- Do not introduce a `merged` phase — mill-merge is out of scope.
- Do not change how mill-setup sets PYTHONPATH — docs-only fix for issue E.

## Testing

### Unit tests — parser hardening (`_forward_output`)
File: `plugins/mill/unit_tests/test-millpy-implement.py` (create if absent)

Scenarios to cover:
- Bare JSON on last line → extracted correctly
- JSON in `\`\`\`json\n...\n\`\`\`` block → extracted correctly
- JSON in block with trailing blank lines → extracted correctly
- Multiple JSON-like lines → last one wins
- No JSON anywhere → stuck/logic sentinel
- Malformed JSON in fence, valid JSON elsewhere → valid one extracted

### Unit tests — cleanup guard (`build_plan`)
File: `plugins/mill/unit_tests/test-millpy-cleanup.py` (existing file, add cases)

Scenarios to cover:
- `phase=done`, branch has unmerged commits → goes to `to_report`
- `phase=done`, branch fully merged → goes to `to_remove_done`
- `phase=done`, `read_parent_branch` returns None → falls through to `to_remove_done` (safe default)
- `phase=done`, no branch name in record → falls through to `to_remove_done`

Use `_subprocess_util` mock / subprocess fixture — no real git needed.

### Manual smoke test — builder lock CLI
After implementing `millpy-builder-lock.py`:
- `acquire <slug>` → lock file written
- second `acquire <slug>` (same slug) → exit 0, timestamp refreshed
- `acquire <other-slug>` within stale window → exit 1 with LockBusy message
- `release` → lock file removed
- `release` (already gone) → exit 0

### No new tests needed for
- CLAUDE.md / SKILL.md doc changes (docs only)
- mill-go cleanliness gate (SKILL.md instruction change, not a Python module)

## Q&A log

- **Q:** Should the builder lock pause path get a dedicated `/mill-pause` skill? **A:** No — stale-self-lock detection in `_builder_lock.acquire()` already makes re-running mill-go idempotent. Document the behaviour; no new skill needed.
- **Q:** Should `_forward_output()` handle nested JSON objects? **A:** No — the implementer report schema is flat. Regex `[^{}]*` is sufficient and avoids regex complexity for nested structures.
- **Q:** Should the cleanliness gate live in `millpy-implement.py` or mill-go SKILL.md? **A:** Mill-go SKILL.md — the CLI owns dispatch; the orchestrator owns state-machine transitions.
- **Q:** Should mill-cleanup get a `merged` phase or a git log check? **A:** Git log check in `build_plan()` — simpler, no mill-merge changes, and the "mill-merge removed the worktree" invariant means the check is only needed pre-merge.
- **Q:** Should PYTHONPATH be explicitly prefixed in all SKILL.md inline Python calls? **A:** No — `uv run --project` handles isolation; the fix is docs-only. Operators who see `ModuleNotFoundError` can prefix manually; the docs now say so.
