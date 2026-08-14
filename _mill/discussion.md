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
- Move already-identical content into it: semantic line-wrap style section (currently byte-for-byte duplicated modulo the tool-name sentence — "Godoc"/"XML-doc tooling"/raw Python docstrings — in all three files), and the "never comment out code" / "no edit-history comments" prohibited-patterns entries.
- Merge `golang-comments`' "No mechanical restatements" and `python-comments`' "No mechanical comments that restate what the code does" into one shared prohibited-patterns entry (same rule, previously worded differently).
- Add to `code-comments` (new, language-wide, not present in any file today in this general form):
  - **Purpose-not-mechanism principle**: a doc comment must convey what the symbol does and why it exists, understandable from signature + doc alone, and must never narrate how it works internally. Corollary: an implementation that seems to need many comments to explain itself is a refactoring signal (decompose into well-named sub-functions with their own docstrings), not evidence the docstring needs to be longer.
  - **Length ceiling** (qualitative, not a hard count — see Decisions): doc comments rarely need to exceed ~10-15 lines; longer is treated as a symptom of implementation-narrative creep, not a size problem.
  - **Mandatory file/module header requirement**: every source file must open with a comment describing what the file contains and why, stated once here since the requirement's substance is identical across languages; each per-language skill keeps only its own syntax + one example.
  - **No end-of-line comments**: comments go on their own line, above the code — no per-language carve-out (see Decisions on the Go `const` block).
  - **Prohibited measured-result/design-rationale narrative**: doc comments must not contain measured numeric deltas, rejected-alternative trails, or reproduction/incident narrative. That belongs in inline why-comments, `_codeguide/` module docs, or `Doc/` design-decision notes — this directly fixes `#858`.
- Each of `golang-comments` / `python-comments` / `csharp-comments` opens with `**Load the `code-comments` skill first.**` as its first line under the H1 (mirroring `mill-plan/SKILL.md`'s Step-0 pattern), then keeps only genuinely language-specific content: placement syntax, `godoc`/XML-doc/Google-style mechanics, `<inheritdoc/>`, boolean-naming ("reports whether"), Python's `Args:`/`Returns:` usage, section dividers, error-wrap pattern, etc.
- Rewrite `python-comments`' "Function docstrings" and "Inline comments" sections to drop the "How it works" numbered-algorithm requirement and the "mandatory comment at every logical step" rule (see Decisions).
- Correct `python-comments`' module-docstring line that currently says "For pipeline or orchestration modules, describe the steps performed" (same how-narration violation, at the file-header level) to match the new shared header requirement.
- Add a file-header section to `csharp-comments` (it has none today): a `///`-style comment block at the top of the file, above `using`/`namespace` (see Decisions on why `///` over `/* */`).
- Rewrite `golang-comments`' "Constants and variables" example to remove end-of-line comments (see Decisions).
- Re-run `millpy-skills-index.py` (or note it for `mill-go`) so `SKILLS.md` picks up the new `code-comments` entry — mechanical, not a design decision.

**Out:**
- The existing build/comments/testing three-way skill split per language (`golang-build`/`golang-comments`/`golang-testing`, etc.) — correct as-is, each triggers at a genuinely different workflow moment. Not touched.
- `workflow.md`'s language-detection table (`plugins/mill/skills/workflow/SKILL.md`) — it already routes to `python-comments`/`golang-comments`/`csharp-comments`, which now internally load `code-comments`; the table itself needs no new row.
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

### end-of-line-comments-no-carveout

- Decision: "No end-of-line comments" is a fully shared rule with no per-language carve-out. Go's own example (`StatusOK = 200 // OK` inside a `const` block) is rewritten to put each constant's comment on its own line above that constant, dropping the column-aligned end-of-line style.
- Rationale: operator call, explicitly for git-diff cleanliness — aligned end-of-line comments in a `const`/`var` block force realignment (and a noisy diff) of every sibling line whenever one identifier's length changes; per-constant above-line comments avoid that entirely and match the shared rule with zero exceptions.
- Rejected: shared rule with a Go carve-out for grouped `const`/`var` blocks (initially proposed as idiomatic-Go accommodation) — rejected in favor of the simpler, fully-uniform rule once the git-diff argument was raised.

## Technical context

Files to edit (all under this repo's `plugins/`):
- `plugins/mill/skills/code-quality/SKILL.md` — read-only reference; new `code-comments` mirrors its location (`plugins/mill/skills/<name>/SKILL.md`) and its language-agnostic framing/frontmatter shape.
- `plugins/golang/skills/golang-comments/SKILL.md` — extract: "Line-wrap style" section (lines ~187-217 as currently laid out), "never comment out code"/"no edit-history comments" entries and "No mechanical restatements" entry from "Prohibited patterns" (~247-255). Add Step-0 load line. Rewrite "Constants and variables" example (~153-167) to remove end-of-line comments. Keep: file-level-comments syntax note + example (trim to syntax only, principle moves to `code-comments`), package doc comments (Go-only, untouched), exported-symbol placement rules, boolean-naming, methods-on-type, interface-implementation `<inheritdoc/>`-equivalent, error-handling wrap pattern, "No `/* */` inside function bodies" (Go-specific, untouched).
- `plugins/python/skills/python-comments/SKILL.md` — extract: "Line-wrap style" section (~138-167), "never comment out code"/"no edit-history comments" and "no mechanical comments" entries from "Prohibited patterns" (~169-175). Add Step-0 load line. Rewrite "Function docstrings" (~20-51) to drop the "How it works" numbered-steps requirement; rewrite "Inline comments — narrate the reasoning" (~102-113) to drop the mandatory-every-step rule, per the `python-how-it-works-conflict` decision. Correct the module-docstring line "For pipeline or orchestration modules, describe the steps performed" (~18) to match the new shared file-header requirement instead. Keep: Google-style formatting mechanics, `Args:`/`Returns:` guidance, class-docstring conventions, section dividers.
- `plugins/csharp/skills/csharp-comments/SKILL.md` — extract: "Line-wrap style" section (~30-63), "never comment out code"/"no edit-history comments" from "Prohibited patterns" (~65-70). Add Step-0 load line. Add a new file-header section per `csharp-file-header-syntax`. Keep: `<inheritdoc/>` rule, XML-doc placement, "no end-of-line comments" (already present at ~71-72 — now points to/matches the shared rule instead of restating it).
- `plugins/mill/skills/workflow/SKILL.md` — no edit needed; its language-detection table (~73-74) already routes to the three per-language skills.
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
