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
- Add the equivalent new guidance to `plugins/python/skills/python-comments/SKILL.md`, `plugins/golang/skills/golang-comments/SKILL.md`, and `plugins/csharp/skills/csharp-comments/SKILL.md` — none of the three currently has any line-wrap rule for docstrings/doc comments/inline comments, so this is new guidance in each, not a rewrite.
- Fix `golang-comments/SKILL.md`'s own existing multi-line comment examples (currently lines 29-31 and 197-198), which already hard-wrap mid-sentence and would contradict the new rule sitting in the same file.
- Add a short before/after example to each of the four files illustrating the new one-sentence-per-line style, matching each file's existing "good vs bad example" pattern.

**Out:**

- No reformatting of any already-committed generated markdown elsewhere in the repo or on other task branches (e.g. the sample `discussion.md` found on `mill-validate-verify-diagnostics-gaps`, which currently has 300-word single-line paragraphs). The user explicitly deferred this to a follow-up task — the new rule governs newly-written prose going forward only.
- No reformatting of `plugins/mill/templates/discussion.md`'s own instructional HTML comment (lines 1-10), even though it was found to already hard-wrap mid-sentence at ~70-75 columns and technically violates the *current* rule too. Same follow-up-task deferral as above; it is not the file this task edits.
- No automated linter, pre-commit hook, or CI check for markdown/comment line-wrap style. None exists today (confirmed during exploration) and none is being added — this remains a pure style convention enforced by the writing agent following the SKILL.md instruction.
- No change to any other section of the four SKILL.md files being touched (e.g. `python-comments`'s docstring-style rules, `golang-comments`'s doc-comment-content rules, `csharp-comments`'s `<inheritdoc/>` rule) beyond adding the new line-wrap guidance and fixing the one contradictory example noted above.

## Decisions

### Break granularity: sentence-per-line, plus clause-boundary breaks for long compound sentences

- Decision: the base rule is one line break per sentence.
On top of that, break also at internal independent-clause boundaries inside a single sentence — specifically before a coordinating conjunction ("but"/"and"/"or") that joins two independent clauses, or at a semicolon.
- Rationale: pure sentence-only breaking is simpler and fully solves the addressing problem, but LLM-generated review/discussion prose frequently produces long run-on compound sentences; without the clause-boundary trigger, a single long sentence would still produce an imprecise diff/citation target.
The clause-boundary trigger is mechanical (comma+conjunction or semicolon), not "break wherever feels right," so it stays unambiguous for a writing agent.
- Rejected: sentence-only breaking (simpler, but leaves long compound sentences under-addressed); breaking at every comma regardless of clause independence (too aggressive — would fragment lists and appositives that read fine as part of one line).

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
- Rejected: limiting scope to markdown only and treating code comments as a separate follow-up — rejected by the user explicitly, who confirmed extending scope to "csharp and other comments" in this same task rather than deferring it.

### Existing-content reformatting: forward-only, except within the four files being edited

- Decision: the new rule applies to newly-written prose going forward.
Do not reformat any already-committed generated markdown or code comments elsewhere in the repo or on other branches.
The one exception is `golang-comments/SKILL.md`'s own existing multi-line comment examples (lines 29-31, 197-198), which get fixed as part of this task because they live inside the very file being edited to introduce the new rule, and leaving them contradictory would make the skill's own documentation self-inconsistent.
- Rationale: retroactive reformatting of existing committed content is unbounded scope (unknown number of files across history and other task branches) and was not what GitHub issue #775 asked for; the user explicitly confirmed this should be a follow-up task.
Fixing the two examples inside `golang-comments/SKILL.md` is different in kind — it is a direct, bounded consequence of editing that specific file's own rule text, not a retroactive sweep.
- Rejected: reformatting nothing at all, including the two contradictory examples in the file being edited (would leave the skill's own doc self-contradictory); reformatting broadly across the repo (explicitly deferred by the user to a follow-up task).

## Technical context

- Target files (all four are self-contained `SKILL.md` files with YAML frontmatter for skill metadata only — see CLAUDE.md's "YAML frontmatter (`---`) is reserved for system-parsed metadata in skill definitions"):
  - `plugins/mill/skills/markdown/SKILL.md` — 27 lines total; the section to rewrite is "## No fixed-column hard-wrapping," currently lines 24-26.
  - `plugins/python/skills/python-comments/SKILL.md` — 139 lines; has an existing "Good vs bad examples" pattern (e.g. lines 51-73, 111-132) to match when adding the new example.
  - `plugins/golang/skills/golang-comments/SKILL.md` — 214 lines; has an existing "Bad example" / "Good example" pattern throughout (e.g. lines 67-81, 89-101); the two examples needing a line-wrap fix are at lines 29-31 (file-level comment example) and 197-198 (error-wrapping example).
  - `plugins/csharp/skills/csharp-comments/SKILL.md` — 34 lines; currently has no multi-line comment example of any kind, so the new example is additive, not a fix.
- No other file in the repo references or restates this line-wrapping convention (confirmed by search) — the four target files are the complete blast radius for the rule text itself.
- No linter, pre-commit hook, or CI check enforces markdown or comment line-wrap style anywhere in this repo (confirmed by search) — this remains purely SKILL.md-instruction-driven, same as today.
- CommonMark soft-break semantics (bare newline inside a paragraph renders as a space) are the mechanism that makes this change safe for markdown; Go's godoc and C#'s XML-doc tooling have an equivalent paragraph-joining behavior for consecutive comment lines, which is why the same principle transfers to the three code-comment skills.

## Constraints

No `CONSTRAINTS.md` exists at the hub root (confirmed absent during exploration) — no project-wide constraints beyond what's captured above.

## Testing

This task changes only skill instruction text (four `SKILL.md` files) — there is no runtime code, so there is no automated test surface.
Verification is by inspection: mill-plan should confirm that each rewritten/added section actually follows its own new rule (i.e. the rule text itself is written with one-sentence-per-line, dogfooding the convention it describes), and that the two fixed `golang-comments` examples no longer break mid-sentence.
No TDD candidates apply.

## Q&A log

- **Q:** Should this task also update `python-comments`/`golang-comments` with the same principle, or stay confined to the markdown skill (per the literal wiki brief)? **A:** Yes, extend scope — and also include `csharp-comments`, which is the third and last comment-convention skill in the repo (no others exist).
- **Q:** Should the break rule be sentence-only, or also break at internal clause boundaries for long compound sentences? **A:** User asked for a judgment call; landed on sentence-per-line plus a mechanical clause-boundary trigger (comma+coordinating-conjunction or semicolon) rather than pure sentence-only or vague "break wherever feels right."
- **Q:** Should already-existing committed markdown/comments be reformatted under the new rule, or does it apply going forward only? **A:** Going forward only — reformatting existing content becomes a separate follow-up task, with the narrow exception of the two contradictory examples inside `golang-comments/SKILL.md` itself (fixed as a direct consequence of editing that file, not a retroactive sweep).
