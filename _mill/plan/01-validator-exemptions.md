# Batch: validator-exemptions

```yaml
task: '_plan_validate.py context-completeness check: false positives across gitignored/quoted/negated/citation/cross-reference prose'
batch: validator-exemptions
number: 1
cards: 8
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: []
```

## Batch Scope

This batch delivers every behavior change to the `context-completeness` check in `plugins/mill/scripts/_plan_validate.py`: four path-shape exemptions, three line-level exemptions, one escape marker, and the fence-aware extraction swap. It is one batch because all eight changes edit the same function's per-token loop and its module-level constants, and splitting them would force later cards to re-read edits they cannot see. The external interface the later batches consume is the changed behavior itself plus one new keyword-only parameter on the check function; batch 2 and batch 3 test that behavior, and batch 4 documents it.

Batch-local decision beyond the overview's Shared Decisions: no existing exemption is tightened and no existing helper is deleted. `_extract_requirements_text` and `_is_prohibition_exempt` keep their current bodies and their documented limitations; this batch only adds exemptions and re-points one call site.

## Cards

### Card 1: Directory-intent exemption

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_check_context_completeness`, inside the path branch (the `if is_path_shaped:` arm that begins by computing `stripped_token` via `_RE_LINE_RANGE.sub("", token)`), add a directory-intent exemption that runs before the `resolve_existing_paths` call: when `stripped_token` ends with the character `/`, `continue` without emitting a finding and without touching the filesystem. Add a short comment stating that a trailing slash is an unambiguous authorial statement of directory intent, that a directory can never be a `Context:` entry, and that the test is deliberately filesystem-independent because in a linked git worktree the repository's own `.git` is a regular file rather than a directory, so the existing `existing_files = [p for p in existing if p.is_file()]` filter does not suppress a `.git/` token there. Do not remove or weaken that existing `is_file()` filter — this exemption is additive.
- **Commit:** `fix(plan-validate): exempt trailing-slash directory references from context-completeness`

### Card 2: Out-of-repo literal exemption with wiki carve-out

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add an out-of-repo exemption to the path branch of `_check_context_completeness`, in two halves. First half, before `resolve_existing_paths` is called: when `stripped_token` does not start with the literal prefix `wiki/`, and it is absolute-looking, `continue`. Treat as absolute-looking a token that starts with `/`, starts with `~`, starts with a doubled backslash denoting a Windows UNC root, or matches a Windows drive-letter root — a single ASCII letter followed by `:` followed by `/` or backslash. Add a module-level compiled regex covering the drive-letter and UNC shapes next to the other module-level regexes rather than compiling it per token. Second half, immediately after `existing_files` is computed: when `existing_files` is non-empty and no entry in it is relative to any in-scope root, `continue`. The in-scope roots are `project_root`, `git_root`, and `wiki_root`, skipping any root that is `None`. Call `.resolve()` on the candidate and on each root before comparing them with `Path.is_relative_to`, and say so in a comment: `resolve_existing_paths` builds its candidates by joining the raw token onto a root and never calls `.resolve()` itself, while `is_relative_to` is a pure lexical prefix comparison that does not collapse parent-directory segments — so a token such as a doubled parent-traversal prefix followed by a path would still carry the root's parts as a literal prefix and would be wrongly judged in-repo. The sibling `_check_out_of_worktree_target` in this same module already establishes this idiom by resolving the worktree root before its own containment test; follow it. The `wiki/` prefix must be carved out of the first half only; the second half needs no carve-out because `wiki_root` is one of the roots it tests. Document in a comment that `resolve_existing_paths` routes a `wiki/`-prefixed raw token to `wiki_root`, a sibling clone that normally lies outside both other roots, so omitting either guard would exempt a legitimate wiki dependency and convert a fixed false positive into a silent false negative.
- **Commit:** `fix(plan-validate): exempt out-of-repo path literals, preserving wiki/ refs`

### Card 3: Gitignored-path exemption

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a module-level helper to `plugins/mill/scripts/_plan_validate.py` that answers whether a resolved candidate path is git-ignored, and call it from the path branch of `_check_context_completeness` immediately after `existing_files` is computed and after card 2's resolved-location guard: when every entry in `existing_files` is confirmed git-ignored, `continue`. The helper takes the resolved candidate plus the three roots plus a memo dict, and derives the candidate's own source root by testing it against `git_root`, then `project_root`, then `wiki_root` in that order, taking the first root the candidate `is_relative_to` and skipping any root that is `None`. Apply `.resolve()` to the candidate and to each root before that comparison, for the same reason card 2's second half does: the candidate arrives unresolved from `resolve_existing_paths` and `is_relative_to` is lexical, so an uncollapsed parent-directory segment would otherwise select the wrong source root and run `git check-ignore` against a repository the path does not belong to. When no root matches, return False without running any subprocess — such a candidate is out-of-repo and card 2's guard has already exempted it. Otherwise run `_subprocess_util.run(["git", "-C", str(source_root), "check-ignore", "-q", str(candidate)])` and treat a returncode of 0 as ignored. Wrap the call so that any exception whatsoever, including a non-git source root, is swallowed and reported as not-confirmed-ignored — never propagate. Memoize by the absolute candidate path in a dict created once per `_check_context_completeness` call and threaded into the helper, alongside the existing `search_cache` dict, so a path recurring across cards costs one subprocess rather than one per occurrence. This mirrors the `soft_fail_gitignored` branch of `resolve_ref_paths` in `plugins/mill/scripts/_review_common.py` in both mechanism and failure posture; the reason the pairing cannot simply be reused is that `resolve_existing_paths` returns a flat list of paths with no source-root attribution, unlike `resolve_ref_paths`, which carries candidate-and-root pairs.
- **Commit:** `fix(plan-validate): exempt git-ignored paths from context-completeness`

### Card 4: Forward cross-card Creates exemption

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a module-level helper to `plugins/mill/scripts/_plan_validate.py` that builds a plan-wide map from each `Creates:` token to the composite key of the card declaring it, and wire it through `run` into `_check_context_completeness`. The composite key is a two-tuple of the batch file's index in the sorted `batch_files` list and the declaring card's number, so keys compare lexicographically. The helper walks each batch file's cards with the existing `_parse_cards` and collects each card's own `Creates:` tokens using the same `_RE_REFS_HEADER` and `_RE_REFS_SUB` traversal that `_card_own_reference_set` already performs, restricted to the `Creates:` header. When one token is declared by more than one card, keep the lowest composite key. Compute the map once in `run`, beside the existing `creates_union` assignment, reusing the same sorted `batch_files` list already built there so the index agrees with what every other check sees, and pass it to `_check_context_completeness` as a new keyword-only parameter defaulting to an empty mapping. In the path branch, after the `resolvable` determination and before the `own_refs` lookup, exempt the token when all three hold: `existing_files` is empty, the token is present in the map, and the map's composite key for the token is strictly greater than the composite key of the card currently being checked. Document in a comment why the bare card number is not used: `_check_card_numbering` enforces only within-batch sequencing and cross-batch uniqueness, never cross-batch monotonicity, so a plan whose first batch holds cards 4 through 6 and whose second batch holds cards 1 through 3 validates today, and on such a plan a bare card-number test would misfire into a false negative. Document also why the `existing_files` emptiness clause is required: nothing prevents a `Creates:` target from already existing on disk, and an earlier card naming the path may genuinely be reading the file's current content before a later card replaces it. Do not add a cross-batch monotonicity check to `_check_card_numbering`.
- **Commit:** `fix(plan-validate): exempt forward cross-card Creates references`

### Card 5: Non-dependency negation phrase exemption

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a module-level non-dependency phrase matcher to `plugins/mill/scripts/_plan_validate.py`, defined next to `_is_prohibition_exempt`, and call it in `_check_context_completeness` immediately after the existing `_is_prohibition_exempt` check and before the `_CITATION_MARKERS` check, so it applies to both the path branch and the symbol branch. The matcher takes the lowercased line and the token's own occurrence position within that line, and returns True when the line positions that specific occurrence as explicitly not-involved. Support three phrase templates: the token preceded by the word "no" and followed by "is involved"; the token immediately preceded by the word "without"; and the token followed by "is not" plus one of "involved", "needed", "required", or "used". Allow intervening words between the token and the trailing phrase only within the same clause, treating comma, semicolon, colon, and period as clause boundaries. Because the matcher needs the occurrence position, change the token loop to iterate matches rather than plain strings, so each token's start and end offsets in the line are available — use `finditer` on the existing backtick regex instead of `findall`, and take the token text from group 1. Keep every downstream use of the token text identical, including the emitted `path` field, which must remain the original token. Add a docstring paragraph stating why the existing `_is_prohibition_exempt` word-set was not simply widened with "no" and the verbs "involve", "need", "require", and "exist": that function matches line-wide with no positional requirement, so a bare "no" paired with any of its roughly twenty existing verb forms anywhere on the line would exempt a large share of ordinary Requirements prose.
- **Commit:** `fix(plan-validate): exempt non-dependency negation phrasing`

### Card 6: Contrast-citation exemption with positional requirement

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a contrast-citation exemption to `_check_context_completeness`, evaluated alongside the existing `_CITATION_MARKERS` substring check and, like it, before the path/symbol branch split. Define a module-level tuple of contrast markers containing the two entries "rather than" and "instead of". A token is exempt when a contrast marker occurs on the same line and the token's own occurrence is adjacent to that marker — either the nearest token occurrence before the marker, or the nearest after it — with adjacency bounded by clause punctuation, meaning no comma, semicolon, colon, or period may lie between the token occurrence and the marker. Both sides must be covered, because in the phrasing that motivates this exemption both the chosen and the rejected alternative are citations. Do not add these two markers to `_CITATION_MARKERS`, and do not match them line-wide: unlike the narrow existing entries such as "e.g." and "signature inlined", "rather than" and "instead of" are ordinary connective English that appears in genuine dependency prose, so a line-wide substring match would exempt real dependencies. State that reason in a comment on the new tuple.
- **Commit:** `fix(plan-validate): exempt contrast-citation phrasing with clause-bounded adjacency`

### Card 7: Quoted-material exemption and fence-aware extraction

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Make two related changes to `_check_context_completeness`. First, change its step-one extraction call from `_extract_requirements_text(card_text)` to `_requirements_fence_aware_body(card_lines)`, using the `card_lines` value the enclosing `_parse_cards` loop already binds. Both return the same optional-string shape, so the existing `if requirements_text is None: continue` guard and the following `splitlines` call are unchanged. Leave both helper functions themselves unmodified — this card re-points one call site and deletes nothing. Second, add a quoted-material exemption: track a boolean fence state across the extracted Requirements lines, toggled by any line whose `startswith` test for three backticks is true, with the toggle applied after the line is processed, matching the convention `_parse_cards` already uses; exempt every token on a line while that state is true, and exempt every token on a line whose leading whitespace-stripped form starts with the character `>`. Place the exemption with the other line-level checks, before the path/symbol branch split. Document why the extraction swap is required rather than cosmetic: `_extract_requirements_text` stops at the first line matching a bold field-header shape unconditionally, with no fence awareness, so a fence quoting a field-header-shaped line would truncate the body before the new fence tracking ever saw the remainder — which is precisely the docs-quoting scenario this exemption exists to fix. Note also that `_requirements_fence_aware_body` is already what the sibling `requirements-quote-indent-drift` check uses, so after this change both checks agree about what a fence means.
- **Commit:** `fix(plan-validate): exempt quoted material and use fence-aware Requirements extraction`

### Card 8: Explicit escape marker

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Append the entry "mentioned, not read" to the module-level `_CITATION_MARKERS` tuple in `plugins/mill/scripts/_plan_validate.py`, and extend that tuple's existing explanatory comment to describe it as the planner's explicit escape hatch for a mention that no structural or phrasing rule reaches. Keep every existing entry unchanged and in place. A bare line-wide substring match is correct for this entry, matching how the sibling entries "signature inlined" and "no file read needed" already behave, because the phrase is unambiguous and would not appear by accident. Update the `_check_context_completeness` docstring's numbered exemption list so it enumerates all of this batch's exemptions rather than the three it currently names, and keep the docstring's existing warning that the emitted symbol-branch message wording must not drift, since a downstream fixer parses it.
- **Commit:** `fix(plan-validate): add mentioned-not-read escape marker`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-plan-validate.py` directly, which is the file that exercises `_plan_validate`. During this batch it acts as a regression gate only: no test for the new exemptions exists yet, so a pass here means the roughly fifty existing `test_check_context_completeness_*` tests plus every other check's tests still hold after the eight changes. The prohibition-marker, citation-marker, line-range-suffix, moves-source, directory-reference, and symbol-branch tests are the ones most likely to catch an over-broad new rule, and any failure among them is a signal to narrow the rule rather than to edit the test. New-behavior coverage arrives in batches 2 and 3, which is a deliberate consequence of the context-cap decision recorded in the overview's Shared Decisions, not an oversight.
