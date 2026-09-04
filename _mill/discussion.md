# Discussion: _plan_validate.py context-completeness check: false positives across gitignored/quoted/negated/citation/cross-reference prose

```yaml
task: '_plan_validate.py context-completeness check: false positives across gitignored/quoted/negated/citation/cross-reference prose'
slug: plan-validate-context-completeness-false-positive-exemptions
status: discussing
parent: main
```

## Problem

`_plan_validate.py`'s `context-completeness` check (`plugins/mill/scripts/_plan_validate.py:1965`, `_check_context_completeness`) flags every backtick-quoted, path-shaped token in a plan card's `Requirements:` prose that resolves to a real file but is absent from that card's own `Context:`/`Edits:`/`Creates:`/`Deletes:`/`Moves:`-source lists. The check's intent is sound: a file the implementer must *read* belongs in `Context:` so the bulk-mode plan reviewer actually sees it.

The check has no way to tell "the implementer reads this file" apart from "the prose merely *names* this path". Seven GitHub issues (#982, #976, #974, #972, #971, #926, #960) report the check firing on cards where the path is named as a gitignored machine-local runtime artefact, an out-of-repo string literal, a grep exclusion, a contrast citation ("named `a.md` rather than `README.md`"), a negation ("so no `.mcp.json` is involved"), a forward pointer to a file a *later* card creates, or quoted prose the card is rewriting. In every case the two available remedies are both wrong: add a non-dependency to `Context:` (which is documented as a read-allowlist, pollutes the reviewer's bulk, and can name a file that does not exist at card-execution time), or strip the backticks and degrade the plan's own precision. One reporter observed the check is avoidable by relocating the same text into `## Batch Scope`, which the check does not scan — evidence it is not measuring what it intends to.

The eighth issue (#979) is the mirror image on the reviewer side: `review-plan-holistic.md` and `review-plan-batch.md` instruct the LLM reviewer to BLOCK on any path in `Requirements:` absent from `Context:`/`Edits:`, with none of the validator's exemptions. On task `reed-collapsed-strip-readability` the validator returned zero findings while plan-review rounds 1 and 2 each burned a round on BLOCKING findings naming only prohibition-line paths the validator deliberately exempts. Two of six review rounds consumed on findings the validator was designed to suppress.

**Why now:** eight independent reports across three repos (quarry, loomyard, millhouse) converge on one fix locus — the check's exemption logic plus the reviewer prompt that must mirror it. Every report ends in a workaround that makes the plan worse, so the cost is paid on every plan-writing run, not once.

## Scope

**In:**

- `plugins/mill/scripts/_plan_validate.py` — `_check_context_completeness` and its module-level exemption constants/helpers (`_PROHIBITION_NEGATIONS` at line 1643, `_PROHIBITION_VERB_FORMS` at 1662, `_is_prohibition_exempt` at 1697, `_CITATION_MARKERS` at 1714, `_extract_requirements_text` at 1742, `_covered_by_own_refs` at 1949).
- Eight new exemptions in `_check_context_completeness`, in three groups:
  - **Four path-shape exemptions**, added to the path branch (step 5 of the per-token flow described under Technical context): directory-intent, out-of-repo/absolute, gitignored, forward cross-card `Creates:`.
  - **Three line-level exemptions**, added before the path/symbol branch split (step 4) and therefore applying to **both** branches: non-dependency negation phrasing, contrast-citation phrasing, quoted-material (fenced/blockquote).
  - **One explicit escape marker**, added to `_CITATION_MARKERS` and therefore also line-level and branch-agnostic.
- A new plan-wide creates-token → declaring-card-number map threaded from `run()` (`plugins/mill/scripts/_plan_validate.py:3339`, call site at 3441) into `_check_context_completeness`.
- `plugins/mill/templates/review-plan-holistic.md` and `plugins/mill/templates/review-plan-batch.md` — the `Context completeness` bullet in each, so the reviewer mirrors the validator's exemptions (#979).
- `plugins/mill/skills/mill-plan/SKILL.md` — the `context-completeness` fix-table row (line 385) and the Requirements-prohibition Principles bullet (line 667), documenting every new exemption and escape hatch.
- `plugins/mill/unit_tests/test-plan-validate.py` — clean-case and dirty-case regression tests per new exemption.

**Out:**

- `_check_non_existent_path` — its `soft_fail_gitignored` behaviour is already correct and is the model being copied, not changed.
- The **symbol branch** of `_check_context_completeness` (`_symbol_candidate_shape`, `_resolve_symbol_files`, `_SYMBOL_SEARCH_*`). No issue reports a symbol-branch false positive. The gitignored/out-of-repo/directory/forward-creates exemptions are path-shape-specific; the *line-level* exemptions (negation, citation, quoted-material, escape marker) already run before the branch split and therefore apply to both branches unchanged — that is existing behaviour being preserved, not new symbol-branch work.
- The `Requirements:` regex's non-handling of markdown's double-backtick escape convention (documented limitation in the existing docstring) — unchanged.
- The `_is_prohibition_exempt` double-negative misdetection and nested-bullet limitation — both documented existing limitations, out of scope. This task adds exemptions; it does not tighten existing ones.
- `## Batch Scope` remains unscanned by the check. Widening the check's scan surface is a separate design question and would work against this task's goal.
- Any change to `resolve_existing_paths` / `resolve_ref_paths` in `_review_common.py`. The gitignored exemption is implemented inside `_plan_validate.py` against already-resolved candidates.

## Decisions

### exemption-architecture

- Decision: structural-first, with narrow lexical additions and exactly one new explicit escape marker. Structural signals (git-ignored status, path outside the repo, trailing-slash directory intent, forward `Creates:` ownership, fenced/blockquote containment) are preferred wherever the false positive has a machine-checkable shape. Lexical phrase matching is used only where the distinction is genuinely in the English (negation, contrast citation). One escape marker covers the residue.
- Rationale: the seven false-positive reports split cleanly into two populations. Four have crisp structural signatures that no amount of marker-list growth would ever catch reliably; three are phrasing. Growing only the marker list would leave the structural cases unfixed and would keep loosening a line-wide substring match until the check exempts most prose. Offering only an escape marker would push the burden onto every planner on every card, which is the workaround-tax this task exists to remove.
- Rejected: (a) lexical marker-list extension only — cannot express "this file is git-ignored" or "a later card creates this"; (b) explicit escape marker only — makes the planner responsible for annotating every mention, and an un-annotated legitimate mention still fails the plan.

### gitignored-exemption

- Decision: a path-branch token whose resolved candidate is confirmed git-ignored under its own source root is exempt. Implemented by running `git -C <source_root> check-ignore -q <candidate>` (return code 0 means ignored) via `_subprocess_util.run`, memoized per `run()` invocation in a dict keyed by the absolute candidate path, with every exception swallowed as "not confirmed ignored". This mirrors `resolve_ref_paths`'s `soft_fail_gitignored` branch (`plugins/mill/scripts/_review_common.py:1000`-ish, inside the non-wiki resolution loop) in both mechanism and failure posture.
- Rationale: fixes #982 directly and removes the check's dependence on local machine state — today the verdict flips depending on whether `.scratch/ladder.env` happens to exist on the running machine (verified empirically: the token fires when the file exists, is silently unresolvable when it does not). `Context:` is a read-allowlist of *repo* files; a machine-local gitignored runtime artefact can never legitimately be listed there. `_check_non_existent_path` already tolerates exactly this class via `soft_fail_gitignored=True`, so the two checks currently disagree about the same path — this closes that disagreement.
- Rejected: (a) parsing `.gitignore` in-process — reimplements git's pattern semantics (negations, nested `.gitignore` files, `core.excludesFile`) and will drift; (b) hardcoding `.scratch/` — fixes one reporter's path and none of the class.

### out-of-repo-literal-exemption

- Decision: a path-branch token is exempt when it is rooted outside the project: either the raw token is absolute-looking (POSIX-absolute `/…`, home-relative `~…`, or Windows drive-letter `X:\…` / `X:/…`), or its resolved file lies outside both `project_root` and `git_root` (tested via `Path.is_relative_to` against each root, with `git_root` skipped when `None`).
- Rationale: fixes #976. `/tmp/quarry-bench` is a hardcoded string inside code being ported — not a file the implementer opens, and unlistable in any of the five fields. Note that today's behaviour is machine-dependent in the same way as the gitignored case: `resolve_existing_paths` builds `project_root / raw`, and pathlib's `/` operator lets an absolute right-hand operand win outright, so the token resolves to the real `/tmp/quarry-bench` and fires only on a machine where that file exists. Both the raw-token test and the resolved-location test are needed: the raw test catches absolute literals that happen not to exist, and the resolved test catches a relative token that escapes the worktree via `../`.
- Rejected: (a) absolute-prefix check only — misses `../`-escaping relative tokens; (b) escape marker only — pushes annotation onto the planner for a case with a perfect structural signal.

### directory-intent-exemption

- Decision: a path-branch token whose raw form (after `_RE_LINE_RANGE` stripping) ends with `/` is exempt unconditionally, without consulting the filesystem.
- Rationale: fixes #974. The existing `existing_files = [p for p in existing if p.is_file()]` filter already exempts a trailing-slash token that resolves to a real directory (verified empirically: `` `plugins/mill/templates/` `` produces zero findings today). It does *not* cover the reported case, because in a linked git worktree `.git` is a regular **file**, not a directory — verified in this worktree: `ls -la .git` shows a 126-byte regular file. So `` `.git/` `` passes the `is_file()` gate and fires (verified empirically: one finding). A trailing slash is an unambiguous authorial statement of directory intent; a directory can never be a `Context:` entry, so honouring the slash without a filesystem probe is both correct and machine-state-independent.
- Rationale (secondary): this also makes the check's behaviour identical inside and outside a linked worktree, which the current on-disk-type test does not guarantee.
- Rejected: (a) keeping the `is_file()` test alone — leaves the reported `.git/` case firing in exactly the environment mill runs in; (b) denylisting `.git` by name — fixes one token, not the class of grep-exclusion prose.

### forward-cross-card-creates-exemption

- Decision: build a plan-wide map from each `Creates:` token to the **global card number** of the card that declares it, and exempt a path-branch token when the declaring card's number is strictly greater than the referencing card's number. A backward reference (an earlier card creates it, a later card names it) keeps firing. A token resolvable on disk *and* declared as a later card's `Creates:` target is still exempt — the forward declaration wins, since the card cannot list a file whose post-card content is what the prose refers to.
- Rationale: fixes #960 and the second half of #971. Today `stripped_token in creates_union` makes a cross-card `Creates:` target *resolvable*, and `_covered_by_own_refs` only consults the referencing card's own refs — so every cross-card mention fires. `Context:` means "files the implementer reads", and a forward-created file does not exist at the referencing card's execution time; the fix-table's "add to `Context:`" remedy would make the plan assert something untrue, and `non-existent-path` would then let it pass. The direction test preserves the genuinely-correct case: if card 3 creates a file and card 9 reads it, card 9 must still declare it. Global card numbering is unique and sequential across batches (enforced by `_check_card_numbering` and the reviewer's "Global step numbering" criterion), so the number ordering is a sound proxy for execution ordering.
- Implementation note: `compute_creates_union` (`plugins/mill/scripts/_review_common.py:783`) returns a flat set with no card attribution, so it cannot be reused as-is. A new `_plan_validate.py`-local helper builds the map by walking each batch file's cards via the existing `_parse_cards` (line 136) and collecting each card's own `Creates:` tokens via the same `_RE_REFS_HEADER`/`_RE_REFS_SUB` traversal `_card_own_reference_set` (line 1766) already uses. Computed once in `run()` alongside `creates_union` (line 3402) and threaded into `_check_context_completeness` as a new keyword argument. When one token is declared by more than one card the map records the **lowest** declaring card number, so a duplicate declaration can never manufacture a forward exemption for a file an earlier card already produced.
- Rejected: (a) exempting every cross-card `Creates:` reference regardless of direction — silently drops the legitimate "later card reads an earlier card's output" dependency, which is the check's whole reason for existing; (b) exempting only same-batch forward references — #971's case crosses cards within one batch but nothing about the problem is batch-scoped, and a cross-batch forward pointer is equally undeclarable.

### negation-phrase-exemption

- Decision: add a dedicated non-dependency **phrase** matcher, separate from `_is_prohibition_exempt`, that exempts a token when the line matches a phrase template positioning the token as explicitly not-involved. Templates: `no <token> is involved`, `without <token>`, and `<token> is not involved|needed|required|used`. Matched against the line with the token's own position taken into account (the phrase must bracket the token occurrence), not as a line-wide substring search.
- Rationale: fixes the first half of #971. `_is_prohibition_exempt` requires a negation from `_PROHIBITION_NEGATIONS` **and** a verb form from `_PROHIBITION_VERB_FORMS`; "so no `.mcp.json` is involved" supplies neither ("no" is not in the negation tuple, "involved" is not in the verb map), so it fires. The narrow phrase form expresses exactly the reported shape without touching the existing prohibition machinery, which other tests and documented behaviour depend on.
- Rejected: adding bare `"no"`/`"none"` to `_PROHIBITION_NEGATIONS` and `involve`/`need`/`require`/`exist` to `_PROHIBITION_VERB_FORMS`. `_is_prohibition_exempt` matches line-wide with no positional requirement, so a bare `"no"` plus any of ~20 existing verb forms anywhere on the line would exempt an enormous amount of ordinary Requirements prose ("Read `foo.py`; there is no cache to update") — a false-exemption rate far worse than the false-positive rate being fixed.

### contrast-citation-exemption

- Decision: add contrast-citation markers `"rather than"` and `"instead of"`, matched with a positional requirement — the marker must occur on the same line **and** the token occurrence must be adjacent to it (immediately before the marker as the chosen alternative, or after it as the rejected one, allowing intervening words within the same clause, bounded by clause punctuation `,` `;` `.` `:`).
- Rationale: fixes #972. The reported sentence — "named `a.md` rather than the more obvious `README.md` so that …" — is a citation in exactly the sense the existing exemption 2 intends, but no marker in `_CITATION_MARKERS` covers it. Both tokens in that sentence are being *cited*, which is why the exemption must reach the token on either side of the marker.
- Rationale (positional requirement): every existing entry in `_CITATION_MARKERS` is matched line-wide as a bare substring, and that is tolerable for narrow phrases like `"e.g."` or `"signature inlined"`. `"rather than"` and `"instead of"` are ordinary connective English that appears in legitimate dependency prose ("Read `foo.py` rather than guessing at the signature"), so matching them line-wide would exempt genuine dependencies. The positional/clause requirement is what makes them safe to add.
- Rejected: adding both markers bare to `_CITATION_MARKERS` — simplest to implement, but the false-exemption risk above is a direct regression of the check's purpose.

### quoted-material-exemption

- Decision: a token is exempt when it occurs inside quoted material within `Requirements:` — either inside a fenced code block (```` ``` ````-delimited, toggled per the same convention `_parse_cards` at line 148 and `_requirements_fence_aware_body` already use) or on a blockquote line (first non-whitespace character is `>`). Requires `_check_context_completeness`'s per-line loop to track fence state across the `Requirements:` body rather than treating each line independently.
- Rationale: fixes #926. A docs card whose job is to reword an existing sentence must quote that sentence to state its requirement precisely; the paths inside the quotation are string content in a document, not inputs. The reported case produced 7 findings across two cards for four files the implementer has no reason to open, and the prescribed remedy inflates `Context:` with pure noise on exactly the docs/manifest tasks that quote filenames most. Fence and blockquote containment are unambiguous, author-controlled, already-idiomatic markdown signals — no new syntax to learn and no phrasing heuristic to misfire.
- Rationale (fence interaction): the sibling `requirements-quote-indent-drift` check already treats fenced blocks inside `Requirements:` as verbatim quoted source, so exempting fenced content here makes the two checks agree about what a fence means.
- Rejected: fenced blocks only — blockquote (`>`) is the more natural markdown form for quoting a sentence inline in prose, and #926's own reproduction uses blockquote-style quotation; covering only fences would leave the reported shape firing.

### explicit-escape-marker

- Decision: add `"mentioned, not read"` to `_CITATION_MARKERS`, matched line-wide as a bare substring exactly like the existing `"signature inlined"` and `"no file read needed"` entries.
- Rationale: covers the residue no structural or phrasing rule reaches, and follows an established precedent — `"signature inlined"` / `"no file read needed"` are already documented escape hatches in the mill-plan fix-table row (SKILL.md line 385) and referenced by the `batch-oversized` row (line 395). Reusing the existing marker mechanism means no new field, no new parser, and no new failure mode. A line-wide bare match is safe here because the phrase is unambiguous and would never appear by accident.
- Rejected: (a) a per-card `skip_checks` field — new plan-file syntax, new parsing, new validation surface, and it disables the whole check for the card rather than exempting one token; (b) no escape marker at all — leaves planners with no recourse for a case none of the seven rules anticipated, which is the exact dead end every reported issue hit.

### documented-in-keeps-firing

- Decision: `"documented in `X`"` phrasing gets **no** exemption of its own. When the named file exists on disk and is not a later card's `Creates:` target, the check keeps firing.
- Rationale: the second case in #971 ("the warm-start alternative documented in `docs/mcp-setup.md`") is already fully handled by the forward-cross-card-creates exemption, since that file was a later card's `Creates:` target. When the pointed-at file *does* already exist, "documented in X" is genuinely ambiguous — it frequently marks a real read dependency, which is precisely what the check exists to catch. Exempting the phrase would trade a fixed false positive for an unbounded false negative.
- Rejected: adding `"documented in"` to `_CITATION_MARKERS`.

### reviewer-prompt-mirror

- Decision: rewrite the `Context completeness` bullet in **both** `plugins/mill/templates/review-plan-holistic.md` (line 66) and `plugins/mill/templates/review-plan-batch.md` (line 65) to enumerate the validator's exemptions, so the LLM reviewer does not BLOCK on what the validator deliberately suppresses. The enumeration covers: same-line prohibitions, citation/contrast/escape-marker lines, quoted material (fenced or blockquote), git-ignored and out-of-repo paths, trailing-slash directory references, and forward references to a later card's `Creates:` target.
- Rationale: fixes #979 and is the whole reason the eighth issue belongs in this task. The validator returning zero findings while the reviewer BLOCKs twice on the same suppressed class is a pure round-burn: two of six review rounds consumed on `reed-collapsed-strip-readability`. Updating both templates keeps batch-scope and holistic-scope reviewers consistent — the two bullets are near-identical today and diverging them would produce scope-dependent verdicts on the same plan.
- Rejected: (a) holistic only — #979 was observed on the holistic reviewer, but the batch template carries the same unqualified bullet and would produce the same finding at batch scope; (b) dropping the exemptions from `_plan_validate` so the two agree — inverts the task: the exemptions are the fix, not the bug.

### docs-sync

- Decision: update `plugins/mill/skills/mill-plan/SKILL.md`'s `context-completeness` fix-table row (line 385) to state that the "add to `Context:`" remedy applies only when no exemption covers the token, and to list every available escape hatch; and extend the Requirements-prohibition Principles bullet (line 667) into a short set of phrasing guidelines covering the new exemptions.
- Rationale: the fix-table row is what a mill-plan fixer reads when acting on a finding. If it still says "add the referenced file to the card's `Context:`" unconditionally, the fixer will keep applying the wrong remedy in the residual cases and will not know the escape hatches exist. The Principles bullet is what the planner reads while *writing*, and it already documents the prohibition exemption's one-line requirement — the new exemptions belong beside it.
- Rejected: fix-table row only — leaves the planner unaware of the exemptions at authoring time, when avoiding the finding is cheapest.

### scope-boundary

- Decision: leave `_check_non_existent_path` and the symbol branch of `_check_context_completeness` untouched.
- Rationale: no reported issue implicates either. `_check_non_existent_path`'s gitignored handling is the reference implementation this task copies. The symbol branch resolves by filesystem walk, never by path shape, so the path-shape-specific exemptions do not apply to it; the line-level exemptions (negation, citation, quoted material, escape marker) already run before the branch split and will cover symbol tokens automatically, which is correct and requires no symbol-branch change.
- Rejected: revisiting the symbol branch opportunistically — YAGNI, and it would widen a task that already touches four files across two subsystems.

## Technical context

**Check location and control flow.** `_check_context_completeness` lives at `plugins/mill/scripts/_plan_validate.py:1965`. Its per-token loop is roughly lines 2085–2155. Order of operations today, per card:

1. `_extract_requirements_text(card_text)` (line 1742) returns the `Requirements:` body — the header line's trailing text plus every following line up to the next `- **<Field>:**` header. Returns `None` when there is no `Requirements:` header.
2. For each line, `` re.compile(r"`([^`]+)`") `` yields backtick tokens.
3. **Shape gate:** `is_path_shaped = "/" in token or token.endswith(_PATH_CANDIDATE_EXTENSIONS)`. Non-path tokens go through `_symbol_candidate_shape`; a `None` result skips the token.
4. **Line-level exemptions** (apply to both branches, computed on `lowered_line = line.lower()`): `_is_prohibition_exempt(lowered_line)`, then `any(marker in lowered_line for marker in _CITATION_MARKERS)`.
5. **Path branch:** strip `_RE_LINE_RANGE` (line 112, `` re.compile(r":\d+-\d+$") ``) to get `stripped_token`; call `resolve_existing_paths`; filter to `existing_files = [p for p in existing if p.is_file()]`; `resolvable` is true when `existing_files` is non-empty **or** the token is in `creates_union` / `deletes_union` / `moves_targets`. Not resolvable → skip. Then lazily compute `own_refs = _card_own_reference_set(card_text)` and skip when `_covered_by_own_refs(stripped_token, own_refs, moves_sources)`. Otherwise emit the error dict.
6. **Symbol branch:** resolve via the memoized `_resolve_symbol_files`; exactly one match is canonicalized to a root-relative path and run through the same `_covered_by_own_refs` test.

New exemptions slot in as follows. The three line-level ones (negation phrase, contrast citation, quoted material) join step 4, before the branch split, so they cover both branches. The four path-shape ones (directory intent, out-of-repo, gitignored, forward-creates) belong in step 5: directory-intent and out-of-repo raw-token tests go *before* `resolve_existing_paths` (they need no filesystem access); the resolved-location half of out-of-repo and the gitignored test go immediately after `existing_files` is computed, since both operate on resolved candidates; forward-creates goes after the `resolvable` determination, since it must override resolution rather than precede it.

**Fence tracking.** Quoted-material exemption requires the per-line loop to carry fence state across the `Requirements:` body. The convention to copy is `_parse_cards` (line 136): a boolean toggled by any line whose `.startswith("```")`, with the toggle applied *after* the line is processed. Blockquote detection is `line.lstrip().startswith(">")` and is stateless.

**Error dict shape** — unchanged: `{check, batch, card, path, message, line}`. The `path` field carries the **original** token (not the line-range-stripped form), and `line` carries the stripped offending line. The mill-plan fix-table row (SKILL.md line 385) parses `message` for the substring `"which resolves to '"` to distinguish the symbol case from the path case, so **neither message format may drift**.

**`run()` wiring.** `run()` is at line 3339. `creates_union` / `deletes_union` are computed at lines 3402–3403, `moves_sources` / `moves_targets` at 3406, and `_check_context_completeness` is called at 3441 with positional `(batch_files, project_root, effective_root, creates_union, deletes_union, moves_sources, moves_targets)` plus keyword `wiki_root` / `git_root`. The new creates→card-number map is computed beside `creates_union` and passed as a new keyword argument, so no existing positional call shape changes. `_check_context_completeness` has exactly **one** call site in the whole codebase — `run()` at line 3441. Every existing `test_check_context_completeness_*` test in `plugins/mill/unit_tests/test-plan-validate.py` goes through `_plan_validate.run(...)`, not through the check function directly (verified: zero occurrences of `_check_context_completeness(` in that test file). There is therefore no existing direct-call contract to preserve; the new argument is nonetheless made keyword-only with a safe default (an empty mapping, which yields no forward exemptions) so the function stays callable in isolation and the default is unambiguously the no-exemption behaviour.

**Gitignore reference implementation.** `resolve_ref_paths` in `plugins/mill/scripts/_review_common.py:888`, in its `soft_fail_gitignored` branch: it builds `(candidate, source_root)` pairs and runs `_subprocess_util.run(["git", "-C", str(source_root), "check-ignore", "-q", str(cand)])`, treating returncode 0 as ignored and swallowing every exception as "not confirmed ignored" (a non-git `source_root` must never propagate). Copy that posture exactly. Memoize by absolute candidate path within one `run()` call — a plan can name the same gitignored path across many cards, and each `check-ignore` is a subprocess spawn.

**Verified current behaviour** (probes run in this worktree against `_check_context_completeness` directly):

- `` `.scratch/ladder.env` `` with the file present → 1 finding; with the file absent → 0. Machine-state-dependent, exactly as #982 reports.
- `` `/tmp/quarry-bench` `` absent locally → 0. Fires only where the file exists, because `project_root / "/tmp/quarry-bench"` collapses to the absolute path under pathlib.
- `` `plugins/mill/templates/` `` (real directory) → 0. Already exempt via `is_file()`.
- `` `.git/` `` in this linked worktree → 1. `.git` is a 126-byte regular file here, so it passes `is_file()`.
- `` named `README.md` rather than … `` → 1 (#972 confirmed).
- `` so no `<path>` is involved `` → 1 (#971 confirmed).
- Quoted-prose sentence naming an existing path → 1 (#926 confirmed).
- Path inside a fenced block within `Requirements:` → 1 (#926 fence half confirmed).

**Reviewer templates.** The two `Context completeness` bullets are near-identical:

- `plugins/mill/templates/review-plan-holistic.md:66` and `plugins/mill/templates/review-plan-batch.md:65` — "BLOCKING if `Requirements:` mentions a function, class, or constant from a file not listed in `Context:` or `Edits:`. The implementer may only read files in `Context:`; a missing entry means cold-start exploration."

Both need the same exemption enumeration appended. Note the batch template already carries a "Reviewer note" (line 75) telling the reviewer that `Creates:` targets are absent from its bulk and must not be flagged as `NEED_CONTEXT` — the forward-creates exemption is the same idea extended to `Requirements:` prose, and the new wording should read consistently with it.

**Conventions that apply.** ASCII-only in any `print()`/`_log()` output (`—` → ` -- `, `→` → ` -> `). Generated markdown uses fenced ` ```yaml ` metadata blocks, not `---` frontmatter. The unit-test suite is `plugins/mill/unit_tests/test-plan-validate.py` (8920 lines), run via `run-all.py`; existing context-completeness tests start at line 1814 and follow a uniform shape — build a fixture batch file in a temp dir, call `_plan_validate.run(...)` or `_check_context_completeness(...)` directly, filter `result` by `e["check"] == "context-completeness"`, assert the expected count. `verify:` commands in plan files must start with a literal `PYTHONPATH=` prefix (this is a Python project — `pyproject.toml` is present).

## Testing

**Framework and placement.** All tests go in `plugins/mill/unit_tests/test-plan-validate.py`, following the existing `test_check_context_completeness_*` naming and structure (first example at line 1814). Fixtures are tempfile/in-memory; no real git clone and no LLM. Run via `plugins/mill/unit_tests/run-all.py`.

**TDD candidates.** The four structural exemptions are the strongest TDD candidates — each has an exact, already-verified current behaviour to invert:

- `gitignored-exemption` — requires a fixture with a real `.git` and a `.gitignore`, since `git check-ignore` is a genuine subprocess. This is the one test that needs `git init` in a temp dir; it is worth the cost because a mocked `check-ignore` would test nothing.
- `directory-intent-exemption` — trivially TDD-able and the regression is exactly reproducible (`` `.git/` `` where `.git` is a regular file).
- `out-of-repo-literal-exemption` — TDD-able with a token pointing at a path outside the fixture root.
- `forward-cross-card-creates-exemption` — TDD-able against a two-card fixture; the *direction* test is the point, so it needs both orderings.

**Scenarios that must be covered.** Each exemption gets a clean case (exemption fires, zero findings) and a dirty case (the exemption must *not* fire, one finding), because an over-broad exemption is the primary risk this task introduces:

- Gitignored: ignored file present on disk → 0. Non-ignored file present on disk, same card shape → 1. Ignored file absent → 0 (already true; lock it in so the machine-state dependence cannot return).
- Out-of-repo: absolute token → 0; home-relative token → 0; `../`-escaping relative token that resolves outside the roots → 0; in-repo relative token → 1.
- Directory intent: trailing-slash token whose target is a real directory → 0; trailing-slash token whose target is a regular file (the `.git` case) → 0; same path without the trailing slash → 1.
- Forward creates: later card's `Creates:` target referenced by an earlier card → 0; **earlier** card's `Creates:` target referenced by a later card → 1; token declared by two cards, referenced by a card between them → 1 (lowest declaring number wins).
- Negation phrase: each of the three templates (`no X is involved`, `without X`, `X is not needed`) → 0; a line containing "no" and a path but not matching a template → 1.
- Contrast citation: `named A rather than B` exempts **both** tokens → 0; a line where the token is in a different clause from the marker ("Read `foo.py` rather than guessing.") → 1. This second case is the whole justification for the positional requirement and must be asserted.
- Quoted material: token inside a fenced block within `Requirements:` → 0; token on a blockquote line → 0; the same token on an ordinary prose line in the same card → 1; fence state correctly closed so a token *after* the fence still fires → 1.
- Escape marker: line carrying `mentioned, not read` → 0; same line without the phrase → 1.

**Regression coverage.** Every existing `test_check_context_completeness_*` test (lines 1814 onward) must still pass unchanged — in particular the prohibition-marker, citation-marker, line-range-suffix, moves-source, and symbol-branch tests. The existing dirty-case tests are the guard against over-exemption; if a new rule breaks one, the rule is too broad.

**Signature compatibility.** Add a **new** test that calls `_check_context_completeness` directly with its current positional argument list and no creates→card-number keyword, asserting the default yields no forward exemptions. No such direct-call test exists today — every current `test_check_context_completeness_*` test goes through `_plan_validate.run(...)` — so this is new coverage pinning the new keyword's default, not preservation of an existing contract.

**Template and docs changes** are prose; they carry no unit tests. Their correctness is verified by reading them against the final validator behaviour at plan-review time.

## Q&A log

- **Q:** Overall exemption architecture — structural-first with narrow lexical additions and one escape marker, lexical marker-list extension only, or escape marker only? **A:** [auto-pick] Structural-first + narrow lexical additions + one explicit escape marker. **Why:** the seven false-positive reports split into four with crisp machine-checkable signatures and three that are genuinely phrasing; a marker-list-only fix cannot express the former, and an escape-marker-only fix taxes every planner on every card.
- **Q:** How should the gitignored exemption (#982) be implemented? **A:** [auto-pick] `git check-ignore` on resolved candidates, memoized, mirroring `resolve_ref_paths(soft_fail_gitignored=True)`. **Why:** reuses git's own pattern semantics instead of reimplementing them, and closes the existing disagreement with `_check_non_existent_path`, which already tolerates this class.
- **Q:** How should out-of-repo string literals (#976) be exempted? **A:** [auto-pick] Exempt absolute/home/drive-letter-rooted raw tokens, and tokens whose resolved file lies outside both `project_root` and `git_root`. **Why:** the raw test catches absolute literals that do not exist locally; the resolved test catches `../`-escaping relative tokens. Either alone leaves a hole.
- **Q:** How should directory references (#974) be exempted? **A:** [auto-pick] Exempt any token ending in `/`, regardless of on-disk type. **Why:** the existing `is_file()` filter already handles real directories, but `.git` is a regular file in a linked worktree — verified here — so the reported case still fires; a trailing slash is unambiguous authorial intent and needs no filesystem probe.
- **Q:** How should forward cross-card `Creates:` references (#960, #971b) be exempted? **A:** [auto-pick] Build a creates-token → declaring-card-number map and exempt only when the declaring card number is strictly greater than the referencing card's. **Why:** direction is what separates the false positive from the genuine dependency; exempting all cross-card references would silently drop the "later card reads an earlier card's output" case the check exists to catch.
- **Q:** How should "no X is involved" negation phrasing (#971) be handled? **A:** [auto-pick] A dedicated non-dependency phrase matcher with positional bracketing, separate from `_is_prohibition_exempt`. **Why:** `_is_prohibition_exempt` matches line-wide with no positional requirement, so adding bare "no" plus common verbs would exempt a large share of ordinary Requirements prose.
- **Q:** How should "named X rather than Y" citation phrasing (#972) be handled? **A:** [auto-pick] Add `"rather than"` / `"instead of"` with a positional adjacency requirement bounded by clause punctuation. **Why:** these are ordinary connective English; matched line-wide like the existing markers they would exempt genuine dependencies such as "Read `foo.py` rather than guessing".
- **Q:** How should quoted prose (#926) be exempted? **A:** [auto-pick] Exempt tokens inside a fenced block or on a blockquote line within `Requirements:`. **Why:** both are unambiguous author-controlled markdown signals; #926's own reproduction uses blockquote quotation, so a fence-only rule would leave the reported shape firing.
- **Q:** What explicit escape marker should exist for the residue? **A:** [auto-pick] Add `"mentioned, not read"` to `_CITATION_MARKERS`. **Why:** follows the established `"signature inlined"` / `"no file read needed"` precedent — no new field, no new parser, no new failure mode.
- **Q:** Should "documented in `X`" get its own exemption? **A:** [auto-pick] No — keep flagging when the file exists and is not a forward `Creates:` target. **Why:** #971's instance is already covered by the forward-creates rule; where the file already exists the phrase frequently marks a real read dependency, so exempting it trades a fixed false positive for an unbounded false negative.
- **Q:** Which reviewer templates get the exemption mirror (#979)? **A:** [auto-pick] Both `review-plan-holistic.md` and `review-plan-batch.md`. **Why:** the two bullets are near-identical today; updating only one would produce scope-dependent verdicts on the same plan.
- **Q:** How far does the mill-plan documentation sync go? **A:** [auto-pick] Both the `context-completeness` fix-table row and the Requirements-prohibition Principles bullet. **Why:** the fix-table row drives the fixer's remedy at fix time; the Principles bullet reaches the planner at authoring time, when avoiding the finding is cheapest.
- **Q:** What test depth is required? **A:** [auto-pick] One clean case and one dirty case per exemption. **Why:** an over-broad exemption is this task's primary risk, and only the dirty cases detect it.
- **Q:** Does the task touch `_check_non_existent_path` or the symbol branch? **A:** [auto-pick] No — leave both untouched. **Why:** no issue implicates either; `_check_non_existent_path` is the reference implementation being copied, and the line-level exemptions already reach symbol tokens without any symbol-branch change.
