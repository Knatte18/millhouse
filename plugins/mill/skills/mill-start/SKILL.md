---
name: mill-start
description: In a spawned worktree, discuss the solution with the user and produce a self-contained discussion.md that mill-plan can consume with zero conversation history.
argument-hint: "[--auto]"
---

# mill-start

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

You are a collaborative solution designer. Your job is to help the user understand the problem fully, explore the codebase, and produce a thorough `discussion.md` that captures every decision needed for autonomous plan-writing. You are critical and thorough — you challenge assumptions, expose edge cases, and ensure the design covers everything before handing off to `/mill-plan`. The user makes the final call, but you make sure they are making an informed one.

## Auto mode

If the skill argument is `--auto`, the rules in this subsection override the default operator-interaction behaviour of Phase: Discuss and Phase: Discussion Review. The bare `--auto` flag is the only supported form; `--auto=<value>` is not accepted.

**Phase: Discuss — `--auto` changes:**

- Every operator prompt MUST be formatted as a numbered-options list per the `mill:conversation` rule "the recommended option, if any, MUST be option 1". Free-text questions are forbidden — the SKILL must coerce any candidate question into options.
- Instead of waiting for operator input, the assistant immediately auto-picks option `1)` (the recommendation).
- Each auto-pick is appended to discussion.md's `## Q&A log` section.

**Q&A log format under `--auto`:**

```
- **Q:** <question> **A:** [auto-pick] <option-1-label>. **Why:** <rationale>.
```

Operator-driven entries keep the existing bare format (`- **Q:** … **A:** …`).

**Phase: Discussion Review — `--auto` changes:**

- Before the loop, initialise: `prev_gap_titles: set[str] = set()` and `extension_used: bool = False`.
- Review still runs up to `max_review_rounds` (no skip).
- The `mill-receiving-review` skill is still loaded before reading any review file (the existing non-negotiable rule applies). Under `--auto` the PUSH BACK path of the decision tree is unavailable: there is no operator to escalate to. Every gap AND every NOTE returned by the reviewer is treated as FIX regardless of the decision-tree outcome (factually-wrong findings included). PUSH BACK is unavailable because no operator is present.
- On `GAPS_FOUND`, the assistant auto-resolves each gap by adding the missing information to discussion.md using best judgment, commits, **pushes**, and re-runs the review.
- On APPROVE, read the review file. If zero `[NOTE]` findings: break the loop and proceed to Handoff (auto-path identical to interactive 4a). If one or more `[NOTE]` findings: take the interactive 4b path verbatim — auto-resolve each NOTE by editing `<discussion_path>` using best judgment (per the `mill-receiving-review` decision tree, with PUSH BACK unavailable), write the same fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-discussion-fix-r<N>.md` with `## Fixed` / `## Pushed Back` sections, append `discussion-fix-r{N}` to the status timeline, single commit covering `<discussion_path>` + `<reviews_dir>/` + `<status_path>` with message `mill-start: discussion-fix round {N} for {slug}`, push, break loop → Handoff. The Q&A log is NOT touched for NOTEs — the fixer report is the audit trail.
- At the end of each GAPS_FOUND round (after committing and pushing gap fixes): (1) parse the current round's gap titles from the review file (heading text of each `### [GAP]` finding) into `current_gap_titles`; (2) if `round >= max_review_rounds` — non-progress check: if `current_gap_titles.isdisjoint(prev_gap_titles)` AND `not extension_used`: set `extension_used = True`, allow one more round (do NOT block), and continue the loop (`round += 1`); otherwise (overlap exists, or `extension_used` is already `True`): call `_status.set_blocked(status_path, f"auto: discussion review gaps unresolved after {N} rounds", timestamp=_timestamp.now_utc_iso())`, then `git -C <worktree> add <status_path> && git commit -m "mill-start: blocked (auto: discussion review gaps unresolved) for <slug>" && git push`, then halt — do NOT proceed to Handoff; (3) update `prev_gap_titles = current_gap_titles` (every round, including the extension round).

`--auto` is independent from `pipeline.autonomous_mode`: `--auto` is a per-invocation flag controlling Phase: Discuss / Discussion Review behaviour in mill-start; `pipeline.autonomous_mode` is a config key controlling mill-go's stuck-handling. The Auto mode subsection neither reads nor writes `pipeline.autonomous_mode`. Operators opt into each separately.

## Entry

1. Resolve the wiki path via `_paths.resolve_wiki_path(_paths.resolve_git_root())`.
   `signature: _paths.resolve_git_root(start: Path | None = None) -> Path`
   `signature: _paths.resolve_wiki_path(git_toplevel: Path) -> Path`
2. Read the slug via `_marker.slug_from_branch(git_root, wiki_path, cfg)`. On `MarkerError`, halt and tell the user this worktree was not created by `mill-spawn`.
3. Load config — deep-merge `<hub_root>/mill-config.yaml` (shared hub overlay) with `.millhouse/config.local.yaml` (gitignored worktree overlay). Read `roles.discussion-review.holistic.rounds` as `max_review_rounds`.
   `signature: _config.load_config(hub_root: Path, worktree_root: Path) -> dict`

**Path Setup.** `cfg` is already loaded. Derive: `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])`. For new discussion file creation (Phase: Discussion File), use `discussion_path = worktree_root / cfg['paths']['discussion_file']` (config-canonical; no compat fallback on write). For reviews: `reviews_dir = worktree_root / cfg['paths']['reviews_dir']`. Use these variables for all subsequent path references.

## Phases

Report the current phase to the user at each transition. Progress is linear; never skip phases.

### Phase: Color

Read `.vscode/settings.json`; extract `titleBar.activeBackground`. Map to a Claude Code colour name (`purple`, `blue`, `yellow`, `red`, `cyan`, `indigo`, `orange`). If matched, tell the user: "Run `/color <name>` to match this worktree's theme." Missing file / no match → skip silently.

### Phase: Select

Read `<WIKI_PATH>/Home.md`, find the task heading whose slug matches the slug derived from the current branch. The entry's phase marker must be `[active]`. If not, halt with a message explaining what `mill-spawn` should have done.

### Phase: Active

The initial status file (at `status_path`) was written by `mill-spawn` and committed on the task branch with `phase: discussing`. Verify it exists and the `parent:` branch is recorded. No edit needed here.

### Phase: Explore

Before asking a single question, explore the relevant parts of the codebase.

- If `_codeguide/Overview.md` exists: follow the codeguide navigation pattern (Overview → module docs → Source links).
- Otherwise: use file structure, `git log`, and `Grep` / `Glob`.
- Check recent commits related to the task.
- Read `CONSTRAINTS.md` at the hub root if present (use `_constraints.read_if_exists()`).
- Do not ask questions you can answer from the codebase.

### Phase: Discuss

Interview the user relentlessly about every aspect of the task. Ask questions in **focused batches**. Questions that don't depend on each other's answers can be asked together. For each question, provide your **recommended answer**. Prefer multiple-choice (A/B/C with trade-offs) when there are distinct options. Cap each batch at ≤5 questions; ask the rest in subsequent batches after the user answers.

Cover these categories:

- **Scope** — what's in, what's out.
- **Constraints** — performance, compatibility, existing patterns.
- **Architecture** — modules, interfaces, dependencies.
- **Edge cases** — failures, concurrency, empty state, invalid input.
- **Security** — trust boundaries, validation. Only if relevant.
- **Testing** — approach per module, TDD candidates, key scenarios.

Propose 2–3 approaches with explicit trade-offs; lead with your recommendation. Wait for user approval before moving on.

### Phase: Discussion File

Render `plugins/mill/templates/discussion.md` into `discussion_path`, substituting `<TASK_TITLE>`, `<SLUG>`, `<PARENT_BRANCH>` from `status_path`. Fill every section — the file must be **self-contained**: a fresh mill-plan session with zero conversation history must be able to write a complete implementation plan from this file alone.

Commit on the task branch: `git -C <worktree> add <discussion_path> && git commit -m "mill-start: write discussion.md for {slug}"`.

### Phase: Discussion Review

**Status safeguard (applies to all `_status.append_phase` calls in this phase):** Before any `_status.append_phase` call, run `git -C <worktree> status --short -- _mill/status.md`. If the output contains `D` (a line beginning with ` D` for working-tree deleted, or `D ` for staged deletion), restore the file via `git -C <worktree> checkout HEAD -- _mill/status.md` before proceeding. Blank output means the file is present and unchanged — blank is NOT the deletion signal.

The new schema has two skip conditions: `rounds: 0` OR `reviewer: null` means "skip discussion review". If `max_review_rounds == 0` OR `roles.discussion-review.holistic.reviewer` is `None`: skip straight to Handoff.

Loop up to `max_review_rounds` rounds. Each round:

1. Report: **"Discussion Review — round N/max_review_rounds"**.
2. Background the CLI via `millpy-bg`:

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug review-discussion-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-discussion.py"
   ```

   This returns immediately with `pid=<N> log=<abs-path>`. Do **not** use `run_in_background: true` on the Bash tool — that routes output to CC's temp dir. Poll the log file with `cat <log-path>` until the line `[mill-bg] EXIT` appears. Once it does, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line. The script writes the review file under `_mill/reviews/` and emits a one-line JSON summary: `{"type": "discussion", "round": <int>, "verdict": "APPROVE" | "GAPS_FOUND", "blocking_count": <int>, "reviews": [{"scope": "holistic", "verdict": ..., "file": "<abs-path>", "session_id": "<id>"}]}`.

3. **BEFORE reading the review file, load the `mill-receiving-review` skill** (see `plugins/mill/skills/mill-receiving-review/SKILL.md`). This is non-negotiable — the decision tree it encodes is what keeps review loops useful instead of adversarial.

3.5. **Step 3.5: ERROR-only-aggregate retry (no round consumed)**

   When the JSON envelope from step 2 has top-level `verdict: "ERROR"` (or, equivalently, every entry in `reviews[]` has `verdict: "ERROR"`), skip steps 4a / 4b / 5 entirely and immediately re-run:

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug review-discussion-retry-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-discussion.py"
   ```

   Returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   The round counter `N` is **not** consumed -- the round produced no reviewable output. On the **second** consecutive run that still has top-level `verdict: "ERROR"`, halt with `BLOCKED: discussion review ERROR-only round {N}` and surface each entry's `error` string from `reviews[]` to the user. Under `--auto` mode, halt by calling `_status.set_blocked(status_path, f"auto: discussion review ERROR-only round {N}", timestamp=_timestamp.now_utc_iso())`, then `git -C <worktree> add <status_path> && git commit -m "mill-start: blocked (auto: discussion review ERROR) for <slug>" && git push`. Do NOT auto-retry beyond the second pass. The two-pass cap mirrors mill-go's Step 4.5.

4a. On APPROVE (verdict from JSON) with no NOTE findings: read the review file at the absolute path supplied by `reviews[0].file` in the JSON envelope from step 2 and confirm zero `[NOTE]`-prefixed findings. Break the loop and proceed to Handoff.

4b. On APPROVE with one or more `[NOTE]` findings: apply each NOTE fix per the `mill-receiving-review` decision tree by editing `<discussion_path>` directly. Write a fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-discussion-fix-r<N>.md` (timestamp from `_timestamp.now_utc_compact()`) with two sections — `## Fixed` (one line per fixed NOTE: short reference to the source review file + quoted finding title) and `## Pushed Back` (one line per rejected NOTE: short reference + reason citing code, doc, or scope per `mill-receiving-review`'s legitimate-pushback rules). Call `_status.append_phase(status_path, f"discussion-fix-r{N}", _timestamp.now_utc_iso())`. Single git commit covering exactly three pathspecs — `<discussion_path>`, `<reviews_dir>/`, `<status_path>` — with message `mill-start: discussion-fix round {N} for {slug}`. Push. Break loop → Handoff. Do NOT run round N+1. Do NOT advance the round counter; the fixer report's `discussion-fix-r<N>` reuses the just-completed review round's `N` value.

5. On GAPS_FOUND: read the review file and enumerate each `[GAP]` finding. Present gaps to the user in **sequential batches of at most 5 gaps per batch**. Each gap is formatted as a numbered question whose resolution options follow the `mill:conversation` rule — numbered text list, the recommended option is option 1 (the SKILL must use its judgment + context to propose a recommended resolution and 1–3 distinct alternatives). Free-text gap prompts are forbidden; the SKILL must coerce every gap into options form, just as the auto-mode rule does for interview questions in Phase: Discuss. Wait for the user to answer every gap in the current batch before presenting the next batch. As each batch's answers arrive, apply them to an in-memory copy of `<discussion_path>` (do NOT write the file mid-round). When the final batch in this round is answered, write `<discussion_path>`, commit on the task branch (`git -C <worktree> add <discussion_path> <reviews_dir>/ && git commit -m "mill-start: discussion-gap-fix round {N} for {slug}"`), push, and start round N+1. If a gap is genuinely impossible to answer (operator does not know yet), the operator may pick the recommended option and add a follow-up note inline — that is the same fallback as Phase: Discuss.

If unresolved gaps remain after `max_review_rounds`: present them to the user for an explicit override ("ignore gap X for now") or more-info decision.

### Phase: Handoff

Call `_status.append_phase(status_path, "discussed", timestamp)`. Commit on the task branch: `git -C <worktree> add <status_path> && git commit -m "mill-start: handoff {slug}"`.

Report: **"Discussion complete. Run `/mill-plan` next to start autonomous plan writing."** Do not invoke `/mill-plan` yourself — handoff is always an explicit user decision.

## Principles

- **Design the full scope** — never suggest MVP phases or "we can add this later".
- **YAGNI ruthlessly** — don't design for hypothetical requirements.
- **Batch independent questions.**
- **Explore before asking** — read `package.json` instead of asking what framework is used.
- **Challenge the problem, not just the solution** — "is this actually the right thing to build?" is always valid.
- **Recommend answers** based on codebase context.
- **Hammer out scope** — explicitly define what changes and what doesn't.
- **In existing codebases** — follow existing patterns; improve code you're working in where appropriate.

## Board discipline

- Wiki mutations go through `_client` calls (`set_phase`, `upsert_task`, `merge_tasks`); the daemon serializes all writes and pushes automatically. For multi-step atomic operations use `_client.merge_tasks`.
- Task-state writes (`status_path`, `discussion_path`) are committed on the task branch via `git add` + `git commit`, then pushed to remote. They never go through the wiki.
- Phase transitions are recorded via `_status.append_phase`. Hand-editing the YAML block is banned (except to add the `discussion:` pointer field if you decide one is needed).
