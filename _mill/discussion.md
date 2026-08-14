# Discussion: Extract a language-agnostic code-comments skill; add a general docstring-length ceiling, purpose-not-mechanism rule, mandatory file/module header, and prohibit measured-result/design-rationale narrative

```yaml
task: Extract a language-agnostic code-comments skill; add a general docstring-length ceiling, purpose-not-mechanism rule, mandatory file/module header, and prohibit measured-result/design-rationale narrative
slug: code-comments-skill-extraction
status: discussing
parent: main
```

## Problem

`csharp-comments`, `golang-comments`, and `python-comments` each carry their own full copy of several rules that are actually identical or near-identical across all three (semantic line-wrap style, "never comment out code", "no edit-history comments"). This duplication is itself a maintenance problem, but it also let real divergence creep in unnoticed: `python-comments` currently mandates the opposite of what the other two skills already say — it requires docstrings to narrate "How it works" in numbered algorithm steps, and requires an inline comment at every logical step. Separately, `csharp-comments` has no wording prohibiting a specific failure mode that was directly observed in production: `#858` reports XML doc comments in `NORCE-DrillingAndWells/Models` (`CuttingsBedLocalExchange`, `CuttingsBedContinuityContext`) ballooning to 40-55+ lines of "we tried X, measured Y, tried Z instead, measured N% better" debugging trails — content that belongs in inline why-comments, `_codeguide/` docs, or design-decision notes, never in the doc-comment block itself.

**Why now:** the triage discussion around `#858` widened from "fix csharp-comments' wording" to "the three skills were compared directly and the divergence is real, not stylistic" — extracting the shared core prevents this class of drift from recurring per-language.

## Scope

**In:**
- New shared skill `code-comments` at `plugins/mill/skills/code-comments/SKILL.md`, mirroring `code-quality`'s location and language-agnostic framing.
- Move already-identical/near-identical content into it:
  - The common core of the semantic line-wrap-style section (hard-wrap prohibition, one-sentence-per-line, clause-boundary rule, ambiguous-punctuation exception) — Go and C# are identical here modulo the tool-name sentence ("Godoc" vs. "XML-doc tooling"); Python's closing paragraph is genuinely different, not just a name swap (see `line-wrap-rendering-paragraph-stays-per-language` Decision) and does NOT move.
  - The "never comment out code" / "no edit-history comments" prohibited-patterns entries.
  - The purpose-not-mechanism principle already stated near-verbatim in `golang-comments` (Introduction, and the relevant lines of "Exported symbol doc comments") and `csharp-comments` ("XML documentation") — this is consolidation of existing duplicated content, not a new addition (corrected from an earlier draft that mischaracterized it as net-new; see Technical Context for the exact per-file sections to trim).
- Merge `golang-comments`' "No mechanical restatements" and `python-comments`' "No mechanical comments that restate what the code does" into one shared prohibited-patterns entry (same rule, previously worded differently in those two files). Note: `csharp-comments` has no equivalent entry today, so shipping this shared entry is net-new content for C#, not a pure consolidation there.
- Add to `code-comments` (genuinely new, language-wide, not present in any file today):
  - **Purpose-not-mechanism corollary**: an implementation that seems to need many comments to explain itself is a refactoring signal (decompose into well-named sub-functions with their own docstrings), not evidence the docstring needs to be longer. (The base principle itself is consolidated from Go/C#, per above — this corollary is the new part, and is what fixes Python's contradiction.)
  - **Length ceiling** (qualitative, not a hard count — see Decisions): doc comments rarely need to exceed ~10-15 lines; longer is treated as a symptom of implementation-narrative creep, not a size problem.
  - **Mandatory file/module header requirement**: every source file must open with a comment describing what the file contains and why, stated once here since the requirement's substance is identical across languages; each per-language skill keeps only its own syntax + one example.
  - **No end-of-line comments**: comments go on their own line, above the code — no per-language carve-out (see Decisions on the Go `const` block).
  - **Prohibited measured-result/design-rationale narrative**: doc comments must not contain measured numeric deltas, rejected-alternative trails, or reproduction/incident narrative. That belongs in inline why-comments, `_codeguide/` module docs, or `Doc/` design-decision notes — this directly fixes `#858`.
- Each of `golang-comments` / `python-comments` / `csharp-comments` opens with `**Load the `code-comments` skill first.**` as its first line under the H1 (mirroring `mill-plan/SKILL.md`'s Step-0 pattern), then keeps only genuinely language-specific content: placement syntax, `godoc`/XML-doc/Google-style mechanics, `<inheritdoc/>`, boolean-naming ("reports whether"), Python's `Args:`/`Returns:` usage, section dividers, error-wrap pattern, etc.
- Rewrite `python-comments`' "Function docstrings" and "Inline comments" sections to drop the "How it works" numbered-algorithm requirement and the "mandatory comment at every logical step" rule (see Decisions).
- Correct `python-comments`' module-docstring line that currently says "For pipeline or orchestration modules, describe the steps performed" (same how-narration violation, at the file-header level) to match the new shared header requirement.
- Add a file-header section to `csharp-comments` (it has none today): a `///`-style comment block at the top of the file, above `using`/`namespace` (see Decisions on why `///` over `/* */`).
- Rewrite `golang-comments`' "Constants and variables" example to remove end-of-line comments (see Decisions).
- Add a Go row (marker `go.mod`) to `workflow.md`'s Language Detection table, routing to `@golang:golang-build`, `golang-comments`, `golang-testing` — matching the Python/C# rows' shape; this closes Go's missing `git-commit`/`git-pr` lint/build routing, a narrower gap than originally stated (see `workflow-md-go-row` Decision).
- Re-run `millpy-skills-index.py` (or note it for `mill-go`) so `SKILLS.md` picks up the new `code-comments` entry — mechanical, not a design decision.

**Out:**
- The existing build/comments/testing three-way skill split per language (`golang-build`/`golang-comments`/`golang-testing`, etc.) — correct as-is, each triggers at a genuinely different workflow moment. Not touched.
- Go's package-level `godoc` comment (`// Package auth provides...`) — no analog in Python/C#, stays entirely Go-specific, untouched.
- Any change to non-comment content of the three per-language skills (naming, file-management, etc. — those live in other skills already).

## Decisions

### python-how-it-works-conflict

- Decision: Remove the "How it works" numbered-algorithm requirement from Python's function-docstring rules, and remove the "mandatory comment at every logical step" requirement from Python's inline-comments rules. When a function's steps genuinely need explaining, the guidance is to decompose it into named sub-functions that each get their own docstring — the decomposition itself becomes the documentation. Only when that isn't practical does a single inline comment inside the method body remain an accepted exception; it does not go in the docstring.
- Rationale: operator call. Python's current wording is the most severe instance of exactly the problem this task exists to fix (implementation-narrative creep in doc comments) — worse than what `#858` reported for C#, since it's not just tolerated but *required*. Structural decomposition keeps the "what+why from signature+doc alone" property intact without forcing narrative prose.
- Rejected: keeping Python's step-by-step narration as a permanent per-language exception for domain/quant code — rejected because it would leave the language-wide purpose-not-mechanism principle contradicted by its single largest consumer (`python-comments` is triggered on every `.py` file). Partial split (drop docstring narration, keep mandatory per-step inline comments) also rejected for the same reason — the inline-comment mandate is the same failure mode, just relocated.

### length-ceiling-form

- Decision: Qualitative ceiling, not a hard line count. State it as: doc comments rarely need to exceed ~10-15 lines; longer is a symptom that implementation-narrative has crept in, not a size problem to fix by trimming words.
- Rationale: operator call. A hard numeric ceiling invites exactly the wrong kind of compliance (cramming the same narrative into fewer, denser lines) instead of addressing why the comment got long in the first place. Framing it as a symptom ties it directly to the purpose-not-mechanism principle it's meant to reinforce.
- Rejected: hard numeric ceiling (mechanically checkable but gameable); no ceiling at all, relying solely on the prohibited-patterns list (leaves no signal for narrative that's off-topic in a new way the list didn't anticipate).

### shared-vs-duplicated-prose

- Decision: Rules that are substantively identical across languages (purpose-not-mechanism, length ceiling, file-header requirement, no-end-of-line-comments, the merged mechanical-restatement rule, plus the already-identical line-wrap-style and comment-out/edit-history entries) are stated exactly once in `code-comments`. Each per-language file keeps only its language-specific syntax and one code example per shared rule — never a restatement of the rule's substance.
- Rationale: operator call ("I do NOT like redundancy") — same principle that already justified extracting line-wrap-style; applying it narrowly (extract only the parts that happened to already be byte-identical) would leave the new rules duplicated three ways from day one, the opposite of what this task is for.
- Rejected: keeping full prose duplicated per language and only fixing/adding content in place — rejected as reintroducing the exact problem (undetected divergence between near-identical copies) that motivated this task.

### csharp-file-header-syntax

- Decision: C# file headers use a `///` comment block at the very top of the file, above `using`/`namespace` — not a plain `/* */` block comment.
- Rationale: operator call — consistent syntax with how every other doc comment in a C# file is written (`///` on members), even though C# has no dedicated "file-level" doc-comment concept the way Go's package comment does.
- Rejected: `/* */` block comment (technically simpler, avoids any doc-tooling ambiguity, but inconsistent with the rest of the file's comment style).
- Open edge case for implementation to verify: placing `///` above `using`/`namespace` with no declaration directly beneath it may trigger the compiler's CS1587 ("XML comment is not placed on a valid language element") warning depending on exact placement (directly above `namespace X { }` vs. above the first `using`). Not treated as blocking — verify during implementation with a real build; if it warns, the fallback is moving the `///` block to sit directly above the `namespace` declaration (namespaces are typically accepted) rather than above `using` statements.

### workflow-md-go-row

- Decision: Add a Go row (marker `go.mod`) to `workflow.md`'s Language Detection table, routing to `@golang:golang-build`, `golang-comments`, `golang-testing`.
- Rationale: review-driven correction (round 2 caught round 1's own rationale error). `golang-comments` is NOT unreachable without this row — `plugins/mill/scripts/_agent_dispatch.py`'s `language_skills_directive` already names `{lang}-comments` (including `golang-comments`) per-batch, independent of `workflow.md`, for any implementer/fixer batch that touches a `.go` file (`LANG_MAP` maps `.go` → `golang`). `workflow.md`'s table has a narrower, different purpose: it's what `git-commit`/`git-pr` (see those skills' "Detect the project language... run the lint/format/build step from the matching `{lang}-build` skill") use to find the `{lang}-build` skill for commit-time lint/format and PR-time build/test. The real gap this task surfaces is that Go has no row there at all, so `git-commit`/`git-pr` never auto-detect Go projects for `golang-build` routing — a genuine, if narrower and pre-existing, gap. Operator confirmed adding the row is still correct once the rationale was corrected.
- Rejected: leaving it as a documented pre-existing gap, out of scope — rejected because the fix is small, the gap is real (just not the one originally claimed), and this task is already touching `golang-comments` directly.

### line-wrap-rendering-paragraph-stays-per-language

- Decision: The line-wrap-style section splits at extraction. The common core — hard-wrap prohibition, one-sentence-per-line, the clause-boundary break rule, the ambiguous-punctuation exception — moves into shared `code-comments` verbatim (Go and C# already state this identically modulo the tool name). Each per-language file keeps its own short trailing note about how *its* tooling renders the result: Go/C# state that consecutive comment lines collapse into one rendered paragraph (so the semantic break is invisible when rendered); Python states the opposite — raw docstrings preserve literal newlines, so `help()`/`pydoc`/IDE tooltips display sentence-per-line text as short lines rather than reflowing it.
- Rationale: review-driven correction. An earlier discussion draft called the whole section "byte-for-byte duplicated modulo the tool-name sentence," which is true for Go vs. C# but false for Python — Python's closing paragraph makes a materially different (opposite) technical claim about rendering behavior, not just a different tool name. Operator confirmed the recommended fix: keep this genuine per-language behavioral difference where it belongs rather than losing it or forcing it into an artificial shared generalization.
- Rejected: moving everything verbatim including the rendering paragraph, generalized into one sentence covering both behaviors (loses the crisp collapse-vs-preserve distinction, reads as hedging); leaving the whole section duplicated per language, unmoved (reintroduces the redundancy this task exists to remove for the part that genuinely is identical).

### end-of-line-comments-no-carveout

- Decision: "No end-of-line comments" is a fully shared rule with no per-language carve-out. Go's own example (`StatusOK = 200 // OK` inside a `const` block) is rewritten to put each constant's comment on its own line above that constant, dropping the column-aligned end-of-line style.
- Rationale: operator call, explicitly for git-diff cleanliness — aligned end-of-line comments in a `const`/`var` block force realignment (and a noisy diff) of every sibling line whenever one identifier's length changes; per-constant above-line comments avoid that entirely and match the shared rule with zero exceptions.
- Rejected: shared rule with a Go carve-out for grouped `const`/`var` blocks (initially proposed as idiomatic-Go accommodation) — rejected in favor of the simpler, fully-uniform rule once the git-diff argument was raised.

## Technical context

Files to edit (all under this repo's `plugins/`):
- `plugins/mill/skills/code-quality/SKILL.md` — read-only reference; new `code-comments` mirrors its location (`plugins/mill/skills/<name>/SKILL.md`) and its language-agnostic framing/frontmatter shape.
- `plugins/golang/skills/golang-comments/SKILL.md` — extract: the "Introduction" section (~12-16, purpose-not-mechanism prose — trim to a one-line pointer at most, or drop entirely now that `code-comments` states it), the purpose-explanation portion of "Exported symbol doc comments" (~67-70, keep the Go-specific placement/naming rules in that section, drop the restated "what+why not how" prose), only the common core of the "Line-wrap style" section (~187-196, up to and including the "Readability wins over mechanical rule compliance" line — stop before the trailing "Godoc collapses..." paragraph at ~198, which stays per `line-wrap-rendering-paragraph-stays-per-language`), and the "never comment out code"/"no edit-history comments" entries plus "No mechanical restatements" entry from "Prohibited patterns" (~247-255). Add Step-0 load line. Rewrite "Constants and variables" example (~153-167) to remove end-of-line comments. Keep: file-level-comments syntax note + example (trim to syntax only, principle moves to `code-comments`), package doc comments (Go-only, untouched), boolean-naming, methods-on-type, interface-implementation `<inheritdoc/>`-equivalent, error-handling wrap pattern, "No `/* */` inside function bodies" (Go-specific, untouched).
- `plugins/python/skills/python-comments/SKILL.md` — reword the intro paragraph (~6-9, "The goal is **readable code** — a developer should be able to understand the module's logic by reading the docstrings and comments without tracing through the implementation") to drop "logic," which echoes the how-it-works framing being struck elsewhere in this file — reframe purpose-oriented, e.g. "understand what the module does and why, without tracing through the implementation," consistent with the shared purpose-not-mechanism principle. Extract: only the common core of "Line-wrap style" (~138-147, up to and including the "Readability wins over mechanical rule compliance" line — stop before the trailing per-language rendering paragraph at ~149-151, which stays per `line-wrap-rendering-paragraph-stays-per-language`), and the "never comment out code"/"no edit-history comments" and "no mechanical comments" entries from "Prohibited patterns" (~169-175). Add Step-0 load line. Trim "Module docstrings" bullets 16-17 ("Describe the module's purpose in plain narrative prose" / "list and briefly describe them") to syntax-only, mirroring the trim applied to `golang-comments`' "File-level comments" section — the purpose/content-description principle now lives in `code-comments`, this section keeps only the Python-specific mechanics (module-level docstring as the file's header, triple-quote placement). Correct the module-docstring line "For pipeline or orchestration modules, describe the steps performed" (~18) to match the new shared file-header requirement instead — do not describe steps. Rewrite "Function docstrings" (~20-51) to drop the "How it works" numbered-steps requirement, AND rewrite the "GOOD" example in "Good vs bad examples" (~53-73) to match — the current example's docstring still narrates a two-step algorithm (`1. Use SSB_quarterly...` `2. Use RSI_weekly...`), which is exactly the pattern being removed; replace it with a what+why example, or an example showing the decomposition-into-sub-functions guidance from `python-how-it-works-conflict`. Rewrite "Inline comments — narrate the reasoning" (~102-113) to drop the mandatory-every-step rule, per the `python-how-it-works-conflict` decision. Keep: Google-style formatting mechanics, `Args:`/`Returns:` guidance, class-docstring conventions, section dividers.
- `plugins/csharp/skills/csharp-comments/SKILL.md` — extract: the purpose-explanation portion of "XML documentation" (~14-16, keep the "public methods and classes must have `/// <summary>`" requirement, drop the restated "what+why not how" prose), only the common core of "Line-wrap style" (~30-40, up to and including the ambiguous-punctuation paragraph — keep the final "XML-doc tooling collapses..." paragraph in place per `line-wrap-rendering-paragraph-stays-per-language`), and "never comment out code"/"no edit-history comments" from "Prohibited patterns" (~65-70). Add Step-0 load line. Add a new file-header section per `csharp-file-header-syntax`. Keep: `<inheritdoc/>` rule, XML-doc placement, "no end-of-line comments" (already present at ~71-72 — now points to/matches the shared rule instead of restating it).
- `plugins/mill/skills/workflow/SKILL.md` — add a Go row to the Language Detection table (~71-74) per `workflow-md-go-row`: `| `go.mod` | Go | `@golang:golang-build`, `golang-comments`, `golang-testing` |`.
- `plugins/mill/scripts/millpy-skills-index.py` — regenerates `SKILLS.md` from frontmatter; run (or have `mill-go` run) after adding `code-comments/SKILL.md` so it appears in the index. No content decisions here, purely mechanical.

No `_codeguide/Overview.md` exists in this repo to navigate via; exploration used direct file reads and `SKILLS.md`/`INDEX.md` grep instead.

Precedent for the Step-0 load pattern: `plugins/mill/skills/mill-plan/SKILL.md` line 16-17 — `**Step 0: Load `mill:conversation`.** Load the `mill:conversation` skill via the Skill tool, unconditionally, immediately — before any other Entry step or phase.` The per-language skills should use the equivalent phrasing adapted to plain prose (not a numbered "Step 0", since these are content-reference skills, not orchestrator entry points) — e.g. `**Load the `code-comments` skill first.**` as the first line under the H1.

## Constraints

_No `CONSTRAINTS.md` present at hub root — no constraints beyond those captured in Decisions above._

## Testing

No automated tests apply — this task only edits Markdown `SKILL.md` prose. Verification is manual/textual:
- After editing, `grep` each of the three per-language files for the extracted section text (line-wrap-style prose, "never comment out code", "no edit-history comments", mechanical-restatement wording) to confirm none of it remains duplicated in place — ties directly to the operator's "no redundancy" requirement in `shared-vs-duplicated-prose`.
- Confirm each per-language file's first line under its H1 is the `**Load the `code-comments` skill first.**` line.
- Confirm `code-comments/SKILL.md` has valid frontmatter (`name: code-comments`, a one-line `description`) matching the shape of `code-quality/SKILL.md`, and that `millpy-skills-index.py` has been run so `SKILLS.md` lists it.
- Confirm Python's rewritten sections no longer contain "How it works" / numbered-algorithm-step / "mandatory" per-step inline-comment language, and that the sub-function-decomposition guidance from `python-how-it-works-conflict` is present somewhere reachable (either in `code-comments`' purpose-not-mechanism section or inline in `python-comments`).
- Confirm Go's rewritten `const` example has no end-of-line comments.
- If feasible during implementation, a throwaway `.cs` file with the proposed `///` file-header placement can be compiled to check for CS1587 — not required to block completion, per the `csharp-file-header-syntax` decision's open edge case.

## Q&A log

- **Q:** Python's docstring/inline-comment rules currently mandate "How it works" narration and mandatory per-step inline comments — directly opposite the new purpose-not-mechanism principle. How to resolve? **A:** Drop both requirements; when steps genuinely need explaining, decompose into sub-functions with their own docstrings. A single inline comment inside the method remains an accepted last-resort exception, never in the docstring.
- **Q:** How should the length ceiling be expressed? **A:** Qualitative/symptom-based (~10-15 lines rarely exceeded, framed as implementation-narrative creep), not a hard numeric count.
- **Q:** File/module header — shared normative text in `code-comments`, or keep full prose duplicated per language? **A:** Shared, stated once; per-language files keep only their syntax + example. Operator: "I do NOT like redundancy."
- **Q:** What syntax should C#'s new file header use, given `///` is conventionally reserved for members? **A:** `///` above `using`/`namespace`, for consistency with the rest of the file's comment style — not `/* */`. Operator flagged `/* */` as available but preferred `///`.
- **Q:** Where does "Load the code-comments skill first" go in each per-language file? **A:** First line under the H1, mirroring `mill-plan`'s Step-0 phrasing.
- **Q:** Merge Go's "No mechanical restatements" and Python's "No mechanical comments that restate what the code does" into one shared entry? **A:** Yes.
- **Q:** Should "no end-of-line comments" become a shared rule, and if so does Go's `const`-block end-of-line style get a carve-out? **A:** Shared rule, no carve-out — Go's `const` example is rewritten to per-constant above-line comments instead. Operator: cleaner `git diff` since aligned end-of-line comments force realignment of sibling lines on any identifier-length change.
