# Discussion: Fix agent-mode dispatch gaps: HTML escaping, missing flags, timeouts, and stale skill content

```yaml
task: Fix agent-mode dispatch gaps: HTML escaping, missing flags, timeouts, and stale skill content
slug: mill-go-dispatch-and-skill-gaps
status: discussing
parent: main
```

## Problem

Five independent gaps were reported against the agent-mode dispatch path
(mill-go's `## Agent-mode dispatch` pattern) and the skill-load path
(mill-start, and generic same-session skill freshness) during recent live
runs. Each is a small, self-contained defect or documentation gap; none
overlap in code paths, but all were folded into one task because they
share the "agent-mode dispatch and skill-load path" surface area. Sourced
from GitHub issues #605, #606, #599, #598, #596 (all CLOSED, consolidated
into this wiki task by mill-fold — the issues are the source-of-truth
detail, not open items to re-derive).

## Scope

**In:**
- (#605) Unescape HTML entities (`&lt;`, `&gt;`, `&amp;`, etc.) from
  `<task-notification>` payload text before it is parsed as the agent's
  report, at every site that reads a `--agent-output` file back from
  disk (four sites — see Decisions).
- (#606) Document in mill-go's `## Agent-mode dispatch` step 6 that
  `millpy-fix.py --stage finalize`'s "same standard arguments" includes
  `--scope`, `--batch-name` (batch scope only), and `--review-file` —
  all three are required by the CLI at every stage, not just prepare.
- (#599) Document an extended Bash-tool timeout recommendation for
  `millpy-fix.py --stage finalize` calls in Agent-mode dispatch step 6,
  since finalize replays every batch's `verify:` command sequentially
  and can exceed the default 2-minute Bash timeout.
- (#598) Add an explicit, unconditional load of the `mill:conversation`
  skill at the very start of mill-start's Entry section, before any
  phase that can prompt the operator.
- (#596) Document a session-freshness rule for the Skill tool: if a
  prior step in the same session edited a `SKILL.md` file, do not trust
  the Skill tool's cached content for that skill later in the session —
  `Read` the file directly first.

**Out:**
- No change to `_forward_output`'s report-parsing logic beyond
  unescaping the raw text before it's handed off — the JSON/status
  parsing contract is unchanged.
- No change to what `millpy-fix.py` accepts or requires as flags (no
  CLI signature change) — #606 is a SKILL.md documentation fix only.
- No change to `millpy-fix.py --stage finalize`'s verify-replay
  behavior (i.e., NOT pursuing the "skip full verify replay for
  nits-only" alternative from #599) — that would weaken the regression
  safety net finalize provides and is a materially bigger, riskier
  change than documenting a longer timeout.
- No attempt to fix the underlying Skill-tool caching behavior itself
  (#596) — that is harness-level and outside mill's codebase. Only the
  orchestrator-facing documentation/workaround is in scope.
- No sweep of other skills for similar timeout/flag/freshness gaps
  beyond the five reported issues — this task fixes what was reported,
  not a general audit.

## Decisions

### html-unescape-at-read-site

- Decision: Fix #605 in code, not prose. At every site that reads an
  `--agent-output` file back from disk and treats its contents as the
  captured notification text, wrap the read with `html.unescape(...)`
  (Python stdlib `html` module) before any further parsing:
  - `plugins/mill/scripts/_implementer_common.py` — `finalize_from_output`
    (around line 844: `output = Path(agent_output_path).read_text(encoding="utf-8")`),
    used by both `millpy-implement.py` and `millpy-fix.py`.
  - `plugins/mill/scripts/millpy-review-code.py` (around line 181:
    `raw_text = agent_output_path.read_text(encoding="utf-8")`).
  - `plugins/mill/scripts/millpy-review-discussion.py` (around line 142:
    same pattern).
  - `plugins/mill/scripts/millpy-review-plan.py` (around line 183:
    `raw_text = agent_output_path.read_text(encoding="utf-8")`, feeding
    `finalize(...)`) — dispatched via the same Agent-mode
    prepare→Agent→finalize flow per `plugins/mill/skills/mill-plan/SKILL.md`
    line 187, so it is equally exposed.
- Rationale: The corruption happens because the `<task-notification>`
  payload arrives HTML-escaped and is captured verbatim into `.out.md`.
  Fixing it at the read site (in code) is mechanical and testable —
  it protects every current and future caller uniformly, regardless of
  whether the orchestrator (an LLM following SKILL.md prose) transcribes
  the capture step perfectly every time. Using stdlib `html.unescape`
  (not a hand-rolled regex for `&lt;`/`&gt;`/`&amp;`) handles the full
  HTML5 entity set correctly, including double-escaping edge cases. The
  captured text at each read site is the notification payload's rendered
  markdown (implementer/reviewer report), which the harness escapes
  uniformly end-to-end before delivery — so a whole-text `html.unescape`
  is the correct full inverse, not a partial one; there is no free-form,
  independently-authored text mixed into that payload that could be
  legitimately entity-encoded on purpose.
- Rejected:
  - Manual entity substitution instructed in SKILL.md prose (relies on
    LLM discipline at write time; error-prone, unverifiable, the exact
    failure mode that produced #605).
  - A new shared helper module/function wrapping `html.unescape` — four
    call sites each doing one extra `html.unescape()` call is not enough
    duplication to justify a new abstraction (YAGNI).
  - Unescaping at write time (when the SKILL.md step 5 capture writes
    `.out.md`) instead of read time — write time is still an LLM
    transcription step; read time is code, so it's the correct place to
    guarantee correctness regardless of what got written.

### document-review-file-required-at-finalize

- Decision: In `plugins/mill/skills/mill-go/SKILL.md`'s `## Agent-mode
  dispatch` step 6 ("Run finalize stage"), add an explicit note that for
  `millpy-fix.py`, "the same standard arguments" means re-passing
  `--scope`, `--batch-name` (batch scope only), and `--review-file
  <path>` exactly as given to the prepare-stage call — `millpy-fix.py`
  requires `--review-file` unconditionally regardless of `--stage`
  (confirmed: the CLI's argument validation checks `--review-file` before
  branching on `--stage`).
- Rationale: This is a documentation-only fix. The CLI behavior is
  already correct and intentional (finalize needs the review file to
  reconstruct context); the gap is purely that SKILL.md step 6's generic
  "same standard arguments" phrasing doesn't spell out which arguments
  are fix-CLI-specific and load-bearing at finalize time, unlike
  implement/review CLIs where finalize doesn't need an equivalent flag.
- Rejected: Changing `millpy-fix.py` to make `--review-file` optional at
  `--stage finalize` (e.g., recovering it from `status.md`) — bigger,
  riskier change for no behavioral benefit; the orchestrator already has
  the review-file path in scope from the same round, so re-passing it
  costs nothing.

### document-finalize-timeout-guidance

- Decision: In the same `## Agent-mode dispatch` step 6, add a note that
  `millpy-fix.py --stage finalize` calls should be given an extended
  Bash-tool timeout — recommend 600000ms (10 minutes) — because finalize
  replays every batch's `verify:` command sequentially as a regression
  guard, and this can exceed the default 2-minute Bash tool timeout on
  plans with several slow verify suites (observed: real-world run hit
  exit 143 at 2 minutes, succeeded at 8 minutes with a longer timeout).
  Scope the note to fix-CLI finalize calls specifically (both
  `--nits-only` and full fix, both batch and holistic scope) — this is
  where the full multi-batch verify replay lives; review-CLI finalize
  calls don't run verify commands and aren't affected.
- Rationale: Documenting a longer default timeout is a small, safe,
  immediately-applicable fix. It matches the existing pattern already in
  the skill for subprocess/psmux poll loops ("Subprocess/psmux poll-loop
  max-wait" — bounded but generous wait, ~3600s) — Agent-mode's direct
  (non-backgrounded) finalize call needs an equivalent generous-timeout
  norm, just expressed as a Bash tool timeout parameter instead of a
  poll-loop bound.
- Rejected: Changing `--stage finalize` to skip the full verify replay
  for nits-only fixes (option (b) from the source issue) — this removes
  a real regression check (a "nits-only" cosmetic fix can still break
  something) for the sake of speed. Out of scope per the Scope section
  above; a documentation fix carries no such risk.

### force-load-conversation-skill-at-entry

- Decision: Add a new "Step 0" to mill-start's `## Entry` section (before
  the existing Step 1 "Resolve the wiki path"), instructing the assistant
  to load the `mill:conversation` skill unconditionally, immediately,
  before any other Entry step. Mirrors mill-go's existing `## Entry`
  "Step 0: Verify `CLAUDE_PLUGIN_ROOT`" pattern (a numbered Step 0 ahead
  of Step 1).
- Rationale: `mill:conversation` is what bans `AskUserQuestion` and
  mandates numbered-option prompts. Every operator-facing prompt in
  Phase: Discuss and Phase: Discussion Review depends on it being
  active. Today it's loaded only by convention/habit (this very session
  loaded it manually at startup per `mill:workflow`'s skill table, not
  because mill-start's own Entry section requires it) — nothing in
  mill-start's Entry forces it, so a session that skips the informal
  step can fire `AskUserQuestion` mid-Phase:-Discuss with no guard.
- Rejected: Relying on `mill:workflow`'s "always use on startup" table
  entry alone — that's exactly the status quo that produced #598; it's
  advisory, not enforced by the specific skill that needs it.

### skill-tool-freshness-anti-pattern

- Decision: Add a new anti-pattern item to `plugins/mill/skills/workflow/SKILL.md`'s
  existing "## Anti-patterns" numbered list (after the existing two
  items): if any prior step in the current session edited a `SKILL.md`
  file (via `Edit`/`Write` on `plugins/*/skills/**/SKILL.md`), do not
  trust the Skill tool's served content for that skill for the rest of
  the session — `Read` the file directly to get the current on-disk
  content before following its instructions. Call out the concrete
  trigger scenario: a batch inside a `mill-go` run edits a `SKILL.md`
  (e.g. `mill-finalize`, `git-pr`, `mill-merge`, `mill-cleanup`), and a
  later step in the *same* run invokes that skill via the Skill tool.
- Rationale: `mill:workflow` is loaded at the start of every mill
  orchestrator session (mill-start, mill-go, mill-plan, etc. all load it
  per its own table), making it the single place a session-wide freshness
  rule reaches every orchestrator, rather than duplicating the same note
  across mill-go, mill-finalize, mill-merge, and mill-cleanup
  individually. The underlying Skill-tool caching behavior is a harness
  property mill's codebase cannot change — the only available fix is an
  orchestrator-facing workaround, i.e., documentation.
- Rejected:
  - Fixing the Skill tool's caching behavior directly — out of reach;
    it's harness infrastructure, not mill code.
  - Duplicating the rule inline in mill-go's Handoff step (where the
    concrete #596 incident occurred, invoking mill-finalize) instead of
    in `mill:workflow` — narrower placement would miss mill-merge,
    mill-cleanup, and any other same-session skill-after-edit sequence
    the issue explicitly calls out as equally affected.

## Technical context

- Agent-mode dispatch pattern lives entirely in
  `plugins/mill/skills/mill-go/SKILL.md`'s `## Agent-mode dispatch`
  section (~lines 105-179 as of this writing); steps 5 and 6 are the
  edit targets for #605 (indirectly — the actual fix is in the read-site
  code, not step 5's prose) and #606/#599 (step 6's finalize-invocation
  note).
- `finalize_from_output` in `plugins/mill/scripts/_implementer_common.py`
  is the single shared read site for both `millpy-implement.py` and
  `millpy-fix.py` — one fix there covers both implement and fix CLIs.
  `millpy-review-code.py`, `millpy-review-discussion.py`, and
  `millpy-review-plan.py` each have their own independent read site
  (they don't route through `_implementer_common`), so the fix needs
  four edits total, not one: `_implementer_common.py` plus the three
  standalone review CLIs.
- `millpy-fix.py`'s argparse validates `--review-file is None` (line
  ~128) unconditionally, before any `--stage` branching — confirms
  #606's premise directly from the CLI source, no behavior change
  needed there.
- `mill-start`'s current `## Entry` section has three numbered steps
  (resolve wiki path, read slug, load config) with no Step 0 and no
  skill-load instruction; `mill-go`'s `## Entry` already has the
  "Step 0: Verify `CLAUDE_PLUGIN_ROOT`" precedent to mirror.
- `plugins/mill/skills/workflow/SKILL.md`'s `## Anti-patterns` section
  currently has exactly two numbered items (helper-internals,
  wrapper-script-for-loops); the new item is a third.
- No CONSTRAINTS.md present at the hub root for this repo.

## Testing

- **html-unescape-at-read-site** is the one code change with real test
  surface — TDD candidate. Existing unit test files
  `plugins/mill/unit_tests/test-implementer-common.py` (for
  `finalize_from_output`) should gain a case that feeds HTML-escaped
  text (e.g. `Q&amp;A`, `send &lt;guid&gt;`, `Cards 20 &amp; 21`)
  through the `--agent-output` file and asserts the parsed/forwarded
  result contains the unescaped form. `test-review-finalize.py` and the
  per-CLI flow tests (`test-review-code-flow.py`,
  `test-review-discussion-flow.py`, `test-review-plan-flow.py`) already
  exist and cover each of `millpy-review-code.py` /
  `millpy-review-discussion.py` / `millpy-review-plan.py`'s finalize
  stage — add an equivalent HTML-escape case to each as required
  coverage for all four read sites, not just
  `test-implementer-common.py`. Use in-memory/tempfile fixtures per
  `mill:testing` conventions — no real git/LLM needed, this is pure text
  transformation.
- The other four decisions (#606, #599, #598, #596) are SKILL.md
  prose/documentation edits with no executable surface — verified by
  reading the edited section back and confirming it accurately reflects
  the corresponding CLI's actual flag/behavior requirements (already
  cross-checked against source during this discussion), not by automated
  tests.

## Q&A log

- **Q:** How should #605's HTML-escaping be fixed — code-level unescape at read time, or SKILL.md prose instructing manual unescaping at write time? 1) Unescape in code at every `--agent-output` read site using stdlib `html.unescape` (Recommended) — mechanical, testable, protects all current/future callers regardless of orchestrator transcription. 2) Instruct manual entity substitution in SKILL.md step 5 prose — relies on LLM discipline at write time, the exact failure mode that caused #605. 3) Add a new shared helper module wrapping `html.unescape` for the three call sites — unnecessary abstraction for three one-line call sites. **A:** [auto-pick] Option 1. **Why:** correctness belongs in code, not in prose an LLM must transcribe perfectly every time; matches CLAUDE.md's "mechanical > manual" bias and avoids premature abstraction.
- **Q:** How should #606 (missing `--review-file` re-pass documentation) be resolved? 1) Document explicitly in mill-go SKILL.md step 6 that finalize's "same standard arguments" for `millpy-fix.py` includes `--scope`/`--batch-name`/`--review-file` (Recommended) — doc-only, zero risk, matches existing (correct) CLI behavior. 2) Change `millpy-fix.py` so `--review-file` is optional at `--stage finalize` and recovered from `status.md` instead — bigger CLI surface change for no benefit, since the orchestrator already has the path in scope. **A:** [auto-pick] Option 1. **Why:** the CLI's requirement is already correct and intentional; the gap is purely in SKILL.md's generic phrasing, not in code.
- **Q:** How should #599 (finalize timeout) be resolved — document a longer timeout, or change finalize to skip the full verify replay for nits-only fixes? 1) Document an extended Bash-tool timeout (recommend 600000ms) for `millpy-fix.py --stage finalize` calls in Agent-mode dispatch step 6 (Recommended) — safe, immediately applicable, no change to verify semantics. 2) Change finalize to skip the full multi-batch verify replay when only a nits-only fix was applied — removes a real regression check; a "nits-only" change can still break something. **A:** [auto-pick] Option 1. **Why:** the safe fix is documentation; weakening the verify replay for speed trades away the exact safety net finalize exists to provide, and is out of this task's scope per the Scope section.
- **Q:** Where should #598's `mill:conversation` force-load live? 1) A new numbered "Step 0" in mill-start's `## Entry` section, unconditional, before Step 1 (Recommended) — mirrors mill-go's existing "Step 0: Verify `CLAUDE_PLUGIN_ROOT`" precedent; enforced by the specific skill that needs it. 2) Rely on `mill:workflow`'s existing "always use on startup" table entry — that's the current (broken) status quo; advisory only, not enforced. **A:** [auto-pick] Option 1. **Why:** #598 exists precisely because the advisory table entry isn't enough; enforcement belongs in the skill whose phases actually prompt the operator.
- **Q:** Where should #596's Skill-tool freshness rule live? 1) A new anti-pattern item in `mill:workflow` SKILL.md's `## Anti-patterns` section (Recommended) — loaded at the start of every mill orchestrator session, covers mill-go, mill-finalize, mill-merge, mill-cleanup, and any other same-session skill-after-edit sequence in one place. 2) Inline in mill-go's Handoff step only (where the concrete #596 incident occurred) — narrower, would miss mill-merge/mill-cleanup which the source issue explicitly calls out as equally affected. **A:** [auto-pick] Option 1. **Why:** the issue's own "Expected" note frames this as a general orchestrator-freshness rule, not a mill-go-specific one; one central location avoids drift across four+ skills.
