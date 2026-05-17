# Batch: mill-go-config

```yaml
task: "61 (A) -- Review pipeline fixes"
batch: mill-go-config
number: 4
cards: 3
verify: null
depends-on: []
```

## Batch Scope

Documentation-and-schema-only batch covering #300 and #319. (1) Add an explicit "exit non-zero + no JSON" handling branch to the holistic-review section of `mill-go` SKILL.md, mirroring the per-batch section's wording (#300). (2) Add `roles.code-review.holistic.fallback_reviewer` and `roles.code-review.holistic.fallback_on` schema entries to the template `mill-config.yaml` and the hub-root `mill-config.yaml` (per CLAUDE.md mirror rule). (3) Add a "Step 3.6 -- rate-limit fallback" sub-section to `mill-go` SKILL.md's holistic loop that consumes the schema and rotates to the fallback reviewer when step 3.5's ERROR-only retry surfaces a rate-limit error string on both passes.

There is no production code to run for this batch, so `verify: null`. The new schema keys must round-trip through `_review_common.load_config` without an "unknown key" warning; that is the only mechanical confirmation needed. The mill-go SKILL.md edits are prose-only, so no automated test catches their correctness -- the holistic crash-recovery and rate-limit-fallback behaviour will be observed in the next autonomous run.

## Cards

### Card 9: mill-go holistic EXIT-without-JSON branch

- **Context:**
  - `_mill/discussion.md`
  - `_mill/plan/00-overview.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/mill/skills/mill-go/SKILL.md`, locate the `## Holistic code review` section, sub-step 3 (the `millpy-bg.py` invocation block). After the existing "Poll and extract JSON as per the per-batch pattern." sentence, add a new paragraph that mirrors the per-batch section's "Only treat exit 1 as an unrecoverable pre-launch error when the JSON line in the log file is absent." phrasing.
  - Concrete wording to add (place immediately after the existing sub-step 3 paragraph, before sub-step 3.5):
    > **Exit handling.** If `[mill-bg] EXIT` reports a non-zero exit AND no JSON summary line is present in the log, halt with "BLOCKED: holistic review pre-launch failure" and surface the last stderr line from the log to the user. If a JSON envelope IS present (even with `verdict: ERROR`), drop through to sub-step 3.5 ERROR-only retry as normal. Matches the per-batch section's "only treat exit 1 as unrecoverable when JSON line is absent" branch.
  - Keep step numbering unchanged. Verify by `grep -n "exit 1\|EXIT\|no JSON" plugins/mill/skills/mill-go/SKILL.md` that the holistic section now contains a parity branch with the per-batch section.
- **Commit:** `docs(mill-go): add exit-without-json branch to holistic review (#300)`

### Card 10: fallback_reviewer schema in mill-config templates

- **Context:**
  - `_mill/discussion.md`
  - `_mill/plan/00-overview.md`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
  - `mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/mill/templates/mill-config.yaml`, locate the `code-review:` block (currently lines 136-146). Inside the existing `holistic:` sub-block, add two new keys after `reviewer: sonnethigh` (and before the commented-out `large_prompt:` block). Use 6-space indentation -- `code-review:` is at column 2, `holistic:` is at column 4, and child keys of `holistic:` (including the existing `reviewer:` and `rounds:`) sit at column 6. The literal text to insert (preserving exact column-6 indent):
    ```yaml
          fallback_reviewer: null     # reviewer name from agents.yaml to swap in on consecutive rate-limit ERRORs; null = no fallback
          fallback_on:                 # list of substrings (lowercased match) in reviews[].error that trigger fallback
            - "rate-limit"
    ```
  - Sanity-check before committing: open the edited file and confirm `fallback_reviewer:` lines up vertically with the existing `reviewer: sonnethigh` line. If they don't line up, indentation is wrong.
  - In the hub-root `mill-config.yaml`, add the commented-out version of the same keys, following the file's convention of commented overrides. Concretely, inside the existing `# code-review:` commented block (currently around lines 86-93), add the two keys also commented out so an operator can uncomment to enable. Use the same indentation depth as the surrounding commented lines.
  - Validate by running `python plugins/mill/unit_tests/run-all.py` -- the merged-config tests must NOT emit a `[config] unknown key` warning for `fallback_reviewer` or `fallback_on`. If they do, the registry of known keys in `_config.warn_unknown_keys` (or wherever the known-key set is defined) needs the two new keys added; check `_config.py` and update if needed. (Search for `KNOWN_KEYS`, `warn_unknown_keys`, or `unknown key` to locate.)
  - If `_config.py` does NOT have an explicit key registry (i.e. the warn function compares against the template keys structurally), the schema addition in the template is sufficient -- no `_config.py` change needed. The unit-test run will confirm.
- **Commit:** `feat(mill-config): add code-review holistic fallback_reviewer schema (#319)`

### Card 11: mill-go holistic rate-limit fallback step

- **Context:**
  - `_mill/discussion.md`
  - `_mill/plan/00-overview.md`
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/mill/skills/mill-go/SKILL.md` `## Holistic code review` section, locate the existing sub-step 3.5 (ERROR-only-aggregate retry). After the existing "On the **second** consecutive run that still has top-level `verdict: \"ERROR\"`, halt..." sentence, modify the halt path to first check for rate-limit fallback before halting. Concrete edit:
    - Find the line `The round counter \`H\` is **not** consumed -- the round produced no reviewable output. On the **second** consecutive run that still has top-level \`verdict: "ERROR"\`, halt with \`BLOCKED: holistic code review ERROR-only round {H}\` and surface each entry's \`error\` string from \`reviews[]\` to the user.`
    - Replace the halt clause with: "On the **second** consecutive run that still has top-level `verdict: \"ERROR\"`, **first check rate-limit fallback** (see sub-step 3.6 below). If sub-step 3.6 does NOT apply, halt with `BLOCKED: holistic code review ERROR-only round {H}` and surface each entry's `error` string from `reviews[]` to the user. Do NOT auto-retry beyond the second pass."
  - Add a new sub-step **3.6 -- Rate-limit fallback** between 3.5 and 4. Place it as a numbered sub-section inside `## Holistic code review`, immediately after the 3.5 block. Content (verbatim, indented as a sub-section):

    ```markdown
    3.6. **Rate-limit fallback (no round consumed)**

       When sub-step 3.5's second pass returns `verdict: ERROR` AND `roles.code-review.holistic.fallback_reviewer` is not null AND any `reviews[*].error` string contains (case-insensitive) a substring listed in `roles.code-review.holistic.fallback_on` (default `["rate-limit"]`):

       1. Emit `_notify.notify("mill-go.holistic-fallback", f"swap reviewer -> {fallback_name}", slug=slug, round=H)`.
       2. In-memory mutation: `cfg["roles"]["code-review"]["holistic"]["reviewer"] = cfg["roles"]["code-review"]["holistic"]["fallback_reviewer"]`. Do NOT write back to disk -- the swap lasts only for the current mill-go invocation.
       3. Re-run sub-step 3 (the holistic review CLI) with the swapped reviewer. The round counter `H` is **not** consumed.
       4. If the fallback reviewer ALSO returns `verdict: ERROR` on its first pass: halt with `BLOCKED: holistic code review fallback also failed at round {H}` and surface every `reviews[*].error` from BOTH the original and fallback attempts. Do NOT cascade to a second fallback.
       5. If `pipeline.autonomous_mode: true` AND `fallback_reviewer is None` AND a rate-limit was detected on both 3.5 passes: halt with `BLOCKED: holistic rate-limited, no fallback_reviewer configured`. The operator-visible message is intentional -- silent infinite fallback is wrong.

       Operator interactive path (no `autonomous_mode`, no `fallback_reviewer`): user prompt remains identical to today (the existing step 5 ROUND-EXHAUSTION sub-section handles this case).
    ```

  - Verify by `grep -n "fallback_reviewer\|fallback_on\|3.6" plugins/mill/skills/mill-go/SKILL.md` that the new sub-step is referenced.
- **Commit:** `docs(mill-go): add holistic rate-limit fallback step 3.6 (#319)`

## Batch Tests

No automated tests. Verification is:
1. `python plugins/mill/unit_tests/run-all.py` confirms the schema addition does not produce an `unknown key` warning.
2. Manual `grep` confirms the SKILL.md edits contain the parity branch (#300) and the new sub-step 3.6 (#319).
3. The fallback behaviour is observable only in production runs that hit a rate-limit; out of scope to mock here.
