# Batch: runtime-and-skills

```yaml
task: 24 (A) — mill-misc-fixes
batch: runtime-and-skills
number: 2
cards: 4
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

Implements bugs B (`${CLAUDE_PLUGIN_ROOT}` brace-form sweep), C (rate-limit error message stdout fallback), and D (Monitor-tool guidance bullet) in one batch. The four cards are sequenced so the cli/SKILL.md update (Card 7) precedes the brace-form sweep (Card 8) — the sweep's verification grep would otherwise produce ambiguous results in the file Card 7 is editing. Cards 5 and 6 (bug C) are independent of Cards 7 and 8 (bugs B + D) but bundled here because they share batch-2's review surface and verify command. The verify command (`run-all.py`) catches the new rate-limit-error-message test added in Card 6 and any regression introduced by Card 5's refactor of `_invoke`. Card 8's mechanical sweep is verified in-card by `git grep -n '\${CLAUDE_PLUGIN_ROOT}' plugins/mill/skills plugins/codeguide/skills` returning only matches inside HTML comments, prose, or non-bash fenced regions; this is a manual inspection step, not part of `run-all.py`. The depends-on=[1] keeps the batch sequential so any test-suite regression introduced by batch 1 surfaces before batch 2 starts.

## Cards

### Card 5: Fall back to stdout for empty stderr in `_llm_claude.py:_invoke`

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_llm_claude.py:_invoke` (around lines 257-270), refactor the error-construction block. Before the `if rate_limited:` branch (currently line 262), introduce one local: `error_detail = (result.stderr or result.stdout or "")[:500]`. Remove the existing `stderr_snippet = (result.stderr or "")[:500]` assignment at line 261. In the `LLMRateLimitError` raise (line 263-265), the `LLMSessionError` raise (line 267-269), and the generic `LLMError` raise (line 270), replace `{stderr_snippet}` with `{error_detail}`. Do NOT change `_scan_rate_limit` (lines 126-154), the `rate_limited = _scan_rate_limit(...)` call, the exception class hierarchy, or the order of branch checks. The 500-char cap is preserved verbatim. The local rename from `stderr_snippet` to `error_detail` improves accuracy: it is no longer purely a stderr snippet.
- **Commit:** `fix(_llm_claude): fall back to stdout for empty stderr in error messages`

### Card 6: Test that rate-limit error message includes stdout fallback content

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_llm_claude.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new assertion block inside `main()` in `test-llm-claude.py`, immediately before the final `return errors` line. The block monkey-patches `_subprocess_util_mod.run` (the import alias used in the file at line 19) with `mock.patch.object` to return a `_subprocess_mod.CompletedProcess(args=[], returncode=1, stdout='{"type":"rate_limit_event","limit_type":"requests"}\n', stderr="")`. While the patch is active, call `run_bulk("ignored prompt", model="claude-sonnet-4-6")` inside a `try/except LLMRateLimitError as e:` and assert: (a) the exception type is `LLMRateLimitError` (not generic `LLMError` or `LLMSessionError`); (b) `"rate_limit_event" in str(e)`. Print `"PASS: rate-limit error message includes stdout fallback content"` on success; on failure increment `errors` and print `f"FAIL: ..."` on stderr. Keep the new block under 25 lines. Do NOT add new module-level imports — `_subprocess_mod`, `_subprocess_util_mod`, `mock`, and `LLMRateLimitError` are already imported (lines 11, 13, 19, 22).
- **Commit:** `test(_llm_claude): cover stdout-fallback path for rate-limit error message`

### Card 7: Add Monitor-tool and `$CLAUDE_PLUGIN_ROOT` bullets to `cli/SKILL.md`

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/cli/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Append two new bullets to the existing PowerShell section in `plugins/mill/skills/cli/SKILL.md`, immediately after the bullet `- PS5 → bash equivalents: ...` (currently line 31). The two new bullets are:
  - First: `- **Commands CC executes via the Monitor tool:** use bash syntax — Monitor runs bash, not PowerShell. PS syntax in a Monitor command yields exit 127 with no warning.`
  - Second: `- **\`$CLAUDE_PLUGIN_ROOT\` is a CC template token, not a Bash subshell variable.** CC substitutes it when loading SKILL.md, so the resolved literal path is visible in the loaded skill text. Autonomous agents (mill-plan, mill-go) constructing new Bash commands must use the resolved path verbatim — never reconstruct \`${CLAUDE_PLUGIN_ROOT}\` as a shell variable in new Bash commands, because it is empty in the Bash subshell on Windows.`
  Match the existing one-line bullet format (single `-` prefix, single-line text). Do not modify any other section, heading, or bullet in `cli/SKILL.md`. The plural `${CLAUDE_PLUGIN_ROOT}` form in the second bullet's prose is intentional — Card 8's sweep is restricted to fenced bash code blocks and will not touch this prose. The companion file `plugins/mill/skills/mill-go/SKILL.md` (in Context) illustrates how `$CLAUDE_PLUGIN_ROOT` is currently used in fenced bash blocks across the codebase; reading it confirms the failure mode the second bullet describes.
- **Commit:** `docs(cli-skill): add Monitor-tool and CLAUDE_PLUGIN_ROOT bullets`

### Card 8: Drop curly braces from `${CLAUDE_PLUGIN_ROOT}` in fenced bash blocks across all SKILL.md files

- **Context:**
  - `plugins/mill/skills/cli/SKILL.md`
- **Edits:**
  - `plugins/codeguide/skills/codeguide-generate/SKILL.md`
  - `plugins/codeguide/skills/codeguide-maintain/SKILL.md`
  - `plugins/codeguide/skills/codeguide-setup/SKILL.md`
  - `plugins/codeguide/skills/codeguide-update/SKILL.md`
  - `plugins/mill/skills/mill-abandon/SKILL.md`
  - `plugins/mill/skills/mill-add/SKILL.md`
  - `plugins/mill/skills/mill-claim/SKILL.md`
  - `plugins/mill/skills/mill-cleanup/SKILL.md`
  - `plugins/mill/skills/mill-color/SKILL.md`
  - `plugins/mill/skills/mill-fetch-issues/SKILL.md`
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-groom/SKILL.md`
  - `plugins/mill/skills/mill-inspect/SKILL.md`
  - `plugins/mill/skills/mill-list/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-resume/SKILL.md`
  - `plugins/mill/skills/mill-setup/SKILL.md`
  - `plugins/mill/skills/mill-skills-from-scripts/SKILL.md`
  - `plugins/mill/skills/mill-skills-index/SKILL.md`
  - `plugins/mill/skills/mill-spawn/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-status/SKILL.md`
  - `plugins/mill/skills/mill-terminal/SKILL.md`
  - `plugins/mill/skills/mill-vscode/SKILL.md`
  - `plugins/mill/skills/mill-worktree/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In every file listed under Edits, replace occurrences of `${CLAUDE_PLUGIN_ROOT}` with `$CLAUDE_PLUGIN_ROOT` (drop the curly braces) ONLY when the occurrence appears inside a fenced ```bash ... ``` code block. Do NOT modify occurrences inside HTML comments (`<!-- ... -->`), plain prose paragraphs, table cells, inline backticks (single-backtick ``${CLAUDE_PLUGIN_ROOT}`` in narrative text), or fenced code blocks tagged with anything other than `bash` (e.g. ```python, ```yaml, ```text). Approach: for each file, scan top-to-bottom tracking fence state — when inside ```bash...``` perform the replacement, otherwise skip the line. After all files are edited, run `git grep -n '\${CLAUDE_PLUGIN_ROOT}' plugins/mill/skills plugins/codeguide/skills` from the worktree root and visually verify every remaining match is in HTML comment, prose, table cell, inline-backtick, or non-bash fenced block. The companion file `plugins/mill/skills/cli/SKILL.md` (in Context, post-Card-7) contains the bullet documenting why this change is needed and confirms the prose-vs-fenced distinction. Files in Edits each have at least one occurrence per the count grep done at planning time (cli/SKILL.md is NOT in Edits because it does not currently contain `${CLAUDE_PLUGIN_ROOT}` in any fenced block — only in the new prose bullet from Card 7, which must remain untouched). Skill: invoke `git-commit` with the Commit message below.
- **Commit:** `fix(skills): unbrace CLAUDE_PLUGIN_ROOT references in fenced bash blocks`

## Batch Tests

The verify command `python plugins/mill/unit_tests/run-all.py` covers regressions introduced by Card 5's refactor of `_llm_claude.py:_invoke` (any existing test that catches `LLMRateLimitError`, `LLMSessionError`, or `LLMError` must still pass) and exercises Card 6's newly-added rate-limit-error-message test. Cards 7 and 8 do not affect Python source — their verification is read-the-file (Card 7) and the in-card git-grep check (Card 8). The grep check is a manual inspection step inside Card 8's commit; no automated test enforces "all bash blocks unbraced" because building such a test would mean re-implementing the fence-tracking parser the card itself uses. Pre-batch state (after batch 1): all 47 unit-test files pass. Post-batch expectation: still all 47 unit-test files pass, with `test-llm-claude.py`'s test count incremented by one (Card 6's new assertion).
