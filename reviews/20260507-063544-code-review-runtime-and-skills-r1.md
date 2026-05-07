# Review: 24 (A) — mill-misc-fixes — runtime-and-skills

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: runtime-and-skills
date: 2026-05-07
```

## Findings

### [BLOCKING] Card 8 missed bash-block substitution in mill-skills-from-scripts
**Location:** `plugins/mill/skills/mill-skills-from-scripts/SKILL.md` Step 5
**Issue:** Step 5's fenced ` ```bash ` block still contains `${CLAUDE_PLUGIN_ROOT}` (braced form): `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-skills-index.py"`. This is a top-level `bash`-tagged fence (not nested inside the outer untagged ` ``` ` block from Step 3), so it falls squarely in Card 8's sweep scope.
**Fix:** Replace both occurrences in that bash block with `$CLAUDE_PLUGIN_ROOT` (no braces), matching every other bash block in the repo.

### [NIT] Bare assert in Card 6 test bypasses error accumulation
**Location:** `plugins/mill/unit_tests/test-llm-claude.py` (new block, `except LLMRateLimitError as e:` branch)
**Issue:** `assert "rate_limit_event" in str(e)` raises `AssertionError` uncaught if it fails, instead of `errors += 1` + stderr FAIL print as the plan specifies. The test harness's `run-all.py` would see a crash rather than a controlled failure count.
**Fix:** Replace the bare `assert` with `if "rate_limit_event" not in str(e): errors += 1; print(f"FAIL: ...", file=sys.stderr)` followed by the PASS print in the else branch.

## Verdict

REQUEST_CHANGES — one missed substitution in `mill-skills-from-scripts/SKILL.md` Step 5's bash block.