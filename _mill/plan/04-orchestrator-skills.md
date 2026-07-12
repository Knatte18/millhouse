# Batch: orchestrator-skills

```yaml
task: Explore and adopt Claude Code fork-agents in mill orchestration
batch: orchestrator-skills
number: 4
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-skill-helper-drift.py test-skills-index.py
depends-on: [2, 3]
```

## Batch Scope

This batch updates the three orchestrator SKILL.md files to match the contract batch 2 shipped. It
is the **only** batch that adopts fork (in mill-start's Explore phase), and the only one that
records why fork was rejected everywhere else.

`mill-go/SKILL.md`'s `## Agent-mode dispatch` section is the single source of truth for the dispatch
protocol; the other two skills point at it. The protocol now **forks by role**: for a reviewer
dispatch the orchestrator no longer captures the notification to `.out.md`, because the reviewer
wrote it. For implementer / fixer / merge-in dispatches, step 5 is unchanged. This asymmetry is
temporary and intentional, and the skill must say so.

**The blast radius is smaller than it looks.** Steps 4(b), 6.5 and the Clean mid-work stop paragraph
(`:131-141`, `:159-165`) are **implementer-only** and stay untouched — that is what the descope
bought. Of the four `.out.md` mentions in the file, only `:149` and `:151` change; `:135` and `:163`
are on implementer paths.

**Why this batch depends on batch 3 as well as batch 2.** Card 18(c) stops the orchestrator from
capturing the reviewer's notification to `.out.md`. That is only correct once the reviewer can
actually write the file itself — which is card 14's `Write` grant, in batch 3. Landing batch 4 on
top of batch 2 alone would produce a window where **nobody** writes `.out.md`: the orchestrator has
stopped and the reviewer is not yet permitted to start, so every review round would find an absent
file and return an `ERROR` envelope. Hence `depends-on: [2, 3]`.

These are prose edits with no runnable surface of their own, so they are verified by inspection plus
the two structural guards named in Batch Tests.

## Cards

### Card 18: `mill-go/SKILL.md` — reviewer-skipped capture, envelope-supplied output path, fork note

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/millpy-review-code.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Five edits inside `## Agent-mode dispatch` (`~:105-175`):
  (a) **`:123`** currently ends *"Read the subagent's final message from the notification payload —
  that is the text used in steps 4 and 5 below."* Reword: for a **reviewer** dispatch, step 5 is
  skipped, so the payload feeds **step 4's classification only**. For implementer / fixer /
  merge-in dispatches it still feeds both, unchanged.
  (b) **Step 4(a) (`:129`)** — reword to key **solely on the error marker**. Its current heuristic
  ("roughly 0 tokens, no `MILL_REVIEW` block and no `status` JSON") becomes actively misleading: a
  *successful* reviewer payload is now exactly ~0 tokens with no `MILL_REVIEW` block, so those
  negative signals no longer discriminate anything. Only the `API Error` / `Internal server error`
  marker clause does. Keep the one-retry policy, the second-consecutive-error escalation, and the
  `--stage full` fallback for read-only reviewer dispatches exactly as they are.
  **Add deliberately no ack predicate.** Do not add a `WROTE ` prefix-match branch. Ack and non-ack
  clean payloads both fall through to `finalize`, which distinguishes them by the **presence of the
  `.out.md` file** — a stronger signal than the chat text, and one the orchestrator gets for free.
  The ack exists for humans reading the transcript, not for branching. State this in the text so the
  next reader does not "fix" the apparent omission.
  (c) **Step 5 (`:149`)** — becomes **reviewer-skipped**. For a reviewer dispatch the orchestrator
  does **not** write `.out.md`; the reviewer already did. For implementer / fixer / merge-in
  dispatches step 5 is unchanged. Explain in one line why: the old text made the orchestrator read
  the sub-agent's entire final message and **write that whole thing back out**, so a full reviewer
  findings dump landed in the Builder's context twice — even though `:376` and `:820` forbid the
  Builder from acting on findings.
  (d) **Step 6 (`:151`)** — take `--agent-output` from the prepare envelope's new `output_path`
  field for review CLIs, rather than re-deriving `<brief_path>.out.md` by string munging. Keep the
  derivation prose for the implementer / fixer / merge-in CLIs, whose envelopes do not carry the
  field.
  (e) **Add a short "Why not fork?" subsection** at the end of `## Agent-mode dispatch` (~6 lines).
  A fork inherits the parent's context but: (1) always runs on the **parent's model** and **ignores
  a `model` override**, which breaks the per-role `roles.*.model` tiers (`roles.fixer.model: haiku`,
  `roles.implementer.model: sonnethigh`, discussion-review `opushigh`); (2) inherits the **parent's
  tools**, so a reviewer forked from mill-go would hold `Edit`, `Write` and `Bash` and lose its
  read-only guarantee; (3) has **no on-disk brief**, so a forked dispatch cannot be resumed after a
  crash. Fork is therefore used only in mill-start's Explore phase. Note also that fork's advertised
  "the child's tool output stays out of the parent" is **not** a differentiator — an ordinary fresh
  Agent call already behaves that way.
  **Do not touch** steps 4(b), 6.5, or the Clean mid-work stop paragraph (`:131-141`, `:159-165`),
  or the `.out.md` mentions at `:135` and `:163`. They are implementer-only.
- **Commit:** `docs(mill-go): reviewer-skipped output capture, envelope output_path, why-not-fork note`

### Card 19: `mill-start/SKILL.md` — fork guidance in Explore, and the stale review rationale

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Two edits:
  (a) **Phase: Explore, Step 3 (`:117-125`)** currently tells the orchestrator to explore *directly*
  with codeguide / file structure / `git log` / `Grep` / `Glob`, and names no Agent dispatch at all.
  **Add** sub-investigation guidance — this *introduces* the practice, it does not replace an
  existing cold-agent one. Prefer `Agent(subagent_type: "fork")` for a **scoped sub-investigation
  that needs the task context already in the orchestrator's head** (the fork inherits the
  conversation, so it needs no brief); use a cold `Explore` agent for a **broad mechanical sweep**
  (it does not benefit from inherited context and would pay the parent's prefix on every turn);
  explore inline when the question is small.
  **This is guidance, not a mandate.** Say so explicitly. This is the one site in mill with no
  brief, no resume requirement, no per-role model tier and no tool restriction to lose — which is
  exactly why none of the three fork disqualifiers (card 18(e)) apply here.
  (b) **`:152`** — the pre-emptive `mill-receiving-review` load is justified by the claim that
  *"under Agent-mode dispatch a reviewer's findings arrive already embedded in the
  `<task-notification>` payload the orchestrator must read just to learn the round's verdict"*. That
  is **no longer true**: findings now arrive only in the review file. The pre-emptive load is still
  **correct** — the skill must be active before the orchestrator reads the review file to present
  gaps or NITs — but the stated reason must be rewritten to that, or it will mislead the next
  reader. Keep the load unconditional; change only the rationale.
- **Commit:** `docs(mill-start): add fork guidance to Explore and fix the stale review-load rationale`

### Card 20: `mill-plan/SKILL.md` — the same stale review rationale

- **Context:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** `plugins/mill/skills/mill-plan/SKILL.md:111` carries the **same** stale
  rationale as `mill-start/SKILL.md:152` (verified: the two paragraphs are identical). Apply the
  same fix as card 19(b) — keep the unconditional `mill-receiving-review` load, rewrite the reason:
  findings now arrive in the review file, not in the `<task-notification>` payload, and the skill
  must be active before the orchestrator reads that file. Change nothing else in this skill; the
  fork guidance in card 19(a) is scoped to mill-start's Explore phase and has no counterpart here.
- **Commit:** `docs(mill-plan): fix the stale review-load rationale`

## Batch Tests

No card in this batch has a runnable surface — all three files are orchestrator prose consumed by a
model, not by an interpreter. `verify:` therefore runs the two structural guards that *do* cover
SKILL.md files:

- **`test-skill-helper-drift.py`** scans every mill SKILL.md for helper references matching
  `_<module>.<fn>(` and asserts each resolves to a real shipped function in
  `plugins/mill/scripts`. It is the net for a prose edit that invents or misspells a helper name —
  a live risk here, since card 18 references `_agent_dispatch` behaviour. It also holds a
  regression lock on `mill-start/SKILL.md`'s `task['body']` / `task['brief']` guidance, which card
  19 must not disturb.
- **`test-skills-index.py`** asserts the root `SKILLS.md` index stays consistent with the shipped
  skills. No skill is added or removed here, so it must stay green.

The substance of these edits — that the rendered prompts and the dispatch protocol now agree — is
asserted in batch 5.
