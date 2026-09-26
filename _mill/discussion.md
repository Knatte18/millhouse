# Discussion: plan validator and wiki-guard hook false positives

```yaml
task: plan validator and wiki-guard hook false positives
slug: tooling-false-positives
status: discussing
parent_branch: main
```

## Problem

Two independent tooling false positives, filed as GitHub issues #1158 and #1161 (both closed, consumed into this task).

**#1158 -- `_plan_validate` context-completeness resolves symbols to the wrong repo file.**
In a downstream plan, a backticked `InvalidOperationException` in a card's Requirements: was flagged as resolving to a repo file (`StaticPreset.cs`) that merely contains that identifier in a member-shaped line, and a qualified `HydraulicsParticipant.Replace` (a method the card itself adds to its own `Edits:` file `HydraulicsParticipant.cs`) resolved to `CoreConduit.cs`, because the qualifier was applied only as a namespace/directory filter and never as a type.
Expected: framework (BCL) types never resolve to repo files; `Type.Member` resolves via `Type`; a member the card's own `Edits:` file declares (or will declare) counts as covered.

**#1161 -- wiki-guard PreToolUse Bash hook false positive.**
The hook denies any Bash command whose text matches `\.wiki\b` anywhere, including quoted `--body "..."` text, heredoc bodies, and `hub.wiki`-style path suffixes (`echo "path/hub.wiki"` is denied).
Expected: block only commands that actually read or write the wiki clone through the `.wiki` junction.
The hook itself blocked exploration during this very task's discussion phase (a `grep` whose pattern contained `.wiki`).

## Scope

**In:**
- `plugins/mill/scripts/_plan_validate.py`: framework-type exclusion and type-qualified member resolution in the symbol branch of `_check_context_completeness`.
- New testable wiki-guard module plus hook CLI shipped in the plugin, replacing the inline `grep` one-liner.
- `_claude_settings.py` helper that installs/reconciles that hook in `~/.claude/settings.json`, wired into mill-setup Phase 4.8.
- Unit tests for all of the above.

**Out:**
- The path branch of context-completeness (unchanged).
- The Read/Edit/Write/Grep/Glob wiki hook matcher (it matches on a structured `file_path`, has no false-positive report, and stays as is).
- Changing the deny message semantics or protecting the real `wiki/` clone path (only the `.wiki` junction is guarded, as today).
- Any other validator exemption.

## Decisions

### framework-types-never-resolve

- Decision: add a curated frozenset `_FRAMEWORK_TYPE_NAMES` in `_plan_validate.py` (C#/.NET BCL: `InvalidOperationException`, `ArgumentException`, `ArgumentNullException`, `ArgumentOutOfRangeException`, `NotSupportedException`, `NotImplementedException`, `KeyNotFoundException`, `FormatException`, `Exception`, `Math`, `Path`, `File`, `Directory`, `String`, `Convert`, `Enumerable`, `List`, `Dictionary`, `HashSet`, `Task`, `Span`, `Guid`, `DateTime`, `TimeSpan`, `Console`, `Environment`, `Debug`, `Array`, `Object`, `Nullable`, plus TS/JS globals `Promise`, `Map`, `Set`, `Error`, `JSON`, `Object`, `Array`, `Math`, and Python builtin exception names `ValueError`, `TypeError`, `KeyError`, `RuntimeError`, `OSError`).
  The set is deduplicated (the prose list above repeats `Object`, `Array`, `Math` across languages; the frozenset literal lists each name once) and is deliberately cross-language: it is applied regardless of the resolving file's extension, and that over-reach is accepted (a Go or Python plan citing a repo symbol named `Map`, `Set`, `Error`, `List`, `Task`, `File` or `Path` is skipped unless a cited file type-declares it).
  A symbol-shaped token is treated as a framework reference, and skipped, when its search key (bare token) or its qualifier (dotted token, e.g. `Path.Combine`, `Math.Max`) is in that set, UNLESS a cited candidate file type-declares that exact name (`class|struct|interface|enum|record <Name>` for `.cs`, `class`/`interface`/`enum`/`type` for `.ts`, `class` for `.py`, `type <Name>` for `.go`) -- a repo that genuinely defines its own `Path` type keeps the current resolution.
- Rationale: the issue's expectation is categorical ("framework types are never resolved to repo files"); a name-set is the only language-agnostic signal available without a compiler.
  The repo-type-declaration override keeps the exemption from creating false negatives for repo-owned types that shadow a common name.
  Exact list contents are a judgment call; exhaustive coverage is not attempted (mill-plan should keep the set as a single module-level constant so it is easy to extend).
- Rejected: (a) restricting `.cs` member matching to require a preceding type or excluding `Exception`-suffixed names by regex -- too broad, and would also hide repo-defined `FooException` classes; (b) reading `using System` directives -- fragile, and a card's Requirements: prose rarely has that context.

### type-qualified-member-resolution

- Decision: in the symbol branch, for a dotted token `Qualifier.Member` whose Qualifier starts with an uppercase letter, first try to resolve `Qualifier` as a TYPE: search the cited candidate files (`candidate_files`) for a type-level declaration of `Qualifier` (reuse `_resolve_symbol_files` with a type-only mode, or a new helper `_resolve_type_files(qualifier, candidate_files, cache)` with its own memo; must not pollute the qualifier-independent `search_cache`).
  - Exactly one declaring file `F`: the token resolves to `F` and only `F`.
    If `F`'s canonical token is covered by the card's own refs (`_covered_by_own_refs`), no error -- this satisfies "a member the card's own Edits: file declares or will declare counts as covered", whether or not the member is declared yet.
    If `F` is not covered by own refs, the token is a genuine unlisted dependency on `F` and is flagged with the existing symbol-branch message wording, but ONLY when `F` actually declares `Member` (via the existing declaration-form check for `Member` against `[F]`); when `F` does not declare it (inherited member, extension method elsewhere, member to be added by another card), the token is unresolvable and never flagged.
  - Zero or more than one declaring file: fall through to today's behavior (`_resolve_symbol_files` + `_filter_matches_by_qualifier`), which still serves lowercase package/namespace qualifiers such as Go's `reedengine.New`.
  Framework-qualifier exclusion (previous Decision) runs before this.
- Rationale: fixes the reported `HydraulicsParticipant.Replace` -> `CoreConduit.cs` misresolution at its cause (qualifier was never treated as a type) and implements the third expectation directly.
  Uppercase-qualifier gating avoids reinterpreting Go package qualifiers.
- Rejected: covering by "any Edits: file in the card" -- too permissive (would silence a real dependency on an unrelated Edits: file).
  Filtering only the declared-member set to the card's Edits: files -- does not handle a member the card is about to add, which is exactly the reported case.

### message-and-error-shape-unchanged

- Decision: the emitted `message` wording and error-dict shape of context-completeness are unchanged (a downstream fixer-doc check parses them).
- Rationale: stated in the existing `_check_context_completeness` docstring.
- Rejected: new message variants for the type-qualified case.

### wiki-guard-lives-in-repo

- Decision: the hook currently exists ONLY as an inline `grep -qE '\.wiki\b'` one-liner in the operator's global `~/.claude/settings.json` (searched the repo, plugin, cache, and marketplaces: no tracked source).
  Since a global settings file cannot be part of a task branch, ship the logic in the plugin: new `plugins/mill/scripts/_wiki_guard.py` exporting `command_touches_wiki(command: str) -> bool`, and a hook CLI `plugins/mill/scripts/millpy-wiki-guard.py` that reads the PreToolUse JSON from stdin and, when `command_touches_wiki` is true, prints the same `permissionDecision: deny` JSON (same reason text) as today; otherwise prints nothing.
  Add `_claude_settings.reconcile_wiki_guard_hook(settings_path, hook_command)` which (a) removes any legacy Bash-matcher PreToolUse hook whose command contains `daemon-owned` and `\.wiki\b`, (b) adds the new hook entry if absent, (c) leaves all other hooks/keys alone, (d) writes only when changed -- same idempotent pattern as `reconcile_destructive_denylist`.
  Wire it into mill-setup Phase 4.8's inline script.
  Exact hook command template, built by the Phase 4.8 script from `plugin_root = _config.resolve_plugin_root_from_syspath(sys.path)` (already computed there for the venv path): `PYTHONPATH="<plugin_root>/scripts" "$MILL_PYTHON" "<plugin_root>/scripts/millpy-wiki-guard.py"`.
  `$MILL_PYTHON` is available to hooks because Phase 4.8 writes it into settings `env`.
  `plugin_root` is the versioned plugin cache directory, so the path goes stale when the plugin cache is refreshed to a new version; the guard then fails open (script missing, non-zero exit, no deny JSON, command proceeds) and re-running mill-setup Phase 4.8 rewrites it.
  This staleness is accepted; it is the same lifecycle as `MILL_PYTHON` itself, which is also written as a versioned cache path.
  `reconcile_wiki_guard_hook`'s "already correct" comparison keys on exact string equality of the hook entry's `command` for a Bash-matcher PreToolUse entry; an existing Bash-matcher entry whose command contains either `millpy-wiki-guard.py` (an older versioned path) or the legacy markers (`daemon-owned` and the `\.wiki\b` grep) is replaced in place rather than duplicated.
  Only the matching hook object inside an entry's `hooks` list is replaced; other hook objects in the same entry are preserved, and an entry is dropped only when its `hooks` list becomes empty.
- Rationale: makes the fix testable and delivered by `mill-setup`, rather than an untracked one-line edit only the current operator has.
  Follows the existing `_claude_settings` reconcile pattern.
- Rejected: only documenting a replacement one-liner (untestable, no delivery path); editing the operator's `~/.claude/settings.json` directly from this task (outside worktree isolation and not a repo change).
  NEEDS-ATTENTION at merge time: the already-installed global hook stays the old one until the operator re-runs mill-setup Phase 4.8 (or replaces the entry by hand).

### wiki-guard-detection-algorithm

- Decision: `command_touches_wiki` is token-based, not substring-based.
  1. Strip heredoc bodies (`<<[-]?['"]?TAG['"]?` through the matching terminator line) from the command text -- heredoc bodies are data, never shell.
  2. Split the remainder with `shlex.split(posix=True)` after normalising shell operators (`;`, `&&`, `||`, `|`, `(`, `)`) into separate tokens (a small tokenizer using `shlex.shlex(punctuation_chars=True)` is acceptable).
     On `ValueError` (unbalanced quotes), fail closed: fall back to the old `\.wiki\b` regex on the whole text.
  3. A token is a wiki path when, split on `/` and `\`, some component is exactly `.wiki` (covers `.wiki`, `.wiki/Home.md`, `../.wiki/x`, `foo/.wiki/x`; does NOT cover `hub.wiki`, `path/hub.wiki`, `x.wikipedia`).
     A token containing whitespace is prose (a `--body`/`-m`/`echo` argument), not a path, and is skipped -- except that for `bash|sh|zsh -c <arg>` and `eval <arg>` the argument is recursively passed to `command_touches_wiki`, and any `$(...)` / backtick substring inside a whitespace-containing token is likewise recursed into.
     `VAR=.wiki/x` style assignments and `--flag=.wiki/x` are handled by splitting a token on `=` once and testing the right-hand side too.
  4. `git -C .wiki ...`, `cd .wiki`, `cat .wiki/Home.md` all satisfy step 3 and are denied, as today.
  5. Pattern/text arguments are not paths (this is the grep case from the Problem section, e.g. grep with the junction name as its search pattern).
     Per simple command (segments split on `;`, `&&`, `||`, `|`): when the command word (basename, after skipping leading `VAR=value` assignments, `sudo`, `env`, and `command`) is `echo` or `printf`, no argument is tested (all are text).
     When it is `grep`, `egrep`, `fgrep`, `rg`, `ag` or `awk`, the pattern/program argument is skipped and every other argument is still tested: the pattern is the first non-flag argument, or the value of `-e`/`--regexp`/`-f`/`--file` when given (in which case there is no positional pattern).
     So a grep with `.wiki` as the pattern and `plugins` as the path is allowed, while `grep foo .wiki/Home.md` and `grep -r foo .wiki` are denied.
     Non-flag detection: an argument starting with `-` is a flag; `--` ends flag parsing.
     This is a heuristic, not a full option parser: flags that take a separate value argument (e.g. `-A 3`, `-m 5`) may cause the value to be taken as the pattern; accepted, since the resulting error mode is either a missed pattern skip (a false positive, as today) or skipping a non-path token.
  Implementation order (authoritative over the numbering above): strip heredoc bodies, then extract and recurse into `$(...)`/backtick spans, then tokenize the remainder, then apply per-command rules (step 5) and the component test (step 3).
  Command substitution is located BEFORE tokenizing and independently of the echo/printf skip: step 2's tokenizer first extracts every `$(...)` span (balanced-paren scan) and every backtick span from the raw text outside heredoc bodies, replaces each with a placeholder token, and recurses `command_touches_wiki` on each extracted inner string.
  So `echo $(cat .wiki/x)` is True (the inner `cat .wiki/x` is denied) while `echo .wiki` stays False (plain text argument skipped).
  Accepted conservative behavior (recorded so plan/tests do not treat these as bugs): a whitespace-free quoted argument that is a wiki path (`--body ".wiki/x"`, `cp x ".wiki/y"`) is denied, since it cannot be told from a real path argument; and `$(...)`/backtick recursion also fires inside single quotes although the shell would not execute it.
- Rationale: the two reported false positives (quoted body text, heredoc text) and the `hub.wiki` suffix case are all eliminated; the true positives (junction used as a path argument) are preserved; fail-closed on parse errors preserves the guard's safety purpose.
- Rejected: regex-only tweaks such as `(^|[\s/])\.wiki(/|$)` (still fires on quoted prose containing ` .wiki/` and on heredocs); dropping the Bash hook (removes the real protection the project's CLAUDE.md describes).
- Assumption made autonomously: escaping the guard by building the path dynamically (`x=.w; cat ${x}iki/Home.md`) is out of scope -- the guard is a footgun-preventer, not a security boundary, exactly as today.

## Technical context

- `_plan_validate.py` symbol branch: `_check_context_completeness` (search for `def _check_context_completeness`).
  Relevant helpers: `_symbol_candidate_shape` (returns `(search_key, qualifier)`; a dotted token yields the trailing segment as `search_key`), `_resolve_symbol_files` (declaration-form matching over `candidate_files` only, memoized in `search_cache` keyed by `search_key` alone -- keep it qualifier-independent), `_filter_matches_by_qualifier` (namespace/dir narrowing, `.go`/`.cs`/`.ts`), `_covered_by_own_refs`, `_card_own_reference_set`, `_compute_plan_wide_cited_files` (the candidate search space is only files cited somewhere in the plan).
- The `.cs` member regex (`cs_member_re`) in `_resolve_symbol_files` matches `public ... <sym> ... [({;=]`, which is how a bare `InvalidOperationException` can match a file that only mentions it in a member-shaped line.
  The framework exclusion is applied before resolution, so this regex needs no change.
- Docstring of `_check_context_completeness` enumerates numbered exemptions; add the framework-type and type-qualified-member behavior there (as new numbered items), keeping the "message must not drift" note.
- `_claude_settings.py`: existing `merge_permission_allowlist` and `reconcile_destructive_denylist` are the pattern (load-or-{} , mutate, write only if changed).
  Hooks live under `data["hooks"]["PreToolUse"]`, a list of `{matcher, hooks: [{type, command}]}` entries.
- mill-setup Phase 4.8 in `plugins/mill/skills/mill-setup/SKILL.md` holds the inline script that already calls the two `_claude_settings` helpers; add the third call and one log line, and extend the trailing "emit" sentence.
- Script-naming: `millpy-*.py` CLIs + `_*.py` helpers, flat in `plugins/mill/scripts/`; no skill wrapper is created for the hook CLI (it is not user-invocable).
  Decision: mill-plan verifies at plan time whether `mill-skills-from-scripts` / `SKILLS.md` generation or any unit test enumerates every `millpy-*.py` script; if so, the plan adds the minimal exclusion or entry needed to keep that check green, and otherwise touches nothing.
- The hook CLI runs under `$MILL_PYTHON` with `PYTHONPATH` set to the plugin scripts dir; it must import only stdlib plus `_wiki_guard`.
- Output of `print()` in scripts: ASCII only (CLAUDE.md).

## Constraints

- No `sed` anywhere, including in any generated prompt/brief.
- Plan `verify:` commands must start with `PYTHONPATH=` and use `uv run --project plugins/mill` for unit tests (see CLAUDE.md).
- `_plan_validate` message wording and error-dict shape must not change.
- `CLAUDE_PLUGIN_ROOT` for intra-plugin paths in skills; never `plugins/mill/...` in SKILL.md bash.
- Generated scripts use ASCII-only output.

## Testing

Test files: `plugins/mill/unit_tests/test-plan-validate.py` (existing symbol-branch tests are the pattern: temp project dir, `_make_overview`/`_make_batch_file`/`_write_plan`, `_plan_validate.run`), new `plugins/mill/unit_tests/test-wiki-guard.py`, and the existing `_claude_settings` test file (locate with a grep for `reconcile_destructive_denylist` in `unit_tests/`).
TDD candidates: `command_touches_wiki` (pure function) and `reconcile_wiki_guard_hook`.

context-completeness scenarios:
- Bare `InvalidOperationException` in Requirements: with a cited `.cs` file that has a member-shaped line mentioning it -> no error.
- Same but the cited file type-declares `class InvalidOperationException` -> still resolves and flags (override).
- `Path.Combine` / `Math.Max` (framework qualifier) -> no error.
- `HydraulicsParticipant.Replace` where the card's `Edits:` is `HydraulicsParticipant.cs` (declares the type, member not yet declared) and a different cited file `CoreConduit.cs` declares `Replace` -> no error.
- Same, member already declared in the Edits: file -> no error.
- `HydraulicsParticipant.Replace` where `HydraulicsParticipant.cs` is NOT in the card's own refs but is cited elsewhere in the plan and declares `Replace` -> one error naming `HydraulicsParticipant.cs`.
- Type declaring file does not declare the member -> no error.
- Lowercase Go qualifier (`reedengine.New`) still resolves through `_filter_matches_by_qualifier` (regression guard; existing tests already cover, keep passing).

wiki-guard scenarios (`command_touches_wiki`):
- True: `grep foo .wiki/Home.md`, `grep -r foo .wiki`, `cat .wiki/Home.md`, `git -C .wiki status`, `cd .wiki && ls`, `ls ../.wiki/`, `bash -c "cat .wiki/x"`, `echo $(cat .wiki/x)`, unbalanced-quote fallback containing `.wiki`.
- False: grep with `.wiki` (bare, quoted, or backslash-escaped `\.wiki`) as its pattern and `plugins` as the path, `grep -e .wiki plugins`, `echo .wiki`, `echo "path/hub.wiki"`, `gh issue create --body "error at /x/hub.wiki"`, `gh issue create --body "see .wiki/Home.md for details"`, heredoc `cat > .scratch/x.md <<'EOF'\n...\n.wiki\nEOF`, `grep foo file.txt`.
- Accepted-conservative (pin as True): `cp x ".wiki/y"`, and a single-quoted `$(cat .wiki/x)` argument to a non-echo command.
- CLI: stdin JSON with a wiki-touching command prints deny JSON; benign command prints nothing; malformed stdin prints nothing (never crash the tool call).
- `reconcile_wiki_guard_hook`: an entry with an older versioned `millpy-wiki-guard.py` path is replaced, not duplicated; empty settings gets the entry; legacy inline entry is replaced; already-correct is a no-op (file mtime/content unchanged); unrelated hooks and keys untouched.

## Q&A log

- **Q:** Where does the wiki-guard hook live, and can this task fix it? **A:** [auto-pick] It lives only in the operator's global `~/.claude/settings.json`; ship the logic in the plugin plus a settings reconcile in mill-setup Phase 4.8. **Why:** a task branch cannot carry the global file, and the plugin path is testable and deliverable.
- **Q:** Should framework-type detection be a curated name list or a heuristic? **A:** [auto-pick] Curated name list with a repo-type-declaration override. **Why:** categorical requirement, no compiler available, override prevents false negatives.
- **Q:** Should the hook guard resist dynamically built paths? **A:** [auto-pick] No. **Why:** it prevents accidents, it is not a security boundary.
- **Q:** Parse failure in the hook tokenizer: allow or deny? **A:** [auto-pick] Deny by falling back to the old substring regex. **Why:** fail closed keeps the protection intact.
