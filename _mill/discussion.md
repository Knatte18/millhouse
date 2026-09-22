# Discussion: Fix prose skill: staleness rule and missing loads

```yaml
task: 'Fix prose skill: staleness rule and missing loads'
slug: prose-skill-gaps
status: discussing
parent: main
```

## Problem

`plugins/mill/skills/prose/SKILL.md` is the skill that governs every piece of text a mill agent writes — chat replies, markdown files, commit messages, code comments, review findings.
It has two independent gaps.

First, it permits prose that names a specific which goes stale the moment the thing it names changes.
The reported case was a sibling repo's `CLAUDE.md` carrying a table of test counts and runtimes; the broader case is any detail a reader could instead derive — a caller list, or a function or file named descriptively inside a sentence where a rename silently falsifies it.
The failure mode is the same either way: an unrelated one-line change elsewhere forces an edit here to keep the prose honest, and nothing signals when it has gone stale.
GitHub issue #1123 filed the numeric case;
the user broadened it in follow-up discussion.

Second, `prose` is largely not loaded.
`conversation/SKILL.md` says "Load `prose` first — this skill assumes those rules already apply", but that line runs only after `conversation` itself is loaded, so it cannot cause `prose` to be loaded.
Every *caller* has to name `mill:prose` explicitly.
Three orchestrators do (`mill-start`, `mill-plan`, `mill-go-base`, plus repo-local `mill-pool`);
`handoff`'s emitted document does not, the per-batch implementer and fixer dispatch does not, and none of the five reviewer prompt templates does.
So the skill that is supposed to govern all agent-written text is absent from most of the agents actually writing it.

A third, smaller problem rides along: `markdown/SKILL.md` is superseded by `prose`'s own "Line breaks" and "Markdown" sections but is still referenced from `mill-go2/SKILL.md` and `templates/review-output.schema.md`, so agents still load and cite a stale skill.

**Why now:** the user is observing the symptom (excess filler, "svada") in live output, and the loading gap is the confound that has to be removed before the content of `prose` can be judged at all.

## Scope

**In:**

- `plugins/mill/skills/prose/SKILL.md` — add the staleness rule, absorb the fenced-YAML metadata rule from `markdown`, sharpen "No padding" with a cut-test.
- `plugins/mill/skills/code-comments/SKILL.md` — reduce "No enumerated-consumer lists" to a pointer at `prose` plus its comment-specific example and rationale.
- Delete `plugins/mill/skills/markdown/SKILL.md`.
- `plugins/mill/skills/handoff/SKILL.md` — the emitted document's first line must instruct loading `mill:prose` then `mill:conversation`.
- `plugins/mill/skills/mill-go2/SKILL.md` — driver preamble loads `mill:prose`, not `mill:markdown`.
- `plugins/mill/scripts/_agent_dispatch.py` — `language_skills_directive()` adds `prose` to the always-present skills alongside `code-quality`.
- The five reviewer prompt templates (`review-code-batch.md`, `review-code-holistic.md`, `review-discussion.md`, `review-plan-batch.md`, `review-plan-holistic.md`) — inlined writing-style block.
- Three agent briefs whose `## Tools` omits `Skill` (`fixer-holistic-brief.md`, `merge-in-conflict-brief.md`, `merge-in-verify-brief.md`) — same inlined block.
- Stale `markdown`-skill references in `templates/review-output.schema.md`, `scripts/millpy-skills-index.py`, `scripts/tools/mdreflow/mdreflow.py`.
- `SKILLS.md` regeneration after the `markdown` skill is deleted.
- `plugins/mill/unit_tests/test-language-skills-directive.py` — update for the added skill.
- A new unit test asserting the load-directive convention.
- A full sweep of `plugins/*/skills/**/SKILL.md` and `plugins/mill/templates/*.md` for any further site with the same gap, fixing each found.

**Out:**

- `.claude/skills/` (repo-local `mill-pool`, `ladder-run`) — not shipped, and `mill-pool` already loads `prose` correctly.
- Widening any agent's `tools:` frontmatter grant. No agent definition under `plugins/mill/agents/` is modified.
- Rewriting `conversation/SKILL.md`'s own content. Its "Load `prose` first" line stays as-is; it is correct, it just cannot be the enforcement mechanism.
- Any change to review *severity* vocabulary, verdict parsing, or the review output schema's machine-read parts. Only the one prose sentence citing "the markdown skill" changes in `review-output.schema.md`.
- Changing `CLAUDE.md`'s "Reviews: tight v1 style" requirement. The inlined reviewer block serves that existing requirement; it does not restate or redefine it.
- Re-observing agent behaviour after the fix to confirm the filler problem is solved. This cannot be done from inside the task (see the `filler-sharpening` Decision).

## Decisions

### staleness-rule-shape

- Decision: one new section in `prose/SKILL.md`, titled "Don't pin a perishable specific", placed between "Say it once" and "Line breaks" (loomyard's position for its equivalent section). It covers tallies, enumerated-consumer/caller lists, and names cited descriptively rather than as stable identifiers, under one principle: name the source, not the snapshot.
- Rationale: these are one failure mode, not three. A count, a caller list, and a descriptively-cited function name all encode a cross-reference to something that changes independently of the prose. Splitting them into separate sections would state the same principle twice and invite the reader to treat an unlisted fourth variant as permitted.
- Rejected: two sections (loomyard's "Never pin a count" verbatim plus a separate named-reference rule) — duplicates the rationale and leaves the general principle unstated. Keeping the title "Never pin a count" while widening the body — the title would then misdescribe most of its own content.

### staleness-rule-source-material

- Decision: use loomyard's "Never pin a count" section (`github.com/Knatte18/loomyard`, `plugins/scribe/skills/prose/SKILL.md`) as the starting point for the numeric case only. Keep its closed-set exception ("a closed set whose size is the contract — an enum a test pins shut — and even that is stated once, at its definition site"). Author the measurement-report exemption ourselves.
- Rationale: the task proposal states loomyard's section already carries a measurement-report exemption. It does not — verified by fetching the file during discussion; its only exception is the closed-set-contract one. The exemption is still correct and must be written, but it is new text, not inherited text, and a plan writer who goes looking for it in loomyard will not find it.
- Rejected: copying loomyard's section wholesale and assuming the exemption is present — would silently drop the exemption.

### measurement-report-exemption

- Decision: exempt a measurement report — a benchmark table, a results document, a captured baseline — from the staleness rule. State the reason in the rule: such a document records one specific run at a point in time and is not claiming to stay true.
- Rationale: the user's framing is the exact test to encode — these artefacts *are supposed to* go stale when a new run happens, and that is what makes them useful. Without the exemption the rule would forbid the one place a hard number is the entire point, and an agent applying the rule literally would strip numbers out of a benchmark table.
- Rejected: omitting the exemption to match loomyard exactly — would make the rule wrong for a real and common document type.

### caller-list-ownership

- Decision: `prose`'s new section owns the rule. `code-comments`' "No enumerated-consumer lists" bullet stops stating the rule and becomes a pointer at `prose` that retains its comment-specific illustration (the `"the logger, reed, shuttle, and burler all write it"` example) and its comment-specific rationale (an unrelated change elsewhere in the codebase becomes a forced edit *here*). Net: the rule is stated once, the illustration survives.
- Rationale: `prose`'s own "Say it once" rule requires a rule to be stated in one place and referenced from elsewhere. Two full statements would make the skill violate itself, and the two copies would drift. `code-comments` already has the exact precedent in its "Line-wrap style" section, which is one sentence pointing at `prose`'s Line-breaks rule. An example is not a restatement of a rule, so keeping it costs nothing under "Say it once".
- Rejected: leaving both full statements (argued on the grounds that implementers load `code-comments` but might not load `prose` — but that gap is precisely what this task closes, so it must not drive the design). Deleting `code-comments`' section outright — loses a good comment-flavoured example and the comment-specific rationale.

### markdown-skill-deletion

- Decision: delete `plugins/mill/skills/markdown/SKILL.md`. Before deleting, move its "Fenced YAML for metadata" rule into `prose`'s existing "Markdown" section. Let its "No fixed-column hard-wrapping" and "Structure" sections die with the file.
- Rationale: only the fenced-YAML rule is unique — `prose`'s "Markdown" section currently covers headings only, and CLAUDE.md plus `review-output.schema.md` both depend on the fenced-YAML-versus-frontmatter convention, so deleting it outright would drop a live rule. The line-break content is genuinely duplicated: `prose`'s "Line breaks" already states the rule, the clause-boundary break, the URL/abbreviation edge case, the plain-newline requirement, and the table/blockquote exclusion. `markdown`'s extra paragraphs (the explicit-subject test, the CommonMark soft-break rationale, the BAD/GOOD example) are elaboration a reader does not need in order to comply. Keeping a thin residual skill would leave one more skill for a caller to forget to load — which is the bug class this task exists to close.
- Rejected: keeping a thin `markdown` skill holding only the fenced-YAML rule. Migrating the explicit-subject test and BAD/GOOD example into `prose` — the user judged `prose`'s existing Line breaks section sufficient.

### filler-sharpening

- Decision: sharpen `prose` now, in this task, by adding a cut-test to the "No padding" section — a concrete per-sentence test the agent applies, modelled on `handoff/SKILL.md`'s proven formulation ("would a fresh agent act differently if this line were missing? If not, cut it"). Do not impose any numeric limit on sentences, paragraphs, or sections. Do not add a new "don't repeat yourself" rule — "Say it once" and "No padding"'s first line already cover it.
- Rationale: the proposal framed this as "re-check after the loading fix is in", but that re-check cannot happen inside this task — observing whether agents still produce filler requires running agents after the change lands. A deliverable that says "check later" is unverifiable and would be dropped. Tightening the wording is the part we can actually land, and it is correct independent of whether the loading fix alone would have sufficed.
- Rejected: a hard cap on paragraph or sentence count. The user's objection is decisive and must be recorded so a later reviewer does not "simplify" the cut-test into a number: a numeric ceiling makes an agent drop content that is vital, because the cheapest way to satisfy a count is to delete, and the agent has no way to know which sentence was load-bearing. A qualitative test costs the agent an extra per-sentence pass — the user accepted that cost explicitly, preferring it to filler. Also rejected: wholesale rewrite of "Get to the point" and "No padding" to loomyard's phrasing, and a named anti-pattern list in place of the test.

### reviewer-templates-inline-not-load

- Decision: inline a short writing-style block directly into the five reviewer prompt templates rather than adding a "load `mill:prose`" directive.
- Rationale: the reviewer sub-agents cannot load skills. `plugins/mill/agents/mill-reviewer.md` grants `Read, Grep, Glob, Write` — no `Skill` tool — and every tiered variant (`mill-reviewer-low` … `mill-reviewer-max`) inherits that shape. A load directive in the template would be an instruction the agent has no tool to execute. Bulk-mode reviewers, though not currently in use, receive a raw rendered prompt string through an LLM-provider wrapper with no skill machinery at all, so an inlined block is the only form that works in both dispatch shapes.
- Rejected: granting `Skill` to the `mill-reviewer` agents and using a load directive — would fix agent-mode only, leave bulk-mode unfixed, and widen a deliberately narrow tool grant as a side effect of a prose change. A shared include referenced from all five templates was considered and is left to mill-plan as an implementation detail, conditional on the template renderer supporting includes (see Technical context).

### brief-load-versus-inline-rule

- Decision: one rule decides the form at every dispatch site — a load directive where the brief's `## Tools` section grants `Skill`, an inlined style block where it does not. In practice: `implementer-brief.md` and `fixer-batch-brief.md` get the skill named via `language_skills_directive()`;  `fixer-holistic-brief.md`, `merge-in-conflict-brief.md`, and `merge-in-verify-brief.md` get the inlined block, as do the five reviewer templates.
- Rationale: these three briefs all produce prose — commit messages, conflict resolutions, verification summaries — and all three omit `Skill` from their Tools list, so they are in the same position as the reviewers. Deriving both forms from one rule means a future brief's treatment follows from its own Tools list rather than from a case-by-case judgement.
- Rejected: adding `Skill` to those three briefs' Tools lists so a load directive works everywhere — widens three agents' prompt-level tool grants as a side effect of a prose fix, which is out of scope. Leaving the three briefs alone as out of scope — they have the same defect for the same reason, and the proposal explicitly says its site list is not closed.

### language-skills-directive-contents

- Decision: `_agent_dispatch.language_skills_directive()` adds `` `prose` `` to the unconditional skills list alongside `` `code-quality` ``, present for every batch regardless of detected language. It is not added to any per-language group. `conversation` is not added.
- Rationale: `prose` is language-agnostic, exactly like `code-quality`, and the function's per-language groups (`{lang}-comments`, `{lang}-testing`) are for skills that vary by file suffix. Implementers and batch fixers write commit messages, structured status reports, and code comments on every batch, including batches that touch no recognized language at all. `conversation` governs talking to a human operator in a live chat, which a dispatched implementer never does — including it would load rules about numbered-option prompts and worktree-isolation chat conventions that have no bearing on the agent's work.
- Rejected: adding `conversation` alongside `prose` for symmetry with the orchestrators' Step 0. Adding `code-comments` — not currently named by the function either, but that is a separate gap outside this task's scope.

### convention-test

- Decision: add a unit test under `plugins/mill/unit_tests/` that walks the shipped skill and template trees and fails when a file issues a load directive naming `mill:conversation` without also naming `mill:prose`.
- Rationale: without it this task is a point-in-time cleanup and the gap returns silently the next time someone writes a skill that loads `conversation` — which is exactly how the current gap arose, with three orchestrators getting it right and three sites getting it wrong and nothing flagging the difference. The user notes loomyard carries many tests of this shape and they work well in practice. The cost is that the test encodes a wording convention in a pattern and must be updated if the convention's wording changes.
- Rejected: applying the fix without a test. Extending the test to also assert the reviewer templates carry the inlined style block — asserting on prose *content* is the thing the user judged untestable, and a substring check on a style block would break on any rewording of the block.

### convention-test-discrimination

- Decision: the test fires only on load-directive shapes — a line containing a load verb ("Load", "load and follow", "loads") in proximity to the skill name. A bare referential mention of `mill:conversation` is ignored.
- Rationale: several files mention `mill:conversation` without instructing anyone to load it — `mill-start/SKILL.md` cites its numbered-options rule, `workflow/SKILL.md` lists it in a routing table, `_inplace.py`'s docstring cites its conventions. Requiring all of those to carry a `mill:prose` reference would add redundant text to satisfy a linter. Matching the load-directive shape targets the way the defect actually manifests.
- Rejected: requiring any file mentioning `mill:conversation` to also mention `mill:prose` — simpler pattern, but forces noise into unrelated files. An explicit allowlist of exempt files — a maintenance burden that grows with every new referential mention and silently goes stale.

### convention-test-scope

- Decision: the test walks `plugins/*/skills/**/SKILL.md` and `plugins/mill/templates/*.md`. It does not walk `.claude/skills/` or `plugins/mill/scripts/*.py`.
- Rationale: that is the shipped plugin surface — what other repos consume, and where the bug class lives. `.claude/skills/` is repo-local and not distributed, and its one relevant file (`mill-pool`) already has the directive correct. Script-level prompt builders are covered directly by the `language_skills_directive()` unit test, which asserts the rendered content rather than pattern-matching source.
- Rejected: extending to `.claude/skills/` and to `plugins/mill/scripts/*.py`.

### handoff-first-line

- Decision: `handoff/SKILL.md`'s instruction for the emitted document's first line becomes "Load `mill:prose`, then `mill:conversation`", matching the Step 0 wording used by `mill-start`, `mill-plan`, `mill-go-base`, and `mill-pool`.
- Rationale: naming only `mill:conversation` means `prose` does not get loaded — `conversation`'s own "Load `prose` first" line executes too late to cause it. The receiving agent is a fresh session writing prose from the first turn. Using the identical wording as the other four sites means all five read the same and the convention test matches one pattern.
- Rejected: naming `mill:prose` only, on the theory that a fresh session picks up `conversation` via `workflow` — leaves the `conversation` load to chance. Leaving the first line alone and listing `mill:prose` under the document's "suggested skills" section — a suggestion is not a load.

## Technical context

**The prose/conversation/markdown/code-comments skill cluster**

- `plugins/mill/skills/prose/SKILL.md` — sections in order: Get to the point, Eliminate empty intensifiers, No padding, Say it once, Line breaks, Markdown, Applies everywhere text is produced. The new staleness section goes between "Say it once" and "Line breaks". The fenced-YAML rule joins the "Markdown" section, which currently holds a single bullet about headings.
- `plugins/mill/skills/conversation/SKILL.md` — line 11 carries the "Load `prose` first" line. Unchanged by this task.
- `plugins/mill/skills/markdown/SKILL.md` — to be deleted. Its "Fenced YAML for metadata" section is the only content that must survive; it distinguishes fenced ` ```yaml ` for generated files from `---` frontmatter reserved for SKILL.md and plugin manifests. This matches CLAUDE.md's Conventions bullet.
- `plugins/mill/skills/code-comments/SKILL.md` — "No enumerated-consumer lists" is the final bullet under "Prohibited patterns". Its "Line-wrap style" section, a few lines above, is the pointer-at-`prose` precedent to imitate.

**Sites needing a load directive or inlined block**

- `plugins/mill/skills/handoff/SKILL.md` — the instruction about the emitted document's first line is a single line in the body. Note that the same file also references "`conversation`'s file-writing rule" earlier; that is a referential mention and needs no change under the `convention-test-discrimination` Decision.
- `plugins/mill/skills/mill-go2/SKILL.md` — "Driver preamble", a single long line naming `mill:code-quality` and `mill:markdown`. Replace `mill:markdown` with `mill:prose`. `mill:conversation` is already handled for this path by `mill-go-base`'s Step 0b, which mill-go2 runs through; the preamble is a pre-Step-0 preload for fork dispatches only.
- `plugins/mill/scripts/_agent_dispatch.py`, `language_skills_directive()` — builds a `skills` list seeded with `` `code-quality` `` and appends per-language entries, then renders one of two prose sentences depending on whether any language was detected. Both branches say "load and follow these skills (non-optional)". Adding `prose` to the seed list is the whole change; the function's docstring ("plus ``code-quality`` for all batches") needs updating to match.
- `plugins/mill/templates/implementer-brief.md` and `fixer-batch-brief.md` — render `<LANGUAGE_SKILLS>` and list `Skill` in `## Tools`. No template edit needed; they inherit the change from the function.
- `plugins/mill/templates/fixer-holistic-brief.md`, `merge-in-conflict-brief.md`, `merge-in-verify-brief.md` — no `<LANGUAGE_SKILLS>` token and no `Skill` in `## Tools`. These get the inlined block. Note `fixer-holistic-brief.md` already instructs loading `mill-receiving-review` despite omitting `Skill` from its Tools list; that pre-existing inconsistency is not this task's to resolve, and the inlined block sidesteps it.
- The five reviewer templates — each opens with a `**If you find issues, REPORT them**` line, identity lines, and `<TOOL_RULE>`, then task-specific sections. They share no common header file today, so the block is either duplicated five times or introduced via an include if `_render.render` supports one. `_render.render` is token-substitution based and raises `KeyError` on any unresolved token, so a new shared token would have to be supplied by every call site that renders these templates — mill-plan should verify what `_render` actually supports before choosing.

**Stale `markdown` references to repoint**

- `plugins/mill/templates/review-output.schema.md` — one prose sentence: "`---`-style YAML frontmatter is reserved for SKILL.md and plugin manifests per the markdown skill."
- `plugins/mill/scripts/millpy-skills-index.py` — `_extract_frontmatter`'s docstring: "the one place `---` frontmatter is allowed by the markdown skill."
- `plugins/mill/scripts/tools/mdreflow/mdreflow.py` — module docstring names "the mill:markdown skill's semantic-line-break rule" and cites `plugins/mill/skills/markdown/SKILL.md`'s section by name. This is a one-shot sweep tool; repointing it at `prose`'s "Line breaks" section keeps the citation valid after the deletion.
- `SKILLS.md` at the repo root is generated by `mill-skills-index` from SKILL.md frontmatter and must be regenerated after the deletion. Its `conversation` row also carries the description string "Builds on `prose`", which comes from `conversation/SKILL.md`'s frontmatter and is unaffected.

**Existing test to update**

`plugins/mill/unit_tests/test-language-skills-directive.py` — six behaviour tests plus two render tests. Adding `prose` to the seed list does not break the existing `in` assertions or the negative assertions, but two things need attention: `test_no_recognized_languages`' docstring claims "code-quality only", and `test_context_excluded` asserts `"Go" not in directive`, so any added skill name must not contain the substring `Go` (`prose` does not). New positive assertions for `prose` belong in each test. Run via `plugins/mill/unit_tests/run-all.py`.

**Repo conventions that bear on the implementation**

- Generated markdown uses fenced ` ```yaml `, not `---` frontmatter — the rule being moved into `prose`.
- `print()` / `_log()` output is ASCII only.
- Verify commands for this Python project must start with a literal empty `PYTHONPATH=` prefix.

## Testing

**`_agent_dispatch.language_skills_directive()`** — update `plugins/mill/unit_tests/test-language-skills-directive.py`. TDD candidate: add the `prose` assertion to each of the six behaviour tests *before* editing the function, confirm they fail, then add `prose` to the seed list. Scenarios that must be covered: `prose` present for a Go-only batch, a Python-only batch, a C#-only batch, a mixed batch, and — most importantly — a batch with no recognized language, where `prose` and `code-quality` are the entire list. `prose` must appear exactly once in a mixed-language batch, mirroring the existing `code-quality`-appears-once assertion. Fix the `test_no_recognized_languages` docstring, which currently claims code-quality is the only skill.

**The load-directive convention test** — a new test file under `plugins/mill/unit_tests/`, named per the `test-<name>.py` convention and picked up by `run-all.py`. TDD candidate: write it first, confirm it fails against the current tree by naming the sites the proposal already identified, then fix those sites until it passes. Scenarios that must be covered: a file with a correct directive passes; a file naming `mill:conversation` in a load directive with no `mill:prose` fails; a file mentioning `mill:conversation` referentially with no load verb passes (this is the discrimination rule, and it is the assertion most likely to regress); a file naming both but in the wrong order. The tree walk reads real repo files, so the test doubles as the audit's regression guard — but the discrimination behaviour itself should be exercised against in-memory or tempfile fixtures rather than depending on which real files happen to exist, per the repo's unit-test convention.

**Prose content changes** — not testable. `prose/SKILL.md`, `code-comments/SKILL.md`, the reviewer templates' style block, and the three agent briefs' style block are all judgement text with no assertable behaviour. Do not add substring assertions on the style block's wording; a check that a template contains a particular sentence breaks on any rewording and tests nothing real.

**The `markdown` skill deletion** — verify by grep that no reference to `mill:markdown`, `markdown/SKILL.md`, or "the markdown skill" survives anywhere in the repo, and that `SKILLS.md` no longer lists a `markdown` row after regeneration.

## Q&A log

- **Q:** Structure of the staleness rule in `prose/SKILL.md` — one section or two? **A:** One section covering tallies, caller lists, and descriptively-cited names under a single principle.
- **Q:** Include a measurement-report exemption, given loomyard does not actually have one? **A:** Yes — tables of runtimes are exactly the case that is *supposed to* go stale when a new run happens.
- **Q:** Where does the caller-list rule live, given `code-comments` already has "No enumerated-consumer lists"? **A:** In `prose`. `code-comments` keeps a pointer plus its comment-specific example and rationale, stating the rule zero times itself.
- **Q:** Delete `markdown/SKILL.md` or keep a thin residual skill? **A:** Delete it; fold the fenced-YAML rule into `prose`. `prose`'s existing "Line breaks" section is sufficient — the extra elaboration dies with the file.
- **Q:** How to handle the filler/"svada" complaint, which cannot be re-observed from inside this task? **A:** Sharpen `prose` now. Add a cut-test, not a numeric cap — a cap would make agents drop content that is vital, since deleting is the cheapest way to satisfy a count. The extra per-sentence pass the cut-test costs is accepted, in preference to filler. "Don't repeat yourself" is already covered by "Say it once".
- **Q:** Reviewer templates — load directive or inlined block, given reviewers have no `Skill` tool? **A:** Inlined block. (Noted: bulk-mode reviewers are not in use at present, but the inlined form works for both dispatch shapes regardless.)
- **Q:** Which skills does `language_skills_directive()` add? **A:** `prose` only, alongside `code-quality`, and in the unconditional group — not the per-language group, since `prose` is language-agnostic. `conversation` is not needed by non-interactive agents.
- **Q:** Audit scope — the proposal's site list, or a full sweep? **A:** Full sweep, fix everything found.
- **Q:** Add an automated check, or just apply the fix? **A:** Add the check. Loomyard carries many tests of this shape and they work well.
- **Q:** How does the convention test avoid firing on referential mentions of `mill:conversation`? **A:** Match only load-directive shapes — a load verb near the skill name.
- **Q:** Which trees does the convention test walk? **A:** `plugins/*/skills/**/SKILL.md` and `plugins/mill/templates/*.md` — the shipped surface.
- **Q:** What does `handoff`'s emitted document instruct on its first line? **A:** "Load `mill:prose`, then `mill:conversation`". It cannot name `conversation` alone — `prose` would not get loaded.
- **Q:** Three more briefs write prose but omit `Skill` from their Tools list — in scope? **A:** Yes, under one derived rule: load directive where the brief grants `Skill`, inlined block where it does not.
