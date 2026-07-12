# Discussion: Explore and adopt Claude Code fork-agents in mill orchestration

```yaml
task: Explore and adopt Claude Code fork-agents in mill orchestration
slug: explore-fork-agent-opportunities
status: discussing
parent: main
```

## Problem

Claude Code has a native "fork" sub-agent (`Agent` tool, `subagent_type: "fork"`) that
continues from the parent's own conversation instead of starting cold. Mill dispatches
every sub-agent cold: it renders a brief file, spawns a fresh `mill:mill-implementer` or
`mill:mill-reviewer`, and relays the result back. The open question was whether forking
could replace or supplement that pattern, and in particular whether it would fix the
orchestrator context-bloat problem observed in mill-go.

The exploration answered both questions, and the answer to the second one is no. Fork
does **not** fix the bloat, because the bloat is not caused by cold-starting agents — it
is caused by mill-go's agent-mode output contract, which forces every sub-agent's entire
final message through the orchestrator's context *twice*. That defect is real,
independently confirmed, and is what this task actually fixes. Fork itself turns out to
fit exactly one place in mill.

**Why now:** a mill-go run was observed burning ~75k/200k tokens of orchestrator context
in a single task. Agent-mode dispatch is the shipped default (`dispatch: agent` in both
the hub config and the plugin template), and the subprocess/psmux paths are dead in
practice, so every mill task pays this cost on every dispatch.

## Scope

**In:**

- **A. Fork adoption at one site:** mill-start's Explore phase gains SKILL.md guidance
  **introducing** sub-investigation dispatch — today Phase: Explore, Step 3
  (`mill-start/SKILL.md:117-125`) tells the orchestrator to explore *directly* with
  Grep/Glob/git log and dispatches no agent at all. The new guidance names
  `Agent(subagent_type: "fork")` as the default for scoped sub-investigations that need
  the task context already in the orchestrator's head, and a cold `Explore` agent for
  broad mechanical sweeps.
- **B. Fix the agent-mode output contract** across **all** agent-mode dispatch sites
  (reviewers: discussion / plan / code; implementer; fixer; NIT-fixer; merge-in conflict
  resolver; merge-in verify-fix). The sub-agent writes its own `<brief>.out.md`; the
  orchestrator's `Write` step is deleted; the sub-agent's final message shrinks to a
  one-line ack, which also becomes mill-go's completion discriminator.
- **C. Grant `mill-reviewer` a `Write` capability**, guardrailed to `_mill/briefs/`, and
  sweep every file whose current instructions contradict the new contract — including the
  `<TOOL_RULE>` block injected from `_review_common.py`, which is not a template. See
  **"Authoritative edit set"** in Technical context for the enumerated list; that list is
  the only file count in this document.
- **D. Add `output_path` to every prepare envelope** and centralise the `.md` → `.out.md`
  rule in one helper owned by `write_brief`.
- **E. Add a missing-file guard** at the four finalize read sites (a missing `.out.md`
  currently raises an uncaught `FileNotFoundError`), and **remove the now-incorrect
  `html.unescape()` calls** at those same four sites.
- **F. A durable decision note** in `mill-go/SKILL.md`'s "## Agent-mode dispatch" section
  recording why fork is rejected for the scripted dispatch sites, so this is not
  re-litigated.

**Out:**

- Forking any scripted dispatch site (implementer / fixer / reviewer / merge-in). Rejected
  on the merits — see Decisions.
- Forking `mill-self-report`. Considered and rejected — see Decisions.
- Merging with the deferred `mill-orchestrator` task (id 0, Thread A/B split). It remains
  a separate, larger proposal. See Technical context for how the two relate.
- Deleting the `subprocess` / `psmux` dispatch paths. They are dead as a *configured*
  dispatch mode (`dispatch: agent` everywhere), but **`--stage full` is not dead**: it is
  still the reviewer's fallback after two consecutive raw API errors
  (`mill-go/SKILL.md:129`), so its prompt contract must keep working. See the
  `output-contract-is-agent-mode-only` Decision. Removing these paths is a separate task.
- Two unrelated bugs found while mapping (file these, don't fix here):
  `millpy-implement.py --stage prepare` never emits `start_sha` even though
  `mill-go/SKILL.md` step 6 says to thread `--start-sha` back into finalize; and
  `_agent_dispatch.resolve_dispatch_mode()` defaults to `"subprocess"` while both shipped
  configs set `agent`, so a hub missing an `llm.claude` block silently falls back to the
  `claude -p` path.

## Decisions

### fork-rejected-for-scripted-dispatch

- **Decision:** Do not use `subagent_type: "fork"` at any of mill's scripted dispatch
  sites (implementer, per-batch/holistic code review, fixer, NIT-fixer, discussion review,
  plan review, merge-in conflict resolver, merge-in verify-fix).
- **Rationale:** Fork's only real advantage over a fresh Agent is that the child inherits
  the parent's context and therefore needs no brief. (Its other advertised property —
  "the child's tool output stays out of the parent" — is **not** a differentiator: an
  ordinary fresh Agent call already behaves that way; only the final message returns.)
  Mill pays the brief-writing cost deliberately, and the brief is load-bearing for three
  things fork destroys, each independently disqualifying:
  1. **Per-role model tiers.** A fork always runs on the parent's model and **ignores a
     `model` override**. Mill assigns models per role: `roles.fixer.model: haiku`,
     `roles.implementer.model: sonnethigh`, `roles.discussion-review…reviewer: opushigh`.
     Forking the fixer silently promotes a Haiku fixer to whatever the orchestrator runs
     on.
  2. **The reviewer's read-only invariant.** `mill-reviewer` is granted only
     `Read, Grep, Glob` — it *cannot* edit source or run commands, by construction. A fork
     inherits the **parent's** tools, so a reviewer forked from mill-go would hold `Edit`,
     `Write`, and `Bash`. The safety property evaporates.
  3. **Crash-safe resume.** The brief is a committed git artifact; `--stage prepare` writes
     it, commits state, and pushes, so a dead session resumes cleanly. A fork's "brief" is
     the parent's in-memory context — not on disk, not reconstructible after a crash.
     Every state-mutating dispatch depends on this.
  A fourth, softer reason applies to reviewers specifically: **review independence.** A
  forked reviewer inherits the author's reasoning, including the rationalizations review
  exists to catch. Discussion review and plan review must not be warm-context.
- **Rejected:** Adding a fourth `fork` dispatch mode. It would trade away model tiers, the
  reviewer tool grant, and resumability for a saving (brief composition) that mill wants
  to keep paying.

### fork-adopted-in-mill-start-explore

- **Decision:** Add guidance (not a mandate) to `mill-start`'s Phase: Explore, Step 3
  (`mill-start/SKILL.md:117-125`). Note this **introduces** sub-investigation dispatch:
  Step 3 currently instructs the orchestrator to explore *directly* ("use file structure,
  `git log`, and `Grep` / `Glob`") and names no Agent dispatch whatsoever, so there is no
  existing cold-agent practice being replaced. The new text says: prefer
  `Agent(subagent_type: "fork")` for scoped sub-investigations that need the task context
  already in the orchestrator's head; use a cold `Explore` agent for broad mechanical
  sweeps; explore inline when the question is small.
- **Rationale:** This is the one place in mill with no brief, no resume requirement, no
  per-role model tier, and no tool restriction to lose — so none of the three
  disqualifiers apply. It is also fork's documented use case ("use a fork when a named
  subagent would need too much background to be useful"). The orchestrator at that point
  holds the task body, the scope digest, and the repo conventions; a fork inherits all of
  it for free and explores better-informed, while its file-reading tool output still stays
  out of the parent's context.
- **Rejected:** Mandating fork for all Explore sub-agents (a broad mechanical sweep does
  not benefit from the inherited context and would pay the parent's prefix on every turn);
  and no change at all (leaves a free quality win on the table).

### no-fork-for-mill-self-report

- **Decision:** Leave `mill-self-report` running in the orchestrator's own context.
- **Rationale:** It was the strongest remaining candidate — its job is literally "scan your
  session memory", so it is the one skill that *cannot* be delegated to a cold agent, and
  fork is the only mechanism that would make it delegatable. But it fires as the **last**
  step of Handoff, so context reclaimed there is nearly worthless, and the parent has to
  block on the fork anyway. Adding a dispatch mechanism for a marginal gain is not worth
  the complexity.
- **Rejected:** Forking it to protect against auto-compact destroying the session memory
  it needs. Real but speculative; revisit if it is ever observed.

### output-contract-is-agent-mode-only

- **Decision:** The write-your-own-`.out.md` contract applies **only to agent-mode
  dispatch**. The `--stage full` LLM-provider path keeps today's behaviour verbatim: the
  reviewer returns its review **as text** and the backend writes the file.
- **Why this must be said out loud:** the `subprocess` path is **not entirely dead**, and
  the earlier "subprocess/psmux are dead in practice" framing was too broad.
  `mill-go/SKILL.md:129` explicitly **retains `--stage full` via `millpy-bg` as the reviewer's
  fallback after two consecutive raw API errors**. The five review templates and the
  `<TOOL_RULE>` block are **shared** between both channels, so a naively-global contract
  change would tell a `--stage full` reviewer to `Write` a file it has no path for
  (`<OUTPUT_FILE>` is never substituted on that path, since `--stage full` never calls
  `write_brief`) and no permission to write (`_llm_claude.py:80` grants at most
  `Read,Grep,Glob`, and a `tooluse: false` spec grants none).
- **How the split is enforced, mechanically:**
  - The **output-contract footer** (the `<OUTPUT_FILE>` path + the ack instruction) is
    appended by `write_brief`, which is called **only** from `--stage prepare`. The
    `--stage full` path builds `prompt_text` and hands it straight to the LLM provider
    without ever calling `write_brief`. So the footer is agent-mode-only *by construction* —
    no conditional needed.
  - The **`<TOOL_RULE>` block is the problem**, because it lives in shared prompt text and
    hardcodes the opposite rule (see below). `build_tool_rule` must therefore become
    dispatch-aware: it takes the existing `mode` (`bulk` / `tool-use`) **plus** a flag for
    agent-mode dispatch, **defaulting to `False` (non-agent)** — mirroring `prepare()`.
    The default is load-bearing, not cosmetic: `test-review-common.py` calls
    `build_tool_rule` **positionally with one argument** at seven sites (`:615`, `:652`,
    `:690`, `:691`, `:695`, `:2828`, `:2880`), so a *required* second parameter would raise
    `TypeError` in all seven. With the `False` default they stay green, because the two
    non-agent cells are specified as byte-identical to today's text. `test-review-common.py`
    therefore does **not** belong in Group 6.
    **`<TOOL_RULE>` also becomes the sole owner of the read-only clause**, since Group 2's
    static header surrenders it (see the edit set).
- **All four cells of the `build_tool_rule` matrix must be defined — the `bulk` × agent-mode
  cell is the trap.** `mode` derives from the reviewer spec's `tooluse` flag, which
  **defaults to `False`** (`_reviewers.py:386`), and the registry ships `*_bulk`
  (`tooluse: false`) variants selectable as any role's `reviewer` — so `bulk` × agent-mode is
  reachable today, not hypothetical. `_TOOL_RULE_BULK` currently opens with *"Do NOT request
  tool calls. All content you need is in this prompt."*, which under agent-mode dispatch
  would coexist with "You MAY use Write" — a self-contradiction that would plausibly yield
  **no `.out.md` and an `ERROR` envelope every round**. The four cells:

  | | `--stage full` (non-agent) | agent-mode |
  |---|---|---|
  | **bulk** | Unchanged: "Do NOT request tool calls. All content is in this prompt. Do NOT use Write. Return review as text." | "Do NOT request tool calls **to gather content** — everything you need is in this prompt. **The single exception:** you MUST use `Write` exactly once, to write your report to the file named in this brief. Do NOT use `Edit`, and do NOT run git or bash." |
  | **tool-use** | Unchanged: "You MAY use Read, Grep, Glob to verify claims. Do NOT use Write, Edit, or run git/bash. Return review as text." | "You MAY use Read, Grep, Glob to verify claims. You MAY use `Write` **only** to write your report to the file named in this brief. Do NOT use `Edit`, and do NOT run git or bash." |

  Both agent-mode cells refer to the report file **by description, never by a `<TOKEN>`** —
  the literal path arrives in `write_brief`'s footer (see the `<OUTPUT_FILE>` constraint under
  `output-path-in-prepare-envelope`). Both agent-mode cells retain the existing "Review-only,
  findings only" and "Do NOT read `reviews/`" clauses verbatim.
- **Who sets that flag (the obvious answer is wrong, so state it):** **not** inside
  `prepare()`. `build_tool_rule` is called *from within* `prepare()` in
  `_review_discussion.py:82` and `_review_code.py:335` — and `run()` (the `--stage full`
  fallback, `_review_discussion.py:181`, `_review_code.py:588`) calls **that same
  `prepare()`**. Defaulting the flag to `True` inside `prepare()` would therefore poison the
  exact path this Decision exists to protect. Instead: the flag is a **parameter on each
  backend's `prepare()`, defaulting to `False` (non-agent)**, and it is set `True` **only**
  by the CLIs' `--stage prepare` branches. `_review_plan.py` is **asymmetric** and needs
  individual attention — its `build_tool_rule` calls are spread across four sites, and only
  two of them are agent-reachable:
  - `prepare()` (`:401` batch-scope, `:490` holistic-scope) — **both carry the flag.**
    `prepare()` takes `scope: str | None`, so a batch-scope prepare is reachable even though
    the hub config disables plan batch review today (`rounds: 0`); thread the flag through
    both callsites rather than relying on config that could change.
  - `run()` (`:836`) and `_review_one_batch` (`:196`) — **both keep the non-agent rule.**
    `_review_one_batch` is *not* a separate entry point: it is submitted to a
    `ThreadPoolExecutor` from `run()` (`_review_plan.py:752`), so it is reachable only on the
    `--stage full` path. **Do not thread the agent-mode flag into it.**
- **Rejected:** Treating subprocess as fully dead and changing the shared prompt text
  globally — it would silently break the one path that exists to rescue a reviewer when the
  Agent API is failing, i.e. exactly when you least want a second failure.

### subagent-writes-its-own-out-md

- **Decision:** Every agent-mode sub-agent writes its **own** `<brief>.out.md`. The
  orchestrator's "capture output" `Write` step (`mill-go/SKILL.md:149`) is **deleted**.
  `--stage finalize` continues to read `--agent-output <brief>.out.md` exactly as it does
  today, so the finalize contract is unchanged.
- **Rationale:** This is the actual context-bloat fix. Today `mill-go/SKILL.md:123` makes
  the orchestrator read the sub-agent's **entire** final message out of the
  `<task-notification>`, and `:149` makes it **write that whole thing back out** to
  `.out.md`. A full reviewer output — thousands of lines of findings — therefore lands in
  the Builder's context *twice*, even though `:376` and `:820` explicitly forbid the
  Builder from acting on findings. The subprocess path never did this: the worker wrote
  the review file itself and the Builder grepped one JSON line out of a log. **Agent mode
  regressed relative to subprocess mode**; this restores parity.
- **Rejected:** Reviewers-only scope (implementers and fixers bloat the Builder too, and a
  single uniform contract is simpler than two); and fork (a fork's final message also
  returns as a tool result, so it fixes nothing here).

### one-line-ack-as-final-message

- **Decision:** The sub-agent's final message becomes a single-line ack —
  `WROTE <abs path to .out.md>`. The orchestrator neither needs nor reads content from
  it; the verdict/status reaches the Builder via `finalize`'s stdout JSON envelope, as it
  already does.
- **Rationale:** Deleting the `Write` step alone only halves the bloat — the notification
  payload is the other half, and it arrives in the Builder's context whether or not the
  Builder does anything with it. Shrinking the final message is what actually reclaims the
  budget.
- **Rejected:** Returning the one-line JSON verdict as the final message (a redundant
  cross-check with `finalize`, and it invites the Builder to start trusting a channel it
  is supposed to ignore); keeping the full output as the final message (halves the fix).

### ack-is-the-completion-discriminator

- **Decision:** The presence of the `WROTE <path>` ack in the notification payload is
  mill-go's discriminator for "the agent completed its protocol". The step-4 classifier
  becomes:
  - payload contains a raw API/infrastructure error marker → `stuck_type: transient`,
    one-retry path — **unchanged** (step 4(a));
  - payload contains the ack → the agent finished and wrote its `.out.md` → go straight to
    `finalize` (step 6), which decides `success` / `incomplete` / verify-stuck exactly as
    it does today;
  - payload contains **neither** → the agent died or exhausted its turn *before* writing
    the file. Split by role, because step 4(b) is scoped to **implementer** dispatches only
    (`mill-go/SKILL.md:131`):
    - *implementer* → the existing step-4(b) split applies unchanged (stopped/interrupted →
      `TaskOutput` liveness probe; clean turn-exhaustion → Clean mid-work stop);
    - *reviewer / fixer* → these have no 4(b) branch (today step 5 simply captured whatever
      text arrived, so the case was never named). They fall through to `finalize`, which
      runs against a missing `.out.md`: reviewers emit the existing `ERROR` envelope, fixers
      take the git-state inference. Step 4(c)'s stopped/interrupted liveness probe for
      reviewer/fixer is unaffected and still runs first.
    In all cases the subsequent `finalize` call runs with **no** `.out.md`, which routes
    into `missing-out-md-defers-to-git-state` below.
- **Rationale:** This is a **blocking prerequisite**, not a nicety. `mill-go/SKILL.md:132`
  currently defines clean turn-exhaustion as "the notification is a non-error, **non-JSON**
  message". A one-line `WROTE <path>` ack is *precisely* a non-error, non-JSON message — so
  without a new discriminator, **every successful implementer dispatch would be
  misclassified as turn-exhausted**. The ack must be a *positive* success marker, not just
  a smaller payload.
- **Affected edits in `mill-go/SKILL.md`:**
  - **`:123`** — says "Read the subagent's final message from the notification payload —
    that is the text used in steps 4 and 5 below". Step 5 is deleted, so this is stale and
    still instructs reading the full message. Reword to "…used in step 4's classification
    only".
  - **step 4(a)** (`:129`) — reworded to key **solely on the error marker**, with the ack
    test evaluated **first**. Its current heuristic ("roughly 0 tokens, no `MILL_REVIEW`
    block and no `status` JSON") becomes actively misleading post-change, because *every
    successful* payload is now ~0 tokens with no review block and no JSON. Only the
    error-marker clause still discriminates; the negative signals must go.
  - **step 4(b)** (`:131-133`) — the clean-turn-exhaustion trigger is redefined as
    "no ack **and** no error marker", instead of "non-error, non-JSON".
  - **step 5** (`:149`) — deleted (the orchestrator no longer captures output).
  - **step 6** (`:151`) — takes `--agent-output` from the envelope's `output_path`.
  - **step 6.5, the warm-`SendMessage` resume** (`:161`, `:163`) — **easy to miss, and it
    would silently re-bloat the Builder.** `:161`'s message literally tells the resumed
    implementer to "emit the required JSON report as your final line", and `:163` tells the
    orchestrator to write that message to `.out.md`. Left alone, a warm-resumed implementer
    returns a full JSON report *in chat* and its payload matches no ack. New wording:
    "Finish any remaining cards in this batch, run verify, rewrite your report file, then
    reply with the ack." The re-capture instruction at `:163` is deleted. **This path
    bypasses prepare**, so `write_brief` never runs and cannot truncate the stale `.out.md` —
    the orchestrator must therefore delete `.out.md` itself (one `rm -f`) **before** sending
    the resume message. See `write-brief-truncates-stale-out-md`.
  - **Clean mid-work stop** (`:135`) — today says "write the notification to the `.out.md`
    file as normal"; under the new contract there is nothing to write, and finalize runs
    against a missing file (see `missing-out-md-defers-to-git-state`).
- **Rejected:** Making the ack a JSON object so the existing "non-JSON" test keeps working.
  It preserves the classifiers untouched, but re-admits a JSON channel the Builder is
  supposed to ignore and contradicts the one-line-ack decision.

### output-path-in-prepare-envelope

- **Decision:** Every prepare envelope **that dispatches an agent** gains an **additive**
  `output_path` field holding the absolute path to the `.out.md`. The `.md` → `.out.md` rule
  lives in exactly one helper in `_agent_dispatch.py`.
- **Explicit carve-outs — three kinds of envelope carry no `output_path`,** because none of
  them writes a brief. The invariant is "`output_path` is present on every **brief-emitting
  success** envelope", and the shape test must be scoped to exactly that:
  1. **`dispatch_needed: false`** — `_implementer_common.emit_prepare_no_dispatch` (`:796`),
     emitted for the merge-in verify-fix pass case (`millpy-merge-in-subagent.py:396`) where
     verify already passes and **no agent is dispatched at all**.
  2. **The plan-validator failure envelope** — `millpy-review-plan.py:142-147` emits
     `{"errors": [...], "summary": ...}` from its `--stage prepare` branch and exits 1
     *before* any brief is rendered (consumed by `mill-plan/SKILL.md:158-159`).
  3. **`print_error_envelope`** — all three review CLIs emit it from the `--stage prepare`
     branch on `ReviewError`.
  A blanket "always present" assertion fails on all three.
- **Who substitutes what (this must be explicit, or the design is unbuildable):**
  `write_brief` is the **sole owner** of the output path. It already computes `brief_path`
  internally (`_agent_dispatch.py:96-120`) and writes the fully-rendered brief during
  `--stage prepare`, *before the orchestrator ever sees the envelope*. So `write_brief`
  derives the `.out.md` path from the `brief_path` it just computed, **appends the
  output-contract footer** (carrying the literal absolute path) to the already-rendered
  `prompt_text`, and returns both paths. The envelope's `output_path` is a **read-only echo**
  of that same helper's result, which the orchestrator forwards verbatim to
  `--agent-output`. The orchestrator never derives a path — it *cannot*, since the brief is
  already written by then.
- **No `<OUTPUT_FILE>` token in any template — this is a hard constraint, not a preference.**
  `_render.render` (`_render.py:35`) matches `<[A-Z][A-Z0-9_]*>` and **raises
  `KeyError: Unresolved template tokens`** for any such token missing from the caller's
  `values` dict. Every brief and review prompt is rendered through it
  (`millpy-implement.py:533`, `millpy-fix.py:402,468`, `millpy-merge-in-subagent.py:339,418`,
  `_review_common.py:1359`). So a literal `<OUTPUT_FILE>` placed in a template would
  hard-fail rendering **before** `write_brief` — the sole owner of the path — ever runs. It
  is also unsuppliable on the `--stage full` path, which renders the same review templates
  and has no brief path at all. Therefore:
  - **Templates become channel-neutral.** Group 2 and Group 3 templates are reworded from
    "your last line of **output** MUST be a single JSON object" to "your **report** must end
    with a single JSON object as its last line" — a statement true on *both* channels.
  - **The footer defines the channel, and only `write_brief` writes it.** It carries the
    resolved absolute path as literal text (never `<TOKEN>` grammar): "Write your full report
    to `<abs path>`. Your final message must be exactly `WROTE <abs path>`." Appended after
    rendering, so `_render` never sees it; absent on `--stage full`, which never calls
    `write_brief`.
- **Rationale:** The rule is currently restated as prose in four separate places in
  `mill-go/SKILL.md` (`:135`, `:149`, `:151`, and the warm-`SendMessage` path at `:163`).
  Under the new contract a further party — the sub-agent itself — also needs the path. One
  helper, one envelope field, zero string-munging in prose. The field is additive, so the
  "finalize's external contract must not change" constraint holds.
- **Rejected:** Keeping the `.md` → `.out.md` munging rule as SKILL.md prose; having the
  orchestrator substitute `<OUTPUT_FILE>` (impossible — the brief is already on disk).

### reviewer-write-grant-scoped-to-briefs

- **Decision:** Add `Write` to `mill-reviewer`'s tool list. Restrict it to `_mill/briefs/`
  by a **prompt guardrail** in the agent definition (naming the report file by description)
  plus the explicit absolute path in `write_brief`'s footer. The reviewer writes **only** its
  own `.out.md`.
- **Rationale:** Narrowest grant that makes the new contract work. The reviewer does *not*
  need to write the review file — `finalize` still owns `_mill/reviews/` and renders it
  from `.out.md`. `mill-implementer` already has `Write`, so only `mill-reviewer`'s
  definition changes.
- **Honest limitation (do not paper over this):** agent-definition `tools:` frontmatter
  grants capabilities **wholesale, with no path scoping**. Adding `Write` therefore grants
  it **repo-wide**, and "the reviewer cannot touch source code or git" degrades from a
  *construction-level invariant* to a *prompt instruction*. That is a real, if small,
  weakening: today the reviewer is incapable of writing; afterwards it is merely instructed
  not to. Accepted because the reviewer has no motive, the brief names one exact absolute
  path, and it still holds no `Bash` and no `Edit` (so it cannot commit, run commands, or
  modify existing files — only create/overwrite by full path).
- **Considered for the plan, not decided here:** a plugin-shipped `PreToolUse` hook denying
  `Write` outside `_mill/briefs/` for the `mill-reviewer` agent would restore genuine
  enforcement. Left out of scope to keep the change reviewable, but it is the correct
  follow-up if the advisory guardrail ever proves insufficient. The plan should note it,
  not silently assume the guardrail is airtight.
- **Rejected:** Granting `_mill/reviews/` too and making `finalize` a pure parser — more
  moving parts, wider grant, no benefit.

### write-brief-truncates-stale-out-md

- **Decision:** `write_brief` **deletes any pre-existing `.out.md`** (`unlink(missing_ok=True)`)
  at brief-write time, and the warm-`SendMessage` resume path — which **bypasses prepare**, so
  `write_brief` never runs — deletes it explicitly before sending the resume message. A dead
  agent therefore always yields a genuinely **absent** file, never a stale one.
- **Rationale — this is a hole the change itself opens.** Today the orchestrator rewrites
  `<brief>.out.md` immediately before every `finalize` (`mill-go/SKILL.md:149`, `:163`), so the
  file is **always fresh by construction**. Deleting that `Write` silently destroys that
  invariant, and **nothing anywhere in `scripts/` unlinks or truncates `.out.md`** (verified).
  Both recovery paths reuse the same role/scope/round — and therefore the **same `.out.md`
  path**: step 4(a)'s transient retry ("re-dispatch once immediately using a fresh brief and
  session") and step 6.5's warm resume. So if attempt 1 writes the file and attempt 2 dies
  before writing, `finalize` reads **attempt 1's output as attempt 2's result**. The
  missing-file guard does not save us: it covers *absent* and *empty*, not *stale*.
- **Why this is severe for reviewers specifically:** the git-state completeness recount is a
  genuine backstop for implementer/fixer/merge-in — a bogus report still gets reconciled
  against actual commits. **Reviewers have no such backstop.** The review CLIs parse the
  verdict straight out of the file text, so a killed-then-retried reviewer that had written
  `APPROVE` before dying would hand mill-start or mill-plan a **green verdict that no live
  reviewer produced**. That is precisely the false-success class this design guards against
  everywhere else (#574).
- **Rejected:** An mtime freshness check (`.out.md` newer than the brief) at the read sites —
  it works, but it is clock-dependent and fails silently on coarse filesystem timestamps;
  deterministic deletion is strictly better. Relying on the agent to always overwrite the file
  — that assumption is exactly what fails when the agent dies.

### missing-out-md-defers-to-git-state

- **Decision:** A missing or empty `.out.md` is handled **per role**. An *empty* file
  already degrades correctly today; a *missing* one does **not** — it crashes. So this
  change must add a **missing-file guard** at all four finalize read sites, which is what
  makes the rest of the rule true:
  - **New guard (in scope, must be built):** each of the four read sites —
    `_implementer_common.py:892`, `millpy-review-discussion.py:146`,
    `millpy-review-plan.py:185`, `millpy-review-code.py:183` — reads the file **defensively,
    yielding `""` when it does not exist**. Today they all call
    `Path(agent_output_path).read_text(...)` with **no existence guard**, so an absent file
    raises an uncaught `FileNotFoundError`: `millpy-implement.py:402` calls
    `finalize_from_output` with no `try`, and the three review CLIs wrap the read in
    `except ReviewError` only — which `FileNotFoundError` does not satisfy. The CLI would
    exit with a traceback and print no envelope at all. This guard collapses *missing* into
    the *empty* case, after which:
  - **implementer / fixer / merge-in finalize:** the (now-empty) text flows into the
    **existing** no-JSON git-state inference (`_implementer_common.py:999`,
    `_batch_completeness_stuck`). The completeness recount runs as it does today, yielding
    `success` (all cards committed, tree clean), `stuck_type: incomplete`
    (some-but-not-all cards committed), or `stuck_type: logic` ("no structured report",
    when there is no commit evidence *and* no report).
  - **review CLIs (discussion / plan / code):** there is no git state to infer from, so the
    empty text fails `parse_verdict`, raising `ReviewError`, which produces the **existing**
    `verdict: ERROR` envelope. That already feeds mill-start's and mill-plan's
    ERROR-only-aggregate retry (their step 3.5) and mill-go's reviewer fallback path.
- **Rationale (guard):** without it, the one failure mode the new contract *introduces* — a
  dead agent leaving no file — is the one failure mode `finalize` cannot survive. "Reuse
  existing machinery" is only true *downstream* of the guard; claiming the existing code
  already covers a missing file was wrong.
- **Rationale (classification):** This corrects a **dangerous** earlier draft of this decision, which said
  "missing/empty `.out.md` → `stuck_type: transient`" unconditionally. That would have been
  a regression, not a fix. `mill-go/SKILL.md:135` deliberately routes a turn-exhausted
  implementer *through* `finalize` precisely so the git-state inference can reclassify it
  as `incomplete`. A blanket `transient` short-circuits that inference and drops a partial
  batch onto the transient retry path's `commits_made > 0` skip-to-cleanliness route —
  which `mill-go/SKILL.md:137` names explicitly as **the #574 false-success bug**. The
  whole point of the `incomplete` classification is that remaining cards must be finished,
  never silently accepted as complete. The new contract must not weaken that, and the
  correct reading is that a missing `.out.md` is *less* information than an empty one, not
  a different kind of failure.
- **Rejected:** Blanket `stuck_type: transient` (reintroduces #574 — see above); a synthetic
  `transient` envelope for the review CLIs (a new code path where the existing `ERROR`
  envelope already does the job); and having the orchestrator stat the file before calling
  `finalize` (duplicates logic `finalize` owns, and adds a step to the hot path).

### remove-html-unescape

- **Decision:** Delete the `html.unescape()` call at all four finalize read sites
  (`millpy-review-code.py:183`, `millpy-review-plan.py:185`,
  `millpy-review-discussion.py:146`, `_implementer_common.py:892`). **Drop the now-unused
  `import html` in each of the four files with it** — otherwise the change leaves four
  lint-visible dead imports.
- **Rationale:** Those calls exist because the harness HTML-escapes the
  `<task-notification>` payload before delivery (fix #605), and the orchestrator was
  writing that escaped payload to `.out.md`. Once the **agent** writes the file directly,
  the content is never HTML-escaped — and unescaping it anyway would **corrupt** any
  literal `&lt;`, `&gt;`, or `&amp;` appearing inside quoted source code in a finding.
  Leaving these in trades a token bug for a correctness bug.
- **Rejected:** Leaving them as defensive no-ops. They are not no-ops; they are actively
  destructive on legitimate content.

### decision-note-for-fork-rejection

- **Decision:** Record the fork rejection durably as a short subsection — "Why not fork?" —
  at the **end of `plugins/mill/skills/mill-go/SKILL.md`'s `## Agent-mode dispatch`
  section**, not only in this `discussion.md` (which lives on a task branch and is
  squash-merged into history where nobody will find it).
- **Content (roughly six lines):** fork inherits the parent's context but (1) always runs on
  the parent's model and ignores a `model` override, breaking `roles.*.model` tiers;
  (2) inherits the *parent's* tools, so a forked reviewer would hold `Edit`/`Write`/`Bash`
  and lose its read-only guarantee; (3) has no on-disk brief, so a forked dispatch cannot
  be resumed after a crash. Fork is therefore used only in mill-start's Explore phase,
  where none of the three apply.
- **Rationale:** "Why don't we just fork the reviewer?" is a question that will recur, and
  `## Agent-mode dispatch` is exactly where the next person will be standing when they ask
  it. Putting it there needs no new docs convention (the repo has no `docs/decisions/`) and
  costs one subsection.
- **Rejected:** Relying on `discussion.md` alone; inventing a new ADR directory for a single
  note.

## Technical context

**Dispatch inventory.** Mill has 12 sub-agent / background-LLM dispatch sites. The ones in
scope for the output-contract fix are the agent-mode ones:

| Site | Skill / script | Agent | Brief template |
|---|---|---|---|
| Per-batch implementer | `mill-go` §1 → `millpy-implement.py` | `mill:mill-implementer` | `implementer-brief.md` |
| Per-batch code review | `mill-go` §3 → `millpy-review-code.py --batch` | `mill:mill-reviewer` | `review-code-batch.md` |
| Holistic code review | `mill-go` → `millpy-review-code.py` | `mill:mill-reviewer` | `review-code-holistic.md` |
| Per-batch fixer / NIT-fixer | `mill-go` §3 → `millpy-fix.py --scope batch` | `mill:mill-implementer` | `fixer-batch-brief.md` |
| Holistic fixer | `mill-go` → `millpy-fix.py --scope holistic` | `mill:mill-implementer` | `fixer-holistic-brief.md` |
| Discussion review | `mill-start` → `millpy-review-discussion.py` | `mill:mill-reviewer` | `review-discussion.md` |
| Plan review | `mill-plan` → `millpy-review-plan.py --holistic-only` | `mill:mill-reviewer` | `review-plan-{batch,holistic}.md` |
| Merge-in conflicts | `mill-merge-in` → `millpy-merge-in-subagent.py --mode conflicts` | `mill:mill-implementer` | `merge-in-conflict-brief.md` |
| Merge-in verify-fix | `mill-merge-in` → `millpy-merge-in-subagent.py --mode verify-fix` | `mill:mill-implementer` | `merge-in-verify-brief.md` |

**The dispatch protocol** is documented once, in `plugins/mill/skills/mill-go/SKILL.md`
§"## Agent-mode dispatch" (lines ~105–175); every other skill points at it. It is a
three-step prepare → Agent → finalize pattern:

- `--stage prepare` renders the brief via `_agent_dispatch.write_brief()` and emits a JSON
  envelope: `{stage, brief_path, subagent_type, model, session_id, role, scope, round,
  start_sha?, nits_only?}`.
- The orchestrator calls the `Agent` tool with `prompt: "Read this file and follow the
  instructions exactly: <brief_path>"`, then waits for the `<task-notification>`.
- **Step 5 (`:149`) — the defect:** "Write the message captured from the
  `<task-notification>` to `<brief_path>.out.md`."
- `--stage finalize --agent-output <brief>.out.md` parses the file and emits the verdict /
  status JSON that the Builder actually consumes.

**Single choke point for the brief change.** Every brief in mill — implementer, fixer,
merge-in, and all five review prompts — is written through
`_agent_dispatch.write_brief(briefs_dir, role, scope, round_n, prompt_text)`
(`_agent_dispatch.py:96-120`). Appending the output-contract directive there covers all
nine dispatch sites uniformly, instead of hand-editing ten templates. The `.out.md` path is
mechanically derivable from `brief_path` (replace the trailing `.md`); a small helper
alongside `write_brief` owns that rule, and `output_path` is emitted in the prepare envelope
so nobody downstream re-derives it (see the `output-path-in-prepare-envelope` Decision).

**What an `.out.md` must contain.** Unchanged from what the agent emits today, only
redirected: the agent's **full report**, ending with the trailing status/verdict block it
already produces. For implementer / fixer / merge-in that is the report text plus the
single status JSON object as the file's last line — `_extract_status_json`
(`_implementer_common.py:914+`) parses it out of that file, so the JSON must survive. For
reviewers it is the whole `MILL_REVIEW_BEGIN … MILL_REVIEW_END` block including the fenced
yaml verdict and the `## Findings` body, which `finalize` renders into `_mill/reviews/`.
**Only the delivery channel changes** — the report goes to the file instead of the chat, and
the final message becomes the ack.

**Authoritative edit set — 29 files (2 + 5 + 5 + 3 + 9 + 5).** This is the **single**
enumerated list, and the only file count in this document; the conformance test in Testing
asserts against it. Every file in groups 1–3 currently tells the sub-agent that its final
*message* is its output, contradicting the new contract.

*Group 1 — agent definitions (2 files):*

- `plugins/mill/agents/mill-reviewer.md` — "Your sole output is your final message. Do not
  create intermediate files…" must go; tool list gains `Write`; add the `_mill/briefs/`
  guardrail.
- `plugins/mill/agents/mill-implementer.md:20` — "report structured status when done" names
  **no channel**, which under the new contract reads as "in your final message" — the same
  ambiguity being swept out of the reviewer definition. Reword to say the report is **written
  to the report file named in the brief**, and the final message is the ack. **Do not write a
  literal `<OUTPUT_FILE>` here:** agent definitions are static text and never pass through
  `_render`, so the token would reach the model unsubstituted. Name the file *by description*
  only. (Its tool list already has `Write`; no capability change.)

*Group 2 — the five review templates (5 files):*

- `plugins/mill/templates/review-{code-batch,code-holistic,discussion,plan-batch,plan-holistic}.md`.
  **The contradiction here is the static READ-ONLY header, not a JSON clause.** All five open
  with identical prose (`review-discussion.md:1-4` and the same at `review-code-batch.md:1-4`
  et al.): *"You are a READ-ONLY reviewer. You MUST NOT call Edit, **Write**, Bash, or any
  tool that modifies files or runs commands. You MUST NOT make git commits. **Your sole
  output is the review file in the format below.**"* That directly contradicts the agent-mode
  footer. It is **static template prose on a shared channel, so unlike `<TOOL_RULE>` it
  cannot be made dispatch-aware.** Resolution:
  - **Delete the tool prohibitions from the header** (the `Edit` / `Write` / `Bash` / no-git
    clause) and let the **dispatch-aware `build_tool_rule` own the entire read-only clause** —
    it is the only channel-aware injection point in the review prompt, so all tool
    permissions must live there and nowhere else.
  - **Keep** the non-tool half of the header: "You are an independent reviewer. REPORT
    issues; do NOT fix them."
  - **Keep the `MILL_REVIEW_BEGIN` … `MILL_REVIEW_END` wrapper and the review format** — that
    is the *content format of the `.out.md` file*, which `finalize` parses. Only the sentence
    "Your sole output is the review file in the format below" changes, to say the report is
    **written to** the file named in the brief, and the final message is the ack.
  - **Also sweep the "source-grounding" paragraph** (`review-discussion.md:21` and its
    counterparts), which statically asserts *"You are in tool-use mode — … open it with
    Read/Grep/Glob"*. That is a **tool statement outside `build_tool_rule`**, and it is
    **already wrong today** for a `bulk` reviewer (which is told the opposite two paragraphs
    earlier). Fold the mode-specific clause into `build_tool_rule` and leave the paragraph
    with only its channel-neutral half ("Never fabricate file contents or code behaviour you
    have not actually read"). This is a pre-existing bug the sweep fixes for free.
  - Note the earlier draft of this entry prescribed rewording "your last line of output MUST
    be a single JSON object" — **that sentence does not exist in any review template**; it
    belongs to Group 3. Do not go looking for it here.

*Group 3 — the five non-review brief templates (5 files):*

- Each mandates "Your last line of **output** (after all work and commits) MUST be a single
  JSON object" and calls anything else a protocol violation: `implementer-brief.md:102,:127`,
  `fixer-batch-brief.md:70,:95`, `fixer-holistic-brief.md:76,:101`,
  `merge-in-conflict-brief.md:56`, `merge-in-verify-brief.md:45`. Reword to the
  **channel-neutral** form — "your **report** must end with a single JSON object as its last
  line" — which is true on both the agent-mode and `--stage full` channels. **Do not
  introduce an `<OUTPUT_FILE>` token here**; the channel is named by `write_brief`'s footer.
  `implementer-brief.md:50` additionally defines a mid-batch turn end as a protocol violation
  — that rule **stays**, but its "and the JSON report has been emitted" clause becomes "and
  the report has been written".

*Group 4 — orchestrator skills (3 files):*

- `plugins/mill/skills/mill-go/SKILL.md` — steps 4(a), 4(b), 5 (deleted), 6, 6.5 (`:161`,
  `:163`), and the Clean mid-work stop paragraph at `:135`. Plus the new "Why not fork?"
  subsection (Decision `decision-note-for-fork-rejection`).
- `plugins/mill/skills/mill-start/SKILL.md` — Phase: Explore Step 3 (`:117-125`) gains the
  fork guidance (item A); and the stale rationale at `:152` (see below).
- `plugins/mill/skills/mill-plan/SKILL.md` — the stale rationale at `:111` (see below).

*Group 5 — Python (9 files):*

- `_agent_dispatch.py` — `write_brief` owns the `.md` → `.out.md` helper, **appends** the
  output-contract footer (literal absolute path, no token), **unlinks any stale `.out.md`**,
  and returns both paths.
- **`_review_discussion.py`, `_review_code.py`, `_review_plan.py`** — the three review
  backends. Each calls `build_tool_rule` and so must thread the new agent-mode flag through
  its `prepare()` signature (`_review_discussion.py:82`, `_review_code.py:335`,
  `_review_plan.py:196,401,490,836`). `_review_plan.py` is the asymmetric one — see the
  `output-contract-is-agent-mode-only` Decision.
- **`_review_common.py`** — **the easiest file in this whole change to miss, because the
  contradiction is injected from Python, not from a template.** `_TOOL_RULE_BULK` and
  `_TOOL_RULE_TOOL_USE` (`:1216-1228`) hardcode
  `**CRITICAL: Do NOT use Write. Return review as text.**`, and `build_tool_rule` (`:1231`)
  feeds that into **every** review prompt — called from `_review_discussion.py:82`,
  `_review_plan.py:196,401,490,836`, and `_review_code.py:335`. It must become
  dispatch-aware per the `output-contract-is-agent-mode-only` Decision. Note its docstring
  also asserts "Write, Edit, and shell access are forbidden in both modes — the backend owns
  file writes and git", which stops being true for agent mode.
- `_implementer_common.py` — `emit_prepare` gains `output_path`; read site `:892` gains the
  missing-file guard and loses `html.unescape`.
- `millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py` — build
  their prepare envelopes inline, so each gains `output_path`; each sets the agent-mode flag
  `True` in its `--stage prepare` branch **only**; and read sites `:146` / `:185` / `:183`
  gain the missing-file guard and lose `html.unescape`.

**Explicitly *not* in the edit set** (checked, and worth recording so the plan does not
create empty batches): `millpy-implement.py`, `millpy-fix.py`, and
`millpy-merge-in-subagent.py` need **no** changes for `output_path`. They do not construct
envelopes — they call `_implementer_common.emit_prepare` (`millpy-implement.py:578`,
`millpy-fix.py:507`, `millpy-merge-in-subagent.py:350,431`), which builds the envelope
itself, so adding the field inside `emit_prepare` covers all three. Likewise the
missing-file guard lives inside `finalize_from_output`, not at their call sites.

*Group 6 — existing tests that pin the old behaviour (5 files). These go red if untouched:*

- **`unit_tests/test-agents-defs.py:60-69`** — asserts `mill-reviewer`'s tools are
  **exactly** `{Read, Grep, Glob}` and that none of `{Edit, Write, Bash, NotebookEdit}` is
  present. Granting `Write` turns this red. **This test *is* the reviewer safety invariant,
  not incidental scaffolding** — do not weaken it to a subset check. New assertion: exactly
  `{Read, Grep, Glob, Write}`, with `Edit`, `Bash`, and `NotebookEdit` still forbidden. That
  keeps the test doing its real job (the reviewer cannot commit, run commands, or modify
  existing files) while admitting the one new capability.

- `unit_tests/test-implementer-common.py:3131-3172` (case 63) — asserts
  `finalize_from_output` **unescapes** HTML entities (#605). Deleted or inverted by the
  `remove-html-unescape` Decision.
- `unit_tests/test-review-finalize.py` — the three
  `test_review_{code,plan,discussion}_finalize_unescapes_html_entities` tests. Same.
- `unit_tests/test-agent-dispatch.py:86-164` — asserts `write_brief` returns a single
  `Path`; it now returns the brief path **and** the output path.
- `unit_tests/test-agent-mode-dispatch.py:370-377` — calls `write_brief(...)` and then
  asserts `brief_path.exists()` **and `brief_content == prepare_result["prompt_text"]`
  exactly**. Both break: the return shape changes, *and* the appended output-contract footer
  means the written brief is deliberately no longer byte-equal to `prompt_text`. Update the
  equality assertion to "starts with `prompt_text`, then the footer".

**Downstream rationale that goes stale.** `mill-start/SKILL.md:152` and
`mill-plan/SKILL.md:111` both pre-emptively load the `mill-receiving-review` skill, and
both justify it with the claim that "under Agent-mode dispatch a reviewer's findings arrive
already embedded in the `<task-notification>` payload the orchestrator must read just to
learn the round's verdict". After this change that is **no longer true** — findings arrive
only in the review file. The pre-emptive load is still correct (the orchestrator must have
the skill active before it reads the review file to present gaps or NITs), but the stated
reason must be rewritten or it will mislead the next reader.

**Relationship to the deferred `mill-orchestrator` task (id 0).** That proposal's core
principle is "Thread B never reads source files" and its own context-budget evidence
section already names this exact defect class (items 1 and 2: `millpy-implement.py` dumping
subprocess output to stdout; `millpy-bg.py` polling tail-output). This task fixes the
agent-mode equivalent of the same disease. The two are **complementary, not overlapping**:
id 0 restructures *who* orchestrates, this task fixes *what the orchestrator is forced to
read*. Landing this makes id 0 cheaper, because a lean agent-mode dispatch is a
precondition for a Sonnet Thread B. Fork is orthogonal to both and is not a mechanism
either one needs.

**Fork availability** (verified, not assumed): requires Claude Code ≥ 2.1.117, on by
default from 2.1.161; this environment runs 2.1.207. `subagent_type: "fork"` is present in
the orchestrator's own `Agent` tool schema. It cannot be dispatched by mill's Python CLIs —
it is a harness-level feature — which is a further structural reason it can only ever
appear in SKILL.md-level guidance, never in a `prepare` envelope.

## Constraints

- No `CONSTRAINTS.md` at the hub root.
- `finalize`'s external contract (`--agent-output <path>`, and the JSON envelopes it emits)
  must not change — mill-go, mill-start, and mill-plan all parse those envelopes. Adding
  `output_path` to the *prepare* envelope is additive and does not violate this.
- **The `incomplete` classification must survive.** Any change to how `finalize` handles a
  missing report must preserve the git-state completeness recount; classifying a partial
  batch as anything that routes to the transient `commits_made > 0` path reintroduces the
  #574 false-success bug (`mill-go/SKILL.md:137`).
- The reviewer must not touch source code or git. Note this is enforced by **prompt
  guardrail**, not by construction, once `Write` is granted — `tools:` frontmatter has no
  path scoping. See the `reviewer-write-grant-scoped-to-briefs` Decision for the honest
  limitation and the `PreToolUse`-hook follow-up.
- Briefs are committed artifacts (`git add _mill/briefs/` appears throughout mill-go). The
  `.out.md` files land in the same directory and are committed with them, so the audit
  trail is preserved — the sub-agent's full output remains on disk and in git, it simply
  stops passing through the orchestrator's context.
- ASCII-only in `print()` / `_log()` output (Windows cp1252).

## Testing

Unit tests live in `plugins/mill/unit_tests/test-<name>.py`, run via `run-all.py`, with
in-memory/tempfile fixtures and no real git or LLM. That suits every part of this change
except the SKILL.md edits, which are prose and are verified by inspection.

**Scope note:** the 29-file "Authoritative edit set" enumerates contract-carrying files plus
existing tests that **go red**. The *new* assertions below are **additive** and not bounded by
that list — they extend existing suites where one fits (`build_tool_rule` cases →
`test-review-common.py`; `write_brief` footer, truncation, and no-token cases →
`test-agent-dispatch.py`; missing/empty/stale `finalize` cases → `test-implementer-common.py`
and `test-review-finalize.py`) and add one new suite for the cross-cutting conformance sweep.
The conformance test asserts against the edit set; it is not itself a member of it.

- **`_agent_dispatch` output-path helper — TDD candidate.** The `.md` → `.out.md` rule is
  currently prose restated in four places; make it one function and test it directly,
  including the edge case of a brief path whose *directory* component contains `.md`, which
  naive string replacement would corrupt.
- **`write_brief` output-contract footer.** Assert the written brief ends with a footer
  naming the absolute `.out.md` path as literal text and instructing the one-line ack, for
  every `role` value used by the nine dispatch sites. This is the test that proves the change
  is uniform rather than reviewer-only.
- **No-token regression test — TDD candidate.** Assert that **no** template under
  `templates/` contains an `<OUTPUT_FILE>` token, and that `_render.render` succeeds on every
  template with its normal `values` dict. This pins the `_render.py:35` constraint that made
  the first token design unbuildable, so nobody reintroduces it.
- **`finalize` on a missing / empty `.out.md` — the most important TDD candidate, and the
  one that guards a known bug.** Split by role, matching the
  `missing-out-md-defers-to-git-state` Decision:
  - *implementer / fixer / merge-in:* with the file **absent**, assert the completeness
    recount still runs and that the result tracks git state — `success` when every card is
    committed and the tree is clean; **`stuck_type: incomplete` when some-but-not-all cards
    are committed**; `stuck_type: logic` ("no structured report") when there are no commits
    and no report. The `incomplete` case is the regression guard for #574: a test asserting
    `transient` here would be asserting the bug. Repeat for zero-byte and whitespace-only
    files, which must behave identically to absent.
  - *review CLIs:* with the file absent / empty / whitespace-only, assert the `verdict:
    ERROR` envelope is emitted (not a synthetic `transient`), so the existing ERROR-only
    retry path picks it up.
  - **A third case — *stale* — for both roles.** Write an `.out.md` (e.g. containing
    `APPROVE`), then call `write_brief` for the same role/scope/round, then run `finalize`.
    Assert the pre-existing file **did not survive**: the reviewer must NOT report `APPROVE`.
    This is the regression guard for `write-brief-truncates-stale-out-md` — without the
    truncation, a killed-then-retried reviewer's old green verdict is silently reused, and
    this test is the only thing that would catch it.
- **`html.unescape` removal — regression test.** A finding whose body quotes source code
  containing a literal `&lt;`, `&gt;`, and `&amp;` must round-trip through `finalize`
  byte-identically into the review file. This test would **fail on today's code**, which is
  the point: it pins the correctness bug the removal fixes.
- **Prepare-envelope shape.** Assert `output_path` is present, absolute, and equals
  `brief_path` with `.md` → `.out.md`, on every **brief-emitting success** envelope (the
  implementer/fixer/merge CLIs and the three review CLIs). **Assert the converse for all three
  carve-outs:** `dispatch_needed: false`, the plan-validator `{"errors": …}` envelope, and
  `print_error_envelope` each carry **no** `output_path`. A blanket "always present"
  assertion fails on all three — precisely the trap the carve-out list exists to avoid.
- **Conflicting-instruction sweep — conformance test.** A cheap grep-style test asserting
  that no *agent-mode* prompt still tells the agent its output's last line must be the JSON,
  or that its sole output is its final message. **Search root must include `scripts/`, not
  just `templates/` and `agents/`** — the `<TOOL_RULE>` contradiction is injected from
  `_review_common.py`, so a doc-directories-only sweep provably cannot catch it (round 3 of
  this discussion's own review caught exactly that miss). Better still, assert against the
  **rendered `prompt_text`** for each of the nine dispatch sites, which catches
  contradictions regardless of which file they came from. Assert against the enumerated
  "Authoritative edit set" in Technical context.
- **`build_tool_rule` — all four cells, TDD candidate.** Not two cases: assert **`bulk` ×
  full**, **`bulk` × agent**, **`tool-use` × full**, **`tool-use` × agent**. The two
  `--stage full` cells must be **byte-identical to today's text** (that is what stops the
  reviewer's API-error fallback from being collaterally broken). The `bulk` × agent cell is
  the one that matters most: assert it does **not** contain a bare "Do NOT request tool
  calls" that would contradict the Write instruction, and that it *does* carve out the single
  `Write`. Assert every agent-mode cell still forbids `Edit`, git, and bash.

**Existing tests that must be deleted or inverted** (they pin the behaviour this change
removes; verify goes red otherwise):

- `test-implementer-common.py:3131-3172` (case 63) and the three
  `test_review_{code,plan,discussion}_finalize_unescapes_html_entities` tests in
  `test-review-finalize.py` — they assert `finalize` **unescapes** HTML entities. Under
  `remove-html-unescape` the correct assertion inverts: the text must survive
  **byte-identically**, entities and all. Rewrite them as the round-trip regression test
  above rather than simply deleting them — the #605 concern was real, it just moves.
- `test-agent-dispatch.py:86-164` — asserts `write_brief` returns a single `Path`; update
  for the brief-path + output-path return.

Not covered by unit tests, and accepted: the end-to-end behaviour that the orchestrator's
context actually shrinks. Verify that manually on the first real mill-go run after this
lands, by observing that the `<task-notification>` payload is one line. Also verify the
classifier change end-to-end on a *successful* implementer batch — under the old rules an
ack-only payload would have been misread as turn-exhaustion, so a clean green batch is the
direct test that `ack-is-the-completion-discriminator` landed correctly.

## Q&A log

- **Q:** Given fork is a poor fit for the scripted dispatch sites, what should this task build? **A:** Fork where it fits, *and* fix the `.out.md` bloat in the same task — it is the motivating problem and fork cannot solve it.
- **Q:** How do we preserve the reviewer's read-only invariant while letting it write? **A:** Grant `Write` guardrailed to `_mill/briefs/` only; the reviewer writes its own `.out.md` and nothing else. `finalize` still owns `_mill/reviews/`.
- **Q:** Fork `mill-self-report`? **A:** No. It fires as the last step of Handoff, so the context it would save is nearly worthless.
- **Q:** How should mill-start's Explore phase use fork? **A:** Guidance, not a mandate — prefer fork for scoped sub-investigations that need the task context; keep cold `Explore` agents for broad mechanical sweeps.
- **Q:** Which dispatch sites get the "sub-agent writes its own `.out.md`" contract? **A:** All of them. Nearly everything writes an `.out.md` today; fix the whole set uniformly.
- **Q:** What is the sub-agent's final message once it writes its own `.out.md`? **A:** A one-line ack (`WROTE <path>`). The Builder needs nothing from it — `finalize` supplies the verdict.
- **Q:** What if the sub-agent dies before writing `.out.md`? **A:** Add a missing-file guard at the four read sites — today an absent file raises an uncaught `FileNotFoundError` — then defer to role: implementer/fixer/merge-in fall into the existing git-state completeness recount (preserving `incomplete`); review CLIs emit the existing `ERROR` envelope. An earlier draft said "blanket `transient`", which review caught would have reintroduced the #574 false-success bug.
- **Q:** Record the fork rejection durably? **A:** Yes — a short decision note in the repo. The three disqualifiers are non-obvious and the question will recur.
- **Q:** Are the `subprocess` / `psmux` dispatch paths a constraint on this design? **A:** Partly — and the first answer here was too broad. They are dead as a *configured* dispatch mode, but **`--stage full` is not dead**: it is the reviewer's fallback after two consecutive raw API errors (`mill-go/SKILL.md:129`), it shares the review templates and `<TOOL_RULE>`, and it must keep working. Hence the `output-contract-is-agent-mode-only` Decision.
- **Q:** What goes in the `.out.md`, and which files need sweeping? **A:** The agent's full report *including* its trailing status/verdict block — only the delivery channel changes. The sweep is the "Authoritative edit set" in Technical context; it grew twice under review, most importantly to include `_review_common.py`, whose `<TOOL_RULE>` injects "Do NOT use Write" into every review prompt from Python rather than from a template.
- **Q:** Does the new contract apply to the `--stage full` reviewer path too? **A:** No — agent-mode only. The `.out.md` footer is agent-mode-only by construction (`write_brief` is prepare-only), but `build_tool_rule` must be made dispatch-aware so the two channels don't get contradictory instructions.
- **Q:** Deleting the orchestrator's `Write` also deletes the guarantee that `.out.md` is fresh. What replaces it? **A:** `write_brief` unlinks any pre-existing `.out.md` at brief-write time, and the warm-`SendMessage` path (which bypasses prepare) deletes it explicitly before resuming. Nothing in the codebase truncates `.out.md` today, and both recovery paths reuse the same file path — so without this, a killed-then-retried **reviewer** could hand back a stale `APPROVE` that no live reviewer produced. Rejected an mtime check as clock-dependent.
- **Q:** The review templates open with a static "READ-ONLY reviewer / MUST NOT call Write" header. How is that reconciled? **A:** The tool prohibitions are **deleted from the header** and `build_tool_rule` becomes the sole owner of the read-only clause — it is the only channel-aware injection point, and a static template cannot be made dispatch-aware. The `MILL_REVIEW_BEGIN`/`END` wrapper stays: it is the content format of the `.out.md` file.
- **Q:** What does `build_tool_rule` emit for a **bulk** reviewer under agent-mode dispatch? **A:** All four cells are enumerated in the Decision. The bulk×agent cell is the trap — `tooluse` defaults to `False`, so it is reachable — and its "Do NOT request tool calls" clause must be narrowed to "no tool calls **to gather content**, with the single exception of the one `Write` of your report", or the reviewer writes no file and returns `ERROR` every round.
- **Q:** Can the templates carry an `<OUTPUT_FILE>` token? **A:** **No.** `_render.render` (`_render.py:35`) raises `KeyError` on any unresolved `<UPPERCASE>` token, so a token in a template hard-fails rendering *before* `write_brief` runs, and is unsuppliable on `--stage full` anyway. Templates go channel-neutral ("your report must end with a single JSON object"); `write_brief` appends a footer carrying the literal absolute path.
- **Q:** What happens to existing tests that pin the old behaviour? **A:** They are part of the edit set. The four `html.unescape` tests get **inverted** (byte-identical round-trip) rather than deleted — the #605 concern is real, it just moves — and `test-agent-dispatch.py`'s `write_brief` return-shape assertion is updated.
- **Q:** Who sets the agent-mode flag that makes `build_tool_rule` dispatch-aware? **A:** The CLIs' `--stage prepare` branches, via a parameter on each backend's `prepare()` that defaults to non-agent. **Not** inside `prepare()` itself — `run()` (the `--stage full` fallback) calls the same `prepare()`, so a default-on flag there would poison the very path the carve-out protects. `_review_plan.py` is asymmetric and needs per-callsite attention.
- **Q:** Does *every* prepare envelope carry `output_path`? **A:** No — `dispatch_needed: false` envelopes (merge-in verify-fix pass case) dispatch no agent and write no brief, so they carry none. The shape test asserts both directions.
- **Q:** How does mill-go tell a successful notification from a dead one once the payload is one line? **A:** The `WROTE <path>` ack becomes the positive completion discriminator. Without this, every successful implementer would match `:132`'s "non-error, non-JSON" turn-exhaustion trigger.
- **Q:** Does the prepare envelope gain an `output_path` field? **A:** Yes, additive. The `.md` → `.out.md` rule then lives in one helper instead of four prose restatements.
- **Q:** How should review gaps be resolved for the rest of this mill-start? **A:** Auto-pick the recommended option on every review round.
- **Q:** Who puts the report-file path into the brief? **A:** `write_brief`, the only thing that knows `brief_path`. It **appends a footer** carrying the literal absolute path after rendering — there is no token anywhere, in templates or agent definitions. The envelope's `output_path` is a read-only echo. (Two earlier drafts were wrong here: the orchestrator cannot inject a token into an already-written brief, and a `<OUTPUT_FILE>` token in a template would hard-fail `_render`.)
- **Q:** Does the warm-`SendMessage` resume path need changing? **A:** Yes — `mill-go/SKILL.md:161` tells the resumed implementer to "emit the required JSON report as your final line", which would re-bloat the Builder and produce a payload the new ack classifier does not recognise. It is part of the edit set.
