# Discussion: git-pr: gh pr create fails on GraphQL 5xx with no REST fallback documented

```yaml
task: 'git-pr: gh pr create fails on GraphQL 5xx with no REST fallback documented'
slug: git-pr-graphql-5xx-fallback
status: discussing
parent: main
```

## Problem

`gh pr create` (invoked by the `git-pr` skill's step 10) uses GitHub's GraphQL API for both
the existing-PR check (step 7, `gh pr view`) and the create mutation itself (step 10).
When GraphQL has a transient outage, `gh pr create` fails outright — even though the REST API
is healthy in the same window and could create the PR just fine.

This was directly observed during a real `mill-go` → `mill-finalize` run (source repo
`Knatte18/loomyard`, branch `planparser-plan-dir`, 2026-08-17): `gh pr create` failed twice in
a row with `HTTP 503: No server is currently available to service your request... (https://api.github.com/graphql)`,
while `gh api /rate_limit` and `gh api repos/<owner>/<repo>/pulls -X POST` (REST) both worked in
the same window.

`git-pr/SKILL.md` step 11 currently documents only a browser-URL fallback for `gh pr create`
failure — it hands the operator a pre-filled compare URL and stops the automated flow. There is
no REST-API fallback, so a GraphQL-specific (not GitHub-wide) outage forces a manual hand-off
even though full automation was still possible via REST.

## Scope

**In:**
- A new REST-API fallback tier for `gh pr create` failure in `git-pr/SKILL.md`, inserted between
  the existing GraphQL create (step 10) and the browser fallback (step 11).
- Trigger condition, payload construction, response parsing, and duplicate-PR handling for that
  new tier.
- Updating step 11's trigger condition so browser fallback only fires when `gh` is unavailable or
  both the GraphQL and REST create attempts fail.
- Updating step 12 (Report) to mention which tier was used, but only when a non-default tier fired.

**Out:**
- Changing step 7's existing-PR check (`gh pr view --json url`). The step's text defines only two
  explicit branches — "PR already exists → stop" and "`gh` not installed → proceed to step 8" —
  with no explicit third branch for "`gh` installed but the command failed for another reason"
  (e.g. a GraphQL 5xx, or simply "no PR found"). By the file's linear step-then-proceed structure,
  that unaddressed case falls through to "proceed to step 8" the same as the gh-unavailable
  branch; this is an inferred convention from the document's structure, not a rule the text states
  outright. That inference can be wrong during a GraphQL outage (a PR could genuinely exist and
  the check simply failed to confirm it), but the consequence is caught safely downstream (see
  Decisions → duplicate-pr-detection) rather than by adding a second REST-based existence check
  here — the downstream catch doesn't depend on step 7's fallthrough being an explicit rule,
  only on the fallthrough actually happening, which the linear-proceed structure supports.
- Retry/backoff logic on the original `gh pr create` call before falling back. Blindly retrying
  the identical GraphQL mutation risks a create-then-503-then-retry double-create race; that race
  already exists today in the browser-fallback path and isn't being solved by this task, so
  adding retry timing here would be unrelated scope creep.
- Draft-PR support. The current skill never creates draft PRs (no `--draft` flag anywhere in step
  10), so the REST payload carries only `title`, `body`, `head`, `base` — no `draft` field.
- Any change to steps 1–9 or 13+ (branch validation, base-branch resolution, merge/verify/push,
  repo detection, PR-content generation). Only steps 10–12 are touched.

## Decisions

### rest-fallback-trigger

- Decision: Attempt the REST-API fallback (step 10.5) on **any** non-zero exit from `gh pr
  create` in step 10 — not only when the error text looks like a GraphQL 5xx.
- Rationale: Matching GitHub's error text (`"GraphQL"`, `"50[0-9]"`, `"No server is currently
  available"`) is fragile — the message format can drift across `gh` CLI versions and outage
  types. An unconditional REST attempt is simpler and still correct: if the underlying cause
  isn't transient (e.g. an auth failure), the REST attempt fails for the same reason and falls
  through to browser at negligible cost.
- Rejected: Pattern-matching stderr for GraphQL/5xx signatures before deciding whether to try
  REST — adds fragile parsing for no behavioral benefit given the fallback chain lands in the
  same place either way.

### rest-payload-construction

- Decision: Build the REST create request with `gh api`'s own field flags, not a hand-built JSON
  file:
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
- Rationale: `gh api -f`/`-q` handles field encoding and response extraction natively — no
  external `jq`/`python` dependency, no manual JSON-string escaping to get wrong, and it mirrors
  the `-q .url` pattern step 7 already uses (`gh pr view --json url -q .url`). `head` is the bare
  branch name (no `owner:` prefix), consistent with step 10's existing `--head <branch>` usage —
  this skill assumes a same-repo (non-fork) flow throughout, so no cross-repo head format is
  needed here. (The duplicate-pr-detection decision's GET fallback uses the owner-prefixed
  `owner:branch` form instead — that's a different GitHub endpoint with a different field
  requirement, not a contradiction; see that decision's note.)
- Rejected: `jq -n ... > payload.json` + `gh api --input payload.json` (adds an external `jq`
  dependency not otherwise required by this skill, plus a temp-file lifecycle to manage).
  `python -c "import json..."` for the same purpose (heavier than needed, same temp-file issue).

### duplicate-pr-detection

- Decision: Only after **both** the GraphQL create (step 10) and the REST create (step 10.5)
  attempts have failed, inspect the combined failure output for an "already exists" pattern
  (case-insensitive match on GitHub's standard message, e.g. `"A pull request already exists
  for <owner>:<branch>"`). If matched: look up the existing PR's URL (re-run `gh pr view --json
  url -q .url`, or on its failure `gh api repos/<owner>/<repo>/pulls -X GET -f
  head="<owner>:<branch>" -f state=open -q '.[0].html_url'`) and report that URL — do not open the
  browser. If both URL-lookup attempts also fail (double failure — GraphQL and REST both still
  unavailable for the lookup), report "A pull request already exists for this branch, but its URL
  could not be retrieved — check the repository's Pull Requests tab" and stop; do not fall through
  to the browser-compare fallback, since that would still create a *new* PR attempt against a
  branch GitHub has already told us has one.
- Rationale: This is the real gap left by leaving step 7 unchanged (see Scope → Out). Step 7
  treats a GraphQL 5xx as "no PR exists" and proceeds; if a PR genuinely already exists, both
  create attempts will fail with GitHub's standard duplicate-PR message (GraphQL and REST use the
  same wording for this case), which is a reliable, stable signal to check at the single point
  where both tiers have already been tried — cheaper than duplicating the check before every
  tier, and it closes the loop without touching step 7 at all. Unlike the transient-outage error
  text rejected in rest-fallback-trigger (which genuinely drifts across `gh` versions and outage
  types), the "already exists" wording is GitHub's stable, canonical 422/GraphQL response for a
  specific, well-defined condition — that's what makes matching it here reliable where matching
  outage text was not.
  Note also that the GET fallback's `-f head="<owner>:<branch>"` is **not** the same field format
  as rest-payload-construction's create-PR `head` (bare branch name): GitHub's list-pulls endpoint
  requires the owner-prefixed `owner:branch` form for its `head` filter, while create-pulls
  (same-repo) does not. The two commands use different formats because the two endpoints require
  different formats — this is not an inconsistency to reconcile.
- Rejected: Checking the duplicate pattern immediately after the GraphQL failure (before
  attempting REST) — adds an extra branch for a case the post-REST check already covers just as
  correctly. Not special-casing duplicates at all — leaves the operator dropped into a browser
  compare page for a PR that already exists, which is confusing and avoidable.

### doc-structure

- Decision: Insert the REST fallback as a new `### 10.5 REST-API fallback` step between the
  existing step 10 (`Create the PR`) and step 11 (`Fallback to browser`), mirroring the file's
  existing `### 1.5 Detect task branch` sub-step convention. Step 11's trigger condition is
  reworded: browser fallback fires only when `gh` is not installed, or both step 10 and step 10.5
  have failed (and step 10.5's own duplicate-PR check — see duplicate-pr-detection — did not
  already resolve and report a URL). Step 11 also gains an explicit early-exit: skip step 10.5
  entirely (go straight to browser) when `gh` was already determined unavailable in step 7 —
  `gh api` needs the same binary as `gh pr create`.
- Rationale: `1.5` is the file's existing precedent for an inserted sub-step; reusing it keeps
  each tier scannable as its own numbered step rather than burying REST-fallback logic inline
  inside step 10 or forcing an unrelated renumbering of steps 11–12.
- Rejected: Folding the REST attempt inline into step 10's prose (harder to scan, mixes two
  distinct API tiers under one heading). Relettering steps 10–12 into 10a/10b/10c (unnecessary
  churn to existing step numbers that other docs/scripts may reference by number).

### report-wording

- Decision: Step 12 (Report) states the URL as it does today when the default GraphQL `gh pr
  create` path succeeds — no extra wording. When step 10.5 (REST) or step 11 (browser) fired
  instead, step 12 additionally states which tier succeeded, using cause-agnostic phrasing, e.g.
  "PR created via REST API fallback: <url>" or the existing browser-opened wording. Duplicate-PR
  resolution (see duplicate-pr-detection) reports "Existing PR found: <url>".
- Rationale: Keeps the common-case output byte-for-byte unchanged; only surfaces extra
  information when something notable (an outage workaround) actually happened. The wording stays
  cause-agnostic ("REST API fallback", not "GraphQL was unavailable") because rest-fallback-trigger
  deliberately fires step 10.5 on any non-zero exit from step 10 without diagnosing *why* it
  failed — asserting "GraphQL was unavailable" in the report would claim a diagnosis the trigger
  logic never actually made.
- Rejected: Always stating the method regardless of tier (noise on the common path). Never
  disclosing the method (loses useful diagnostic signal for the rare cases operators will want to
  know about, e.g. to notice a GraphQL outage is in progress).

## Technical context

- File to change: `plugins/mill/skills/git-pr/SKILL.md` (this repo, `plugins/mill/skills/git-pr/`).
  Only steps 10, 11, 12 change; steps 1–9 and 13 (none exists beyond 12) are untouched.
- Step 8 already resolves `<owner>/<repo>` before step 10 runs (via `gh repo view --json
  nameWithOwner -q .nameWithOwner`, with a URL-parsing fallback) — step 10.5 reuses that same
  `<owner>/<repo>` value, no new detection needed.
- The same `<branch>` (current branch) and `<base>` (resolved base branch) values from steps 1–2
  and `<title>`/`<body>` from step 9 are reused verbatim for the REST payload — no new content
  generation.
- `gh pr view --json url -q .url` (step 7) and `gh api ... -q .html_url` (new step 10.5) are the
  established `-q`/`--jq`-flag pattern already used in this skill file and elsewhere in the repo
  (e.g. `plugins/mill/skills/mill-merge/SKILL.md` uses `gh pr list ... --jq '.[0]'`) — no new
  external `jq` binary dependency; `gh`'s `-q`/`--jq` flags are built in.
- GitHub's REST create-PR endpoint: `POST /repos/{owner}/{repo}/pulls` with JSON body
  `{title, body, head, base}`, response field `.html_url` on success (HTTP 201), or HTTP 422 with
  a `message` field like `"A pull request already exists for <owner>:<branch>."` on duplicate.
  This is the same duplicate-PR wording GraphQL's `createPullRequest` mutation surfaces, which is
  what makes the case-insensitive `"already exists"` match reliable across both tiers.

## Testing

This is a markdown skill-instructions file, not executable code — there's no unit-test target.
Verification is manual / scenario-walkthrough:

- **Happy path (no regression):** confirm step 10's `gh pr create` command block and step 12's
  default reporting text are byte-identical to before this change when GraphQL succeeds.
- **REST fallback path:** walk through the new step 10.5 instructions as written and confirm the
  `gh api ... -f ... -q .html_url` invocation is syntactically well-formed bash, uses the correct
  endpoint (`repos/<owner>/<repo>/pulls`), and the fields match what step 10's `gh pr create`
  passes (`title`, `body`, `head`, `base` — no extras). Not reproducible against live GitHub
  GraphQL (outage is transient/on-demand only, per the source issue) — a live end-to-end run
  isn't a testing candidate here.
- **Duplicate-PR path:** confirm the "already exists" match wording and the fallback lookup
  command (`gh pr view` retry, then REST `GET .../pulls?head=...&state=open`) are present and
  correctly ordered *after* both create attempts, per the duplicate-pr-detection decision. This is
  a direct check against GitHub's known 422/GraphQL error string — no live-API repro needed to
  validate the doc.
- **Browser-fallback trigger correctness:** confirm step 11's reworded trigger condition
  (`gh` unavailable OR both 10 and 10.5 failed) doesn't regress the existing `gh`-not-installed
  path — that path must still skip straight to browser without attempting step 10.5.

## Q&A log

- **Q:** What should trigger the REST-API fallback attempt at step 10 (`gh pr create` failure)?
  **A:** [auto-pick] Attempt REST fallback on any non-zero exit from `gh pr create`, not only on
  GraphQL-5xx-looking errors. **Why:** avoids fragile message-pattern matching against GitHub's
  error text, which can drift across `gh` versions/outage types; a wasted REST attempt on a
  non-transient failure is cheap and still falls through correctly.
- **Q:** Where should "PR already exists" be detected to avoid needlessly opening a browser?
  **A:** [auto-pick] Only after both the GraphQL create and REST create attempts fail, inspect the
  combined failure output for an "already exists" pattern and report the looked-up URL instead of
  opening the browser. **Why:** a single check at the final fallback boundary is simpler than
  duplicating the check before every tier, and covers the real gap left by step 7 treating a
  GraphQL 5xx the same as "no PR exists."
- **Q:** How should the REST-API request body be constructed?
  **A:** [auto-pick] `gh api ... -f title=... -f body=... -f head=... -f base=... -q .html_url`
  using `gh api`'s own field flags. **Why:** zero new dependencies, no escaping-bug surface, and
  mirrors the `-q .url` pattern the skill already uses in step 7.
- **Q:** Where does the new fallback tier go in the document?
  **A:** [auto-pick] New `### 10.5 REST-API fallback` step between step 10 and step 11, mirroring
  the existing `1.5` sub-step numbering convention already used in this file. **Why:** matches
  this file's existing `1.5` precedent, keeps each tier scannable as its own step.
- **Q:** What should step 12 (Report) say about which tier succeeded?
  **A:** [auto-pick] Only mention the fallback path when a non-default tier was used; say nothing
  extra when the default GraphQL `gh pr create` succeeds. **Why:** keeps the unchanged, common-case
  output exactly as-is; only adds information when something notable (an outage workaround)
  actually happened.
