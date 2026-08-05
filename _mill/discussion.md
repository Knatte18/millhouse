# Discussion: markdown skill: use semantic line breaks instead of one unbroken line per paragraph

```yaml
task: markdown skill: use semantic line breaks instead of one unbroken line per paragraph
slug: markdown-semantic-line-breaks
status: discussing
parent: main
```

## Problem

`plugins/mill/skills/markdown/SKILL.md`'s "No fixed-column hard-wrapping" section (currently lines 24-26) correctly bans fixed-column hard-wrapping — the previous bug it fixed was agents breaking lines mid-word/mid-phrase at a fixed character count (e.g. `file-` / `based`).
But the fix it landed on, "write prose paragraphs as a single unbroken line each," has two costs specific to LLM-driven mill runs, per GitHub issue #775:

1. **Addressing precision.** A reviewer citing `file.md:47` points at an entire paragraph (sometimes 300+ words), not a sentence, because the whole paragraph is one line.
2. **Diff locality / token waste.** A single-word edit inside a long paragraph causes git diff to show the whole paragraph as removed-and-re-added, and an orchestrator re-verifying an agent's edit pays for re-reading the whole paragraph in tokens, not just the changed sentence.

The rule's author (the user, in this conversation) introduced the "single unbroken line" prescription a few days before this task without weighing the LLM-addressing cost.
Concrete evidence cited in issue #775: six rounds of plan review on a 46-card plan document, each round requiring a full diff re-read of eight markdown files, because paragraph-level line granularity made every small edit look like a full-paragraph rewrite in the diff.

**Why now:** this is actively costing tokens on every mill-plan/mill-go review round across the project, and the fix is a small, contained rule-text change.

## Scope

**In:**

- Rewrite `plugins/mill/skills/markdown/SKILL.md`'s "No fixed-column hard-wrapping" section to prescribe semantic line breaks (one line break per sentence, with a mechanical trigger for breaking at internal independent-clause boundaries in long compound sentences) instead of "single unbroken line per paragraph."
The rule applies to prose paragraphs; it does not apply inside table cells, where a bare newline breaks table parsing.
Blockquote content is a stylistic exception, not a CommonMark syntax requirement — CommonMark permits multiple `>`-prefixed lines to soft-wrap into one rendered paragraph the same as a normal paragraph, so semantic line breaks could technically apply there too; the rule keeps blockquote content on one line per default project style; most existing blockquotes in this repo are short one-liners today, though one multi-line exception exists (`plugins/mill/skills/mill-finalize/SKILL.md` lines 135-139, a 5-line quoted report block) — that file is untouched by this task per the forward-only decision above, and the exemption is a default for new blockquote content, not a claim that every existing blockquote is already single-line.
- Add the equivalent new guidance to `plugins/python/skills/python-comments/SKILL.md`, `plugins/golang/skills/golang-comments/SKILL.md`, and `plugins/csharp/skills/csharp-comments/SKILL.md` — none of the three currently has any line-wrap rule for docstrings/doc comments/inline comments, so this is new guidance in each, not a rewrite.
- Fix `golang-comments/SKILL.md`'s own existing multi-line comment example that hard-wraps mid-sentence (currently lines 29-31), which would contradict the new rule sitting in the same file.
Lines 197-198 were also checked and already break at a semicolon — a valid clause-boundary point under the new rule — so no fix is needed there.
- Add a short before/after example to each of the four files illustrating the new one-sentence-per-line style, matching each file's existing "good vs bad example" pattern.
At least one of the four examples must also demonstrate the clause-boundary break (comma+coordinating-conjunction or semicolon before an independent clause) — the sentence-per-line case alone doesn't illustrate the rule's one genuinely ambiguous judgment call.
The same example must also demonstrate a negative case — a comma+coordinating-conjunction that does NOT trigger a break because no second independent clause follows (see the "Break granularity" decision below for why this negative case matters).
`markdown/SKILL.md` has no existing fenced bad/good example anywhere (it is pure prose) — its new example should take the form of a compact "Example" subsection with a fenced ` ```markdown ` before/after snippet (bad: single-line paragraph; good: semantic-line-broken version), matching the before/after spirit of the other three files without importing their full "Bad example"/"Good example" heading structure into a file that has never used it.
- Fix `python-comments/SKILL.md`'s own existing docstring example (lines 63-64 and 66-67, inside the `create_CBI_from_SSB_and_RSI` `GOOD` example), which hard-wraps mid-sentence at a fixed column — the same defect already found and fixed in `golang-comments` lines 29-31, applied here for the same reason: it lives inside the very file being edited to introduce the rule.

**Out:**

- No reformatting of any already-committed generated markdown elsewhere in the repo or on other task branches (e.g. the sample `discussion.md` found on `mill-validate-verify-diagnostics-gaps`, which currently has 300-word single-line paragraphs). The user explicitly deferred this to a follow-up task — the new rule governs newly-written prose going forward only.
- No reformatting of `plugins/mill/templates/discussion.md`'s own instructional HTML comment (lines 1-10), even though it was found to already hard-wrap mid-sentence at ~70-75 columns and technically violates the *current* rule too. Same follow-up-task deferral as above; it is not the file this task edits.
- No automated linter, pre-commit hook, or CI check for markdown/comment line-wrap style. None exists today (confirmed during exploration) and none is being added — this remains a pure style convention enforced by the writing agent following the SKILL.md instruction.
- No change to any other section of the four SKILL.md files being touched (e.g. `python-comments`'s docstring-style rules, `golang-comments`'s doc-comment-content rules, `csharp-comments`'s `<inheritdoc/>` rule) beyond adding the new line-wrap guidance and fixing the two contradictory examples noted above (golang-comments lines 29-31, python-comments lines 63-64/66-67).

## Decisions

### Break granularity: sentence-per-line, plus clause-boundary breaks for long compound sentences

- Decision: the base rule is one line break per sentence.
On top of that, break also at internal independent-clause boundaries inside a single sentence — specifically before a coordinating conjunction ("but"/"and"/"or") or a semicolon, but ONLY when what follows is a second independent clause with its own subject and verb.
A comma+conjunction that joins a list item or a compound predicate (no second subject+verb) does NOT trigger a break.
- Rationale: pure sentence-only breaking is simpler and fully solves the addressing problem, but LLM-generated review/discussion prose frequently produces long run-on compound sentences; without the clause-boundary trigger, a single long sentence would still produce an imprecise diff/citation target.
The trigger is not a bare "comma+conjunction" pattern-match — discussion-review round 3 found that framing false-positives on real content (`python-comments/SKILL.md`'s own "...information...on how the index was created, and a "count" column representative..." is comma+"and" joining a list of two noun phrases, not two independent clauses).
The corrected disambiguator (second independent clause required) is still a concrete, checkable test — not "break wherever feels right" — so it stays workable for a writing agent, just not literally mechanical string-matching.
- Rejected: sentence-only breaking (simpler, but leaves long compound sentences under-addressed); breaking at every comma regardless of clause independence (too aggressive — would fragment lists and appositives that read fine as part of one line); the original bare "comma+conjunction" framing (rejected in round 3 — false-positives on lists and compound predicates, see the required negative worked example in Scope bullet 4).

### Ambiguous sentence-ending punctuation: don't force a break

- Decision: when the sentence-ending punctuation is ambiguous — e.g. a period that's part of a URL, or an abbreviation like "e.g." or "etc." — do not force a line break there.
Readability wins over mechanical rule compliance in that edge case.
- Rationale: forcing a break on every literal `.`/`!`/`?` without judgment would break mid-URL or mid-abbreviation, reintroducing exactly the kind of nonsensical mid-token break the original "No fixed-column hard-wrapping" rule was written to eliminate.
- Rejected: strict mechanical "always break on sentence-ending punctuation, no exceptions" — rejected because it regresses the original bug this section exists to prevent.

### Markdown-specific: forbid trailing-whitespace/backslash hard breaks

- Decision: the markdown skill's rule text must explicitly state that a plain newline (soft break) is required — never a line ending in two trailing spaces or a backslash (both force a real `<br>` in rendered output).
- Rationale: CommonMark treats a single bare newline inside a paragraph as a soft break, rendered as a space by any conforming renderer (GitHub, VS Code preview, etc.) — this is what makes semantic line breaks visually invisible to a reader while still being addressable/diffable in source.
A trailing-whitespace or backslash line ending forces an actual visible line break in rendered output, which would change how the document reads and is very easy for a writing agent to introduce by accident (e.g. an editor that auto-trims or preserves trailing spaces inconsistently).
- Rejected: leaving this unstated and trusting agents not to trail whitespace — rejected because it is a silent, hard-to-notice failure mode (invisible trailing spaces) with a visible, wrong result (unwanted line breaks in rendered docs).
This is markdown-specific; it does not apply to the three code-comment skills, since Python/Go/C# comment syntax has no equivalent trailing-whitespace hard-break behavior.

### Scope extension: also update python-comments, golang-comments, csharp-comments

- Decision: apply the same one-sentence-per-line (+ clause-boundary trigger) principle to docstrings, doc comments, and inline comments in all three language-specific comment skills, not only to `markdown/SKILL.md`.
- Rationale: the underlying problems (imprecise line-citation addressing, token-wasteful diffs on small edits) apply equally to multi-sentence prose inside a Python docstring, a Go doc comment, or a C# XML `<summary>` block — all three are reviewed and diffed the same way markdown prose is.
Godoc and XML-doc tooling collapse consecutive comment lines into one rendered paragraph the same way CommonMark does for markdown, so the soft-break-is-invisible property holds there too.
Python docstrings are different: raw `\n` characters are preserved, and common consumption paths (`help()`, `pydoc`, many IDE tooltips) print the docstring text as-is rather than reflowing it, so a sentence-per-line docstring may display as short lines instead of one flowing paragraph.
This risk is accepted: sentence-per-line prose is still fully readable either way, and the addressing/diff-locality benefit — the actual goal of this task — holds regardless of whether the display reflows it.
- Rejected: limiting scope to markdown only and treating code comments as a separate follow-up — rejected by the user explicitly, who confirmed extending scope to "csharp and other comments" in this same task rather than deferring it.

### Existing-content reformatting: forward-only, except within the four files being edited

- Decision: the new rule applies to newly-written prose going forward.
Do not reformat any already-committed generated markdown or code comments elsewhere in the repo or on other branches.
The one exception is `golang-comments/SKILL.md`'s own existing multi-line comment example (lines 29-31), which gets fixed as part of this task because it lives inside the very file being edited to introduce the new rule, and leaving it contradictory would make the skill's own documentation self-inconsistent.
(Lines 197-198 in the same file were also checked and already comply with the new rule — they break at a semicolon, a valid clause-boundary point — so they are not part of this exception.)
- Rationale: retroactive reformatting of existing committed content is unbounded scope (unknown number of files across history and other task branches) and was not what GitHub issue #775 asked for; the user explicitly confirmed this should be a follow-up task.
Fixing the two examples inside `golang-comments/SKILL.md` is different in kind — it is a direct, bounded consequence of editing that specific file's own rule text, not a retroactive sweep.
- Rejected: reformatting nothing at all, including the two contradictory examples in the file being edited (would leave the skill's own doc self-contradictory); reformatting broadly across the repo (explicitly deferred by the user to a follow-up task).

## Technical context

- Target files (all four are self-contained `SKILL.md` files with YAML frontmatter for skill metadata only — see CLAUDE.md's "YAML frontmatter (`---`) is reserved for system-parsed metadata in skill definitions"):
  - `plugins/mill/skills/markdown/SKILL.md` — 26 lines total; the section to rewrite is "## No fixed-column hard-wrapping," currently lines 24-26. This file has no existing fenced bad/good example anywhere (pure prose) — its new example is additive in the same sense as `csharp-comments`'s, but should still take a compact fenced-snippet "Example" form (see Scope bullet 4) rather than staying prose-only, so the expected output is unambiguous.
  - `plugins/python/skills/python-comments/SKILL.md` — 138 lines; has an existing "Good vs bad examples" pattern (e.g. lines 51-73, 111-132) to match when adding the new example. Its own `GOOD` docstring example (lines 63-64, 66-67) needs the same fixed-column-hard-wrap fix as `golang-comments` — see Scope bullet 5.
  - `plugins/golang/skills/golang-comments/SKILL.md` — 214 lines; has an existing "Bad example" / "Good example" pattern throughout (e.g. lines 67-81, 89-101); the example needing a line-wrap fix is at lines 29-31 (file-level comment example). The error-wrapping example at lines 197-198 was checked and already breaks at a semicolon — a valid clause-boundary point under the new rule — so it needs no change.
  - `plugins/csharp/skills/csharp-comments/SKILL.md` — 34 lines; currently has no multi-line comment example of any kind, so the new example is additive, not a fix.
- No other file in the repo references or restates this line-wrapping convention (confirmed by search) — the four target files are the complete blast radius for the rule text itself.
- No linter, pre-commit hook, or CI check enforces markdown or comment line-wrap style anywhere in this repo (confirmed by search) — this remains purely SKILL.md-instruction-driven, same as today.
- CommonMark soft-break semantics (bare newline inside a paragraph renders as a space) are the mechanism that makes this change safe for markdown; Go's godoc and C#'s XML-doc tooling have an equivalent paragraph-joining behavior for consecutive comment lines, which is why the same principle transfers to the three code-comment skills.

## Constraints

No `CONSTRAINTS.md` exists at the hub root (confirmed absent during exploration) — no project-wide constraints beyond what's captured above.

## Testing

This task changes only skill instruction text (four `SKILL.md` files) — there is no runtime code, so there is no automated test surface.
Verification is by inspection: mill-plan should confirm that each rewritten/added section actually follows its own new rule (i.e. the rule text itself is written with one-sentence-per-line, dogfooding the convention it describes), and that the fixed `golang-comments` example (lines 29-31) and the fixed `python-comments` example (lines 63-64/66-67) no longer break mid-sentence.
No TDD candidates apply.

## Q&A log

- **Q:** Should this task also update `python-comments`/`golang-comments` with the same principle, or stay confined to the markdown skill (per the literal wiki brief)? **A:** Yes, extend scope — and also include `csharp-comments`, which is the third and last comment-convention skill in the repo (no others exist).
- **Q:** Should the break rule be sentence-only, or also break at internal clause boundaries for long compound sentences? **A:** User asked for a judgment call; landed on sentence-per-line plus a mechanical clause-boundary trigger (comma+coordinating-conjunction or semicolon) rather than pure sentence-only or vague "break wherever feels right."
- **Q:** Should already-existing committed markdown/comments be reformatted under the new rule, or does it apply going forward only? **A:** Going forward only — reformatting existing content becomes a separate follow-up task, with the narrow exception of the contradictory example inside `golang-comments/SKILL.md` itself (fixed as a direct consequence of editing that file, not a retroactive sweep).
- **Q:** (Discussion-review round 1, gap) `golang-comments` lines 197-198 were listed alongside lines 29-31 as needing a line-wrap fix — is that accurate? **A:** No — verified against source, 197-198 already breaks at a semicolon, a valid clause-boundary point under the new rule. Only lines 29-31 actually violate; the discussion's scope/decision sections were corrected to say so.
- **Q:** (Discussion-review round 1, gap) Does extending scope to `python-comments` carry the same "soft-break-is-invisible" guarantee as markdown/Go/C#? **A:** No — raw Python docstrings preserve literal newlines and common tooling (`help()`, `pydoc`, IDE tooltips) doesn't reflow them the way CommonMark/godoc/XML-doc do. Accepted as a non-issue: sentence-per-line docstring text is still fully readable even displayed as short lines, and the addressing/diff-locality goal holds regardless of rendering.
- **Q:** (Discussion-review round 1, gap) Should the required before/after examples include one demonstrating the clause-boundary trigger specifically, not just sentence-per-line? **A:** Yes — the clause-boundary judgment (comma+coordinating-conjunction or semicolon before an independent clause) is the one genuinely ambiguous part of the rule and needs at least one worked example.
- **Q:** (Discussion-review round 2, gap) `markdown/SKILL.md` has no existing bad/good example pattern to match (unlike the three comment skills) — what format should its new example take? **A:** A compact "Example" subsection with a fenced ` ```markdown ` before/after snippet (bad: single-line paragraph; good: semantic-line-broken version) — matches the before/after spirit of the other files without importing their full heading structure into a file that's always been pure prose.
- **Q:** (Discussion-review round 3, gap) `python-comments/SKILL.md`'s own docstring example already hard-wraps mid-sentence at a fixed column (lines 63-64, 66-67) — same defect as golang-comments 29-31, which we already agreed to fix. Should this get the same in-file fix? **A:** Yes — consistent with the golang precedent; it lives inside the very file being edited.
- **Q:** (Discussion-review round 3, gap) The "mechanical" comma+conjunction clause-boundary trigger false-positives on lists/compound predicates (e.g. python-comments' own "...on how the index was created, and a "count" column..."). How to fix? **A:** Restate the trigger as requiring a second independent clause (subject+verb) after the comma/semicolon, not a bare pattern-match; require a negative worked example (comma+conjunction that should NOT break) alongside the positive one.
- **Q:** (Discussion-review round 3, note) Line counts for markdown/SKILL.md and python-comments/SKILL.md were off by one. **A:** Corrected to 26 and 138 lines respectively (verified via `wc -l`).
- **Q:** (Discussion-review round 3, note) The blockquote CommonMark justification conflated a syntax requirement with a single-line constraint that doesn't actually follow from it. **A:** Restated as a stylistic default (repo's existing blockquotes are short one-liners today) rather than a CommonMark-forced rule.
- **Q:** (Discussion-review round 4, gap) Scope > Out still said "the one contradictory example" after round 3 added a second (python-comments). **A:** Corrected to name both: golang-comments lines 29-31, python-comments lines 63-64/66-67.
- **Q:** (Discussion-review round 4, gap) Testing section misattributed both fixed examples to golang-comments. **A:** Corrected to attribute one fixed example to golang-comments (29-31) and the other to python-comments (63-64/66-67).
- **Q:** (Discussion-review round 5, gap) The blockquote exemption's rationale claimed "this repo's existing blockquotes are all short one-liners today" — is that accurate? **A:** No — `plugins/mill/skills/mill-finalize/SKILL.md` lines 135-139 is a genuine 5-line multi-line blockquote. Corrected the rationale to acknowledge this exception (untouched by this task, per the forward-only decision) rather than claiming a false repo-wide survey result.
- **Q:** Should discussion review continue to round 6? **A:** No — operator called it done after round 5's fix; remaining review rounds (up to max_review_rounds=8) explicitly waived. `python-comments`/`golang-comments`/`csharp-comments` unification into one shared comments skill was raised as a related idea but explicitly deferred to a separate follow-up task, not folded into this task's scope.
