# mill-go-base: Holistic code review

**Guard:** The skip semantics have two conditions: `reviewer: null` OR `rounds: 0` means "skip holistic".
Only execute this section if `cfg.get("roles", {}).get("code-review", {}).get("holistic", {}).get("reviewer") is not None`.

`max_holistic_rounds = cfg.get("roles", {}).get("code-review", {}).get("holistic", {}).get("rounds", 1)`.
`min_holistic_rounds = cfg.get("roles", {}).get("code-review", {}).get("holistic", {}).get("min_rounds", 1)`.
Loop variable `H` starts at 1. `extra_files = []`.

**Convergence gate (min_rounds + demoted predicate).** On any round whose envelope's top-level `verdict` is `APPROVE` (the `APPROVE` branch below), compute:

```
converged = (H >= min_holistic_rounds) and not any(f.get("demoted") for f in envelope["findings"])
```

`envelope["findings"]` is the top-level field the JSON envelope already carries (`ReviewResult.findings`) — no backend change needed to read it. This site has no approved-batch carryforward concept, so `envelope["findings"]` is read directly, unfiltered.

- `converged is True`: proceed exactly as the `APPROVE` branch describes (no behavior change).
- `converged is False` AND `H < max_holistic_rounds`: the NIT-fix dispatch (when `nit_count > 0`) still runs — real, safe work — but do NOT execute the branch's terminal actions (`_status.append_phase(status_path, "holistic-approved", ...)`, the approve-commit, "Proceed to Handoff"). Instead continue the loop to round H+1.
- `converged is False` AND `H >= max_holistic_rounds` (last allowed round): treat as an implicit approval — run the branch's existing terminal actions exactly as if `converged` were `True`, but append `" (min_rounds/demoted-predicate not satisfied by round cap)"` to the approve-commit message (`"<VARIANT_LABEL>: holistic approve {slug}"`) so the shortfall is auditable.
- Step 7 (Rounds exhausted) is untouched — it only fires when verdict never reached `APPROVE` (BLOCKINGs remained the whole time), orthogonal to this gate's implicit-approve-at-cap fallback, which lives inside the `APPROVE` branch itself.

For each round `H` from 1 to `max_holistic_rounds`:

0. Wiki health-check

   Before launching the implementer / reviewer for this batch, verify a config source is reachable.
   If the check fails, release the builder lock and halt — a config source became unavailable mid-run and the implementer's downstream error would mask the root cause.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   import sys
   import _paths
   from wiki import _client
   wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
   if not _client.health_check(wiki_path):
       print('[<VARIANT_LABEL>] wiki daemon health check failed', file=sys.stderr)
       raise SystemExit(1)
   " || {
       PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
       echo "[<VARIANT_LABEL>] HALT: wiki daemon unreachable or unhealthy -- see the reason printed above; re-run mill-setup only if mill-config.yaml is confirmed missing" >&2
       exit 1
   }
   ```

1. **Crash-recovery.**
   Two-way branch based on what is on disk in `_mill/reviews/`:
   - **(a) Review file present.**
     Scan `reviews/` for a file matching `*-code-review-r{H}.md` (holistic code review files have format `{ts}-code-review-r{N}.md` -- no batch-name segment, no `-holistic-` substring;
     per-batch files embed `{batch_name}` so the glob never collides).
     If found, validate its freshness: fetch `ref_ts = _status.phase_entry_timestamp(status_path, "holistic-reviewing", occurrence=H)` (the Hth occurrence corresponds to round H);
     treat the file as this round's review ONLY if `ref_ts` is not None AND the file's mtime (UTC) is at or after `ref_ts`.
     If freshness validation passes, skip the CLI and use that file's verdict directly.
     Proceed to step 4 (verdict branch);
     do NOT execute step 2 (the phase entry was already appended on the original run) and do NOT execute step 3.
     If the file is stale or `ref_ts` is None, fall through to branch (b) handling (fire the CLI).
     Provide the inline-Python comparison snippet as per `plugins/mill/skills/mill-go-base/SKILL.md`'s per-batch section (Execute step 3 sub-step 1, crash-recovery).
   - **(b) No review file for round H.** Proceed normally to step 2 (append `holistic-reviewing` phase) and step 3 (fire the CLI).

   Inline Python helper for branch (a):

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   from pathlib import Path
   import _paths, json, sys
   hub = _paths.resolve_hub_path()
   reviews_dir = hub / '_mill/reviews'
   H = ${H}
   # (a) review file scan
   matches = sorted(reviews_dir.glob(f'*-code-review-r{H}.md')) if reviews_dir.exists() else []
   if matches:
       print(json.dumps({'branch': 'a', 'review_file': str(matches[-1])}))
       sys.exit(0)
   # (b) nothing on disk
   print(json.dumps({'branch': 'b'}))
   "
   ```

   Parse the JSON line.
   Branch dispatch is exactly as enumerated above.
   The helper is one-shot;
   do not poll it.

2. **Skip this step when step 1 returned branch (a).**
   Tree-guard checkpoint block, pre-dispatch form (see `plugins/mill/skills/mill-go-base/SKILL.md`'s "## Agent-mode dispatch") — before the append_phase/commit below. `_status.append_phase(status_path, "holistic-reviewing", _timestamp.now_utc_iso())`.
   Commit: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: holistic reviewing round {H}"`.

2.5.
**Prior-notes digest (round H > 1 only).**
If `H > 1`: scan the prior round's review file (from round `H-1`, matching `*-code-review-r{H-1}.md` with no batch-name segment) for every line matching `### [NIT] <title>` (case-insensitive NIT marker); the heading may carry a class suffix, so `### [NIT:consistency] <title>` matches as well as `### [NIT] <title>`, and the title is the heading text after the closing bracket in either form.
A heading carrying a `**Demoted-from:** BLOCKING` line on the line below it was demoted by the stage ceiling and is a genuine NIT for the purposes of this prior-non-blocking-items list, not a suppressed BLOCKING.
Extract the title text and the next non-empty line (which should contain Location and Issue fields).
Build a digest: one line per NIT finding, in format "- Title: issue context" (ASCII-only, all non-ASCII replaced with closest ASCII), write to `<briefs_dir>/prior-nonblocking-holistic-r{H}.txt`, and pass `--prior-notes <digest-path>` to the `millpy-review-code.py` invocation below.
The `reviews/` read-ban is unchanged — only the curated digest reaches the reviewer.
Round 1 passes no `--prior-notes` (digest defaults to `(none)` in the template).

3. Tree-guard checkpoint block, pre-dispatch form (see `plugins/mill/skills/mill-go-base/SKILL.md`'s "## Agent-mode dispatch") — immediately before the Agent-mode dispatch below.

   Follow the Agent-mode dispatch pattern (see `plugins/mill/skills/mill-go-base/SKILL.md`'s "## Agent-mode dispatch") with `<cli> = millpy-review-code.py` and `<args> = [--extra-file <p> ...] [--prior-notes <digest-path>]` (no `--batch` flag for holistic scope).
   Include any accumulated `extra_files` from prior `NEED_CONTEXT` rounds via `--extra-file <p>` (one flag per path).

   **Exit handling.**
   If the finalize envelope is absent, halt with "BLOCKED: holistic review pre-launch failure" and surface the last stderr line to the user.
   If a JSON envelope IS present (even with `verdict: ERROR`), drop through to sub-step 3.5 ERROR-only retry as normal.
   Matches `plugins/mill/skills/mill-go-base/SKILL.md`'s per-batch section's "only treat exit 1 as unrecoverable when JSON line is absent" branch.

   Tree-guard checkpoint block, post-dispatch form (see `plugins/mill/skills/mill-go-base/SKILL.md`'s "## Agent-mode dispatch") — immediately after that Agent-mode dispatch pattern returns (prepare through finalize).

3.5.
**Step 3.5: ERROR-only-aggregate retry (no round consumed)**

   When the JSON envelope from step 3 has top-level `verdict: "ERROR"` (or, equivalently, every entry in `reviews[]` has `verdict: "ERROR"`), skip steps 4 and 5 entirely and immediately re-run:

   Tree-guard checkpoint block, pre-dispatch form (see `plugins/mill/skills/mill-go-base/SKILL.md`'s "## Agent-mode dispatch") — immediately before this retry's Agent-mode dispatch.

   Follow the Agent-mode dispatch pattern (see `plugins/mill/skills/mill-go-base/SKILL.md`'s "## Agent-mode dispatch") with `<cli> = millpy-review-code.py` and `<args> = [--extra-file <p> ...]`.

   Tree-guard checkpoint block, post-dispatch form (see `plugins/mill/skills/mill-go-base/SKILL.md`'s "## Agent-mode dispatch") — immediately after it returns.

   The round counter `H` is **not** consumed — the round produced no reviewable output.
   On the **second** consecutive run that still has top-level `verdict: "ERROR"`, **first check rate-limit fallback** (see sub-step 3.6 below).
   Before halting: `_status.set_blocked(status_path, f"holistic code review ERROR-only round {H}", timestamp=_timestamp.now_utc_iso())`; commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on holistic review (ERROR-only round {H})"` and push; `_notify.notify("<VARIANT_LABEL>.blocked", f"holistic review: ERROR-only round {H}", slug=slug)`; release the builder lock (`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release`).
   If sub-step 3.6 does NOT apply, halt with `BLOCKED: holistic code review ERROR-only round {H}` and surface each entry's `error` string from `reviews[]` to the user.
   Do NOT auto-retry beyond the second pass.

3.6.
**Rate-limit fallback (no round consumed)**

   When sub-step 3.5's second pass returns `verdict: ERROR` AND `roles.code-review.holistic.fallback_reviewer` is not null AND any `reviews[*].error` string contains (case-insensitive) a substring listed in `roles.code-review.holistic.fallback_on` (default `["rate-limit"]`):

   1. Emit `_notify.notify("<VARIANT_LABEL>.holistic-fallback", f"swap reviewer -> {fallback_name}", slug=slug, round=H)`.
   2. In-memory mutation: `cfg["roles"]["code-review"]["holistic"]["reviewer"] = cfg["roles"]["code-review"]["holistic"]["fallback_reviewer"]`.
      Do NOT write back to disk -- the swap lasts only for the current mill-go invocation.
   3. Tree-guard checkpoint block, pre-dispatch form (see `plugins/mill/skills/mill-go-base/SKILL.md`'s "## Agent-mode dispatch") — its pre-dispatch checkpoint fires before re-running sub-step 3 with the swapped reviewer below.

      Re-run sub-step 3 (the holistic review CLI) with the swapped reviewer.
      The round counter `H` is **not** consumed.

      Tree-guard checkpoint block, post-dispatch form (see `plugins/mill/skills/mill-go-base/SKILL.md`'s "## Agent-mode dispatch") — immediately after the redispatch above returns.
   4. If the fallback reviewer ALSO returns `verdict: ERROR` on its first pass: before halting, `_status.set_blocked(status_path, f"holistic code review fallback also failed at round {H}", timestamp=_timestamp.now_utc_iso())`; commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on holistic review (fallback also failed at round {H})"` and push; `_notify.notify("<VARIANT_LABEL>.blocked", f"holistic review: fallback also failed at round {H}", slug=slug)`; release the builder lock (`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release`); then halt with `BLOCKED: holistic code review fallback also failed at round {H}` and surface every `reviews[*].error` from BOTH the original and fallback attempts.
      Do NOT cascade to a second fallback.
   5. If `fallback_reviewer is None` AND a rate-limit was detected on both 3.5 passes: before halting, `_status.set_blocked(status_path, "holistic rate-limited, no fallback_reviewer configured", timestamp=_timestamp.now_utc_iso())`; commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on holistic review (rate-limited, no fallback)"` and push; `_notify.notify("<VARIANT_LABEL>.blocked", "holistic review: rate-limited, no fallback_reviewer configured", slug=slug)`; release the builder lock (`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release`); then halt with `BLOCKED: holistic rate-limited, no fallback_reviewer configured`.
      The operator-visible message is intentional -- silent infinite fallback is wrong.

4. On `APPROVE`: If `nit_count > 0` in the envelope, dispatch one cold-start NIT-only fix pass:
   
   `nit_count` is derived from the envelope's post-ceiling `findings` list; the per-finding `title`, `severity`, and `class` are available there too, if the fixer brief needs them.

   **Dispatch the NIT-fix pass whenever `nit_count > 0` — there is no exception to this for the Builder, even under time or performance pressure.
   'Non-blocking' does NOT mean optional: deferred nits re-surface as BLOCKING in later rounds and cost more total rounds.**
   The fixer, not the Builder, decides what to leave: within the pass, the fixer may leave a nit unfixed only when the reviewer explicitly marked it 'no action required' — that latitude governs the fixer's in-pass judgment, not the Builder's dispatch decision, and never excuses skipping the dispatch itself.

   **Prior-blocking digest.**
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   import _prior_blocking, pathlib
   digest = _prior_blocking.build_digest(pathlib.Path('<reviews_dir-abs-path>'), scope='holistic')
   pathlib.Path('<briefs_dir>/prior-blocking-holistic-r{H}.txt').write_text(digest, encoding='utf-8')
   "
   ```
   Unlike the existing prior-notes digest above, this is called at every round with no `H > 1` guard — `build_digest` returns `""` when there is no prior BLOCKING history yet, and `millpy-fix.py` renders an empty digest file as `"(none)"`, so the round-1 case needs no special-casing here.

   Follow the Agent-mode dispatch pattern (see `plugins/mill/skills/mill-go-base/SKILL.md`'s "## Agent-mode dispatch") with `<cli> = millpy-fix.py` and `<args> = --scope holistic --review-file <review-file-abs-path> --round {H} --nits-only --prior-blocking <briefs_dir>/prior-blocking-holistic-r{H}.txt`.
   The fixer loads `mill-receiving-review` and applies the NITs. Do NOT re-review — the NIT fix is trusted. On stuck → escalate via the existing Stuck escalation path.
   After the NIT-fix completes successfully (or is skipped because `nit_count = 0`): compute `converged` per the Convergence gate above.
   If `converged`, or `H >= max_holistic_rounds` (implicit-approve-at-cap): `_status.append_phase(status_path, "holistic-approved", _timestamp.now_utc_iso())`. Commit on the task branch: `git -C <worktree> add <status_path> <review_file_path> _mill/briefs/ && git -C <worktree> commit -m "<VARIANT_LABEL>: holistic approve {slug}"` — when not `converged` (implicit-approve-at-cap fired), append `" (min_rounds/demoted-predicate not satisfied by round cap)"` to the commit message — where `<review_file_path>` is the `file` field from `reviews[0]` of the JSON envelope (or the crash-recovery branch (a) scan path). This mirrors `plugins/mill/skills/mill-go-base/SKILL.md`'s per-batch APPROVE branch, which already stages its review file. If a NIT-fix pass ran for the holistic scope this round, the fixer already committed its own changes; this commit still stages the review file plus the `holistic-approved` status row. Proceed to Handoff.
   If not `converged` and `H < max_holistic_rounds`: skip the terminal actions above and continue to round H+1.

5. On `REQUEST_CHANGES`: the holistic-fix CLI dispatches a fresh fixer;
   the fixer loads `mill-receiving-review` (see `plugins/mill/skills/mill-go-base/SKILL.md`'s "## Principles").
   Builder does not load the skill.

   Follow the Agent-mode dispatch pattern (see `plugins/mill/skills/mill-go-base/SKILL.md`'s "## Agent-mode dispatch") with `<cli> = millpy-fix.py` and `<args> = --scope holistic --review-file <abs-path-to-holistic-review-file> --round {H}`.
   Parse stdout JSON (same last-`{"status":...}`-line pattern as `plugins/mill/skills/mill-go-base/SKILL.md`'s per-batch handling).
   The CLI handles `holistic-fixing` phase + commit + push itself.
   - `stuck_type: infrastructure`: auto-retry ONCE with a fresh re-fire: re-dispatch once with a fresh session.
     If the re-fire also fails with `infrastructure`: set batch state -> `blocked`, `blocked_reason: "infrastructure: worker died (logout?)"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on holistic review"`, and go to *Blocked*.
     The re-fire is fresh (killed session cannot be reattached).
   - `stuck_type: transient`: one-retry policy (re-invoke once) — this retry IS the one-shot self-resolve attempt.
     If still transient after it: set batch state -> `blocked`, `blocked_reason: "transient: unresolved after retry"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on holistic review"`, and go to *Blocked*.
   - `stuck_type: verify` or `logic` (first occurrence) → self-resolve once: investigate the finding using the same judgment an implementer/fixer already applies when picking "edit plan and retry" — read the holistic review file, edit the plan file(s) if the failure traces to an ambiguous or incorrect card.
     **Regardless of whether a plan edit was made**, append a `## Prior failure` section to `00-overview.md` (placed immediately after its frontmatter, before `## Batch Index` — create the section if it is not already present) with one new bullet stating the round and the verbatim stuck-JSON `reason` text, regardless of whether the reason names a specific batch, spans several, or names none at all.
     Before re-invoking, record the self-resolve: `_status.append_phase(status_path, "self-resolved-verify-logic", _timestamp.now_utc_iso())`, `git -C <worktree> add <plan_dir> <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: self-resolved verify/logic stuck (holistic)"`.
     Then re-invoke `millpy-fix.py --scope holistic` once (fresh) for this round.
     If the retry produces the *same* `verify`/`logic` failure: set batch state -> `blocked`, `blocked_reason: "verify/logic: unresolved after retry"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on holistic review"`, and go to *Blocked*.
   - On success: increment H and loop.

6. On `NEED_CONTEXT`: apply the same extra-files / notify path as `plugins/mill/skills/mill-go-base/SKILL.md`'s per-batch handling.

7. **Rounds exhausted** (`H > max_holistic_rounds`, `REQUEST_CHANGES` still returned): `_status.set_blocked(status_path, f"holistic review exhausted {max_holistic_rounds} round(s)", timestamp=_timestamp.now_utc_iso())`;
   commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on holistic review"` and push;
   halt with "Holistic review exhausted {max_holistic_rounds} round(s).
   Task left as [active] for manual review."
