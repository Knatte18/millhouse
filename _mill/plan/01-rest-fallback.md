# Batch: rest-fallback

```yaml
task: 'git-pr: gh pr create fails on GraphQL 5xx with no REST fallback documented'
batch: rest-fallback
number: 1
cards: 1
verify: null
depends-on: []
```

## Batch Scope

This batch delivers the entire fix: a new `### 10.5 REST-API fallback` step in
`plugins/mill/skills/git-pr/SKILL.md`, inserted between the existing step 10
(`Create the PR`) and step 11 (`Fallback to browser`), plus the two small edits
that wire it in — step 11's reworded trigger condition and step 12's
tier-aware report wording. All three edits land in the same file and only make
sense together (step 11's trigger references step 10.5's outcome; step 12's
report references whichever tier fired), so this is one batch, one card, one
commit. There is no external interface for a downstream batch to consume —
this is the only batch in the plan.

## Cards

### Card 1: Insert step 10.5 REST fallback; reword step 11 trigger; update step 12 report

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/git-pr/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  1. Insert a new `### 10.5 REST-API fallback` section immediately after the
     existing `### 10. Create the PR` section and before `### 11. Fallback to
     browser` (mirrors the file's existing `### 1.5 Detect task branch`
     sub-step numbering convention). Content:

     ```````markdown
     ### 10.5 REST-API fallback

     If `gh pr create` (step 10) exits non-zero, attempt the REST API before
     falling back to the browser.

     Skip this step entirely if `gh` was already determined to be unavailable
     in step 7 — `gh api` needs the same binary as `gh pr create`. Go straight
     to step 11.

     ```bash
     gh api repos/<owner>/<repo>/pulls -X POST \
       -f title="<title>" \
       -f body="$(cat <<'BODY'
     <body text>
     BODY
     )" \
       -f head="<branch>" \
       -f base="<base>" \
       -q .html_url
     ```

     `<owner>/<repo>` is the value resolved in step 8. `<branch>`, `<base>`,
     `<title>`, `<body>` are the same values used in step 10 — no new content
     generation.

     If this command succeeds (prints a URL): the PR was created via REST.
     Record this for step 12's report and skip step 11.

     If this command also fails:

     - Inspect the combined failure output of both step 10 and this step for
       an "already exists" pattern (case-insensitive match on GitHub's
       standard duplicate-PR message, e.g. "A pull request already exists for
       `<owner>:<branch>`").
       - If matched: look up the existing PR's URL — re-run `gh pr view
         --json url -q .url`, or on its failure `gh api
         repos/<owner>/<repo>/pulls -X GET -f head="<owner>:<branch>" -f
         state=open -q '.[0].html_url'`. Report that URL (see step 12) and
         stop — do not proceed to step 11. If both URL-lookup attempts also
         fail, report "A pull request already exists for this branch, but its
         URL could not be retrieved — check the repository's Pull Requests
         tab" and stop — do not proceed to step 11.
       - If not matched: proceed to step 11.
     ```````

  2. In the existing `### 11. Fallback to browser` section, replace the
     trigger sentence "If `gh` is not installed or the `gh pr create` command
     fails, fall back to opening a pre-filled GitHub PR URL in the browser:"
     with: "If `gh` is not installed, or both step 10 and step 10.5 have
     failed (and step 10.5's own duplicate-PR check did not already resolve
     and report a URL), fall back to opening a pre-filled GitHub PR URL in the
     browser:" Add one sentence immediately after that trigger sentence: "Skip
     step 10.5 entirely and come straight here when `gh` was already
     determined unavailable in step 7." The rest of step 11 (the three
     platform-specific `open`/`start`/`xdg-open` command blocks and the
     URL-encode/platform-detect notes) is unchanged.

  3. In the existing `### 12. Report` section, keep the current text
     ("Tell the user the PR URL from `gh` output, or that the browser was
     opened as fallback.") as the default-path wording, and add: when step
     10.5 (REST) fired and succeeded, state "PR created via REST API
     fallback: `<url>`" instead of the plain URL line; when the duplicate-PR
     check in step 10.5 resolved and reported a URL, state "Existing PR
     found: `<url>`" instead. Do not add any wording that names the cause
     ("GraphQL was unavailable") — step 10.5 fires on any non-zero exit from
     step 10 without diagnosing why, so the report must stay cause-agnostic.

  Do not change steps 1–9 or 13+ (there is no step 13 in the current file).
  Do not change step 7's existing-PR check.

- **Commit:** `docs(git-pr): add REST-API fallback tier for gh pr create failures`

## Batch Tests

`verify: null` — this batch edits `plugins/mill/skills/git-pr/SKILL.md`, a
markdown skill-instructions file with no executable code and no unit-test
target (per `_mill/discussion.md`'s Testing section). Verification is manual /
scenario-walkthrough, done by the plan/code reviewer reading the rendered
diff:

- **Happy path (no regression):** step 10's `gh pr create` command block and
  step 12's default reporting text must be byte-identical to before this
  change.
- **REST fallback path:** the new step 10.5's `gh api ... -f ... -q
  .html_url` block is syntactically well-formed bash, targets
  `repos/<owner>/<repo>/pulls`, and passes exactly `title`, `body`, `head`,
  `base` — matching step 10's fields, no extras.
- **Duplicate-PR path:** the "already exists" match and the fallback lookup
  (`gh pr view` retry, then REST `GET .../pulls?head=...&state=open`) appear
  in step 10.5, ordered after both create attempts.
- **Browser-fallback trigger correctness:** step 11's reworded trigger (`gh`
  unavailable OR both step 10 and step 10.5 failed) still lets the existing
  `gh`-not-installed path skip straight to browser without attempting step
  10.5.
