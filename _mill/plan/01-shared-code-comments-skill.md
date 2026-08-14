# Batch: shared-code-comments-skill

```yaml
task: Extract a language-agnostic code-comments skill; add a general docstring-length ceiling, purpose-not-mechanism rule, mandatory file/module header, and prohibit measured-result/design-rationale narrative
batch: shared-code-comments-skill
number: 1
cards: 5
verify: null
depends-on: []
```

## Batch Scope

Create the new language-agnostic `code-comments` skill (mirroring `code-quality`'s location and framing) carrying every rule that is — or, after this task, becomes — identical across Go/Python/C#: purpose-not-mechanism, the "many comments needed" refactor-signal corollary, the qualitative length ceiling, the file/module header requirement, no-end-of-line-comments, the line-wrap-style common core, and the four prohibited-patterns entries (comment-out, edit-history, mechanical restatement, measured-result/design-rationale narrative). Then rewrite each of the three per-language `*-comments` skills to point at it (`**Load the `code-comments` skill first.**` as the first line under the H1) and keep only what is genuinely language-specific: placement syntax, per-language examples, and the one rendering-behavior sentence that differs (Go/C# collapse consecutive comment lines into one paragraph; Python preserves literal newlines — see `line-wrap-rendering-paragraph-stays-per-language` in the overview's Shared Decisions). This is one batch because the four files are edited as a single coordinated move: nothing in the per-language files should restate what now lives in the shared file, so the shared file's exact final text must be decided before (and held in context alongside) each per-language trim.

External interface the next batch consumes: `plugins/mill/skills/code-comments/SKILL.md` must exist (with valid `name`/`description` frontmatter) before batch 2 regenerates `SKILLS.md`, since the regeneration scans frontmatter across every `SKILL.md` under `plugins/*/skills/`.

No batch-local decisions beyond the three listed in the overview's `## Shared Decisions` — see `no-redundancy-extraction`, `line-wrap-rendering-paragraph-stays-per-language`, and `end-of-line-comments-no-carveout`.

## Cards

### Card 1: Create the shared `code-comments` skill

- **Context:**
  - `plugins/mill/skills/code-quality/SKILL.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/skills/code-comments/SKILL.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create `plugins/mill/skills/code-comments/SKILL.md` with exactly the following content (frontmatter `name: code-comments`, mirroring `code-quality/SKILL.md`'s frontmatter and H1/framing shape):

````markdown
---
name: code-comments
description: Language-agnostic code comment and documentation rules. Use when writing or reviewing code comments in any language.
---

# Code Comments Skill

Guidelines for code comments and documentation.
Language-agnostic — each language's own `{lang}-comments` skill covers syntax and mechanics on top of this.

---

## Purpose, not mechanism

Doc comments explain **what** a symbol does and **why** it exists — not just a restatement of the name.
Do **not** narrate **how** something works internally (algorithm steps, control flow);
that belongs in the implementation, not the comment.
A reader should understand a symbol's purpose from its signature and doc comment alone, without reading the implementation.

Inline comments explain **why** something is done, never **what** is being done;
the code already shows that.

### Corollary: many comments needed is a refactoring signal

An implementation that seems to need many comments to explain itself is a signal to decompose it into well-named sub-functions with their own docstrings — not evidence that the docstring needs to be longer.

## Length ceiling

Doc comments rarely need to exceed ~10-15 lines.
Longer is a symptom that implementation-narrative has crept into the comment, not a size problem to fix by trimming words.

## File/module header

Every source file must open with a comment describing what the file contains and why it exists, in plain narrative prose.
One to three lines is usually sufficient.
See the per-language skill for exact placement and syntax.

## No end-of-line comments

Comments go on their own line, above the code they describe — never at the end of a code line.
An aligned end-of-line comment in a grouped block forces every sibling line to realign (and shows up in the diff) whenever one identifier's length changes;
an above-line comment avoids that.

## Line-wrap style — semantic line breaks, not fixed-column wrapping

Do not hard-wrap a multi-line comment at a fixed column.
Write one sentence per line instead — a semantic line break — so a diff or review citation lands on the sentence that changed, not the whole comment block.
Break also inside a long sentence, at an internal independent-clause boundary: a comma followed by a coordinating conjunction ("but", "and", "or"),
or a semicolon, where what follows has its own subject and verb.
A comma followed by a coordinating conjunction that joins a list item or a compound predicate does not trigger a break.

When sentence-ending punctuation is ambiguous — for example a period inside a URL, or an abbreviation like "e.g." or "etc." — do not force a break there.
Readability wins over mechanical rule compliance in that edge case.

See the per-language skill for how that language's tooling renders consecutive comment lines.

## Prohibited patterns

- **Never** comment out code.
  Delete it.
  Version control handles history.
- **No edit-history comments** ("added in v2", "removed old logic", "changed from X to Y").
- **No mechanical restatements** — a comment that just restates what the code already says by reading it.
  If code needs a "what" comment, refactor instead.
- **No measured-result or design-rationale narrative** — a doc comment must not contain measured numeric deltas, rejected-alternative trails, or reproduction/incident narrative.
  That belongs in an inline why-comment, `_codeguide/` module docs, or a `Doc/` design-decision note.
````
- **Commit:** `docs(mill): add shared code-comments skill`

### Card 2: Rewrite `golang-comments` to load the shared skill and drop duplicated content

- **Context:**
  - `plugins/mill/skills/code-comments/SKILL.md`
- **Edits:**
  - `plugins/golang/skills/golang-comments/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Replace the entire content of `plugins/golang/skills/golang-comments/SKILL.md` with exactly the following.
  Relative to today's file: adds the Step-0 load line; trims "File-level comments" to Go's placement mechanic only (the "must describe the file" principle now lives in `code-comments`); drops the "Introduction" section entirely (purpose-not-mechanism now lives in `code-comments`); trims "Exported symbol doc comments" to keep only the Go-specific placement/naming-start rule (drops the restated what+why/not-how prose); rewrites the "Constants and variables" example and bullet to remove the end-of-line comment style, per `end-of-line-comments-no-carveout`; trims "Line-wrap style" to keep only the Godoc-collapses-into-one-paragraph sentence (the common rule now lives in `code-comments`); drops "Never comment out code", "No edit-history comments", and "No mechanical restatements" from "Prohibited patterns", keeping only the Go-specific "No `/* block comments */` inside function bodies" entry:

````markdown
---
name: golang-comments
description: Godoc and inline comment rules for Go. Use when writing Go comments.
---

# Comments and Documentation Skill

**Load the `code-comments` skill first.**

Guidelines for code comments and documentation in Go.

---

## File-level comments

Separate the file's header comment from the `package` declaration by a blank line, so it is not parsed as a godoc package comment (see "Package doc comments" below for the no-blank-line form).

**Example:**

```go
// handlers_auth.go implements the HTTP handlers for login, logout, and token refresh.
// Each handler validates the request, delegates to the auth service, and writes a structured JSON response.

package auth
```

---

## Package doc comments

Exactly one file per package must have a godoc package comment (no blank line between comment and `package`).
Use `doc.go` when the package is large;
otherwise put it in the main file.

- The comment must start with `Package <name>`, where `<name>` is the package name.
- Follow with a sentence or paragraph explaining what the package is for and how to use it.

**Example:**

```go
// Package auth provides user authentication and session management.
// It handles login, token validation, and logout for HTTP services.
package auth
```

---

## Exported symbol doc comments

All exported functions, types, methods, variables, and constants must have a doc comment.

**Rules:**

- Place the doc comment immediately before the declaration with no blank line between comment and code.
- Begin the comment with the name of the symbol being documented.

**Bad example:**

```go
// GetUser returns a user.
func GetUser(id int) (*User, error) {
```

**Good example:**

```go
// GetUser retrieves a user by ID from the database.
// It is used during login to load the user's profile and verify credentials.
// Returns an error if the user does not exist or the database query fails.
func GetUser(id int) (*User, error) {
```

---

## Boolean-returning functions

Use "reports whether", not "returns true if".

**Bad example:**

```go
// IsActive returns true if the user is active.
func (u *User) IsActive() bool {
```

**Good example:**

```go
// IsActive reports whether the user's account is currently active.
func (u *User) IsActive() bool {
```

---

## Types

Document what an instance of the type represents, not just its name.

- State the purpose and domain meaning of the type.
- Document the zero value if it is meaningful or if its behavior differs from what a reader might expect.
- Document concurrency safety if the type is used in concurrent code (e.g., "safe for concurrent use" or "not safe for concurrent use without external synchronization").

**Example:**

```go
// User represents an authenticated user in the system.
// The zero User value is not valid and must not be used.
// User is safe for concurrent reads but not concurrent writes.
type User struct {
	ID    int
	Email string
}
```

---

## Methods on a type

Do not repeat the type name in the doc comment;
the receiver is part of the signature.

**Bad example:**

```go
// User deletes the user from the database.
func (u *User) Delete(ctx context.Context) error {
```

**Good example:**

```go
// Delete removes this user from the database.
func (u *User) Delete(ctx context.Context) error {
```

---

## Constants and variables

- Group-level variables and constants get one introductory comment explaining the purpose of the group.
- Individual items get a short comment on the line above when the name alone is insufficient to convey meaning.

**Example:**

```go
// HTTP status codes used by the API.
const (
	// StatusOK indicates the request succeeded.
	StatusOK = 200
	// StatusBadReq indicates the request was malformed.
	StatusBadReq = 400
	// StatusNotFound indicates the resource does not exist.
	StatusNotFound = 404
)
```

---

## Interface implementations

When a method satisfies an interface, write a brief comment acknowledging the delegation if it is non-obvious.
Only write a full doc comment when the implementation adds behavior beyond the interface contract.

**Example:**

```go
// Write implements io.Writer by forwarding to the underlying buffer.
func (b *Buffer) Write(p []byte) (int, error) {
	return b.buf.Write(p)
}
```

---

## Line-wrap style

Godoc collapses consecutive `//` comment lines into one rendered paragraph, the same way CommonMark does for markdown, so a semantic line break is invisible to a reader of the rendered doc.
See the `code-comments` skill for the full line-wrap rule.

**Bad example:**

```go
// LoadPortfolio reads every position file in dir and validates each one against the
// schema. It merges the valid files into a single Portfolio, and it returns an error
// if any file fails validation or two files declare the same position ID.
func LoadPortfolio(dir string) (*Portfolio, error) {
```

**Good example:**

```go
// LoadPortfolio reads every position file in dir and validates each one against the schema.
// It merges the valid files into a single Portfolio,
// and it returns an error if any file fails validation or two files declare the same position ID.
func LoadPortfolio(dir string) (*Portfolio, error) {
```

---

## Inline comments

- Use inline comments only to explain **why**, never **what**.
- If the code needs a "what" comment, the code itself is unclear — refactor instead.

---

## Error handling

Always comment non-obvious error handling choices.

- Use the `fmt.Errorf("context: %w", err)` pattern to wrap errors;
  the `%w` verb preserves the error chain so callers can unwrap it with `errors.Unwrap()` or use `errors.Is()` to check for specific errors.
- Explain why you are wrapping the error and what context it adds.

**Example:**

```go
// Wrap the error with %w to preserve the underlying error chain;
// callers can then use errors.Is() to check if the error is context-specific.
if err := db.Query(ctx, sql); err != nil {
	return fmt.Errorf("load user profile: %w", err)
}
```

---

## Prohibited patterns

- **No `/* block comments */` inside function bodies.**
  Use `//` line comments only.

<!-- Project-specific comments configuration goes here -->
````
- **Commit:** `docs(golang-comments): extract shared rules into code-comments, drop end-of-line const example`

### Card 3: Rewrite `python-comments` to load the shared skill and drop the how-it-works conflict

- **Context:**
  - `plugins/mill/skills/code-comments/SKILL.md`
- **Edits:**
  - `plugins/python/skills/python-comments/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Replace the entire content of `plugins/python/skills/python-comments/SKILL.md` with exactly the following.
  Relative to today's file: adds the Step-0 load line; rewords the intro paragraph to drop "logic" (echoes the how-narration framing being struck); trims "Module docstrings" to Python-specific mechanics only (drops "describe the module's purpose in plain narrative prose" and "for pipeline or orchestration modules, describe the steps performed" — both now covered, correctly, by `code-comments`' file/module header rule); renames "Function docstrings — Google style, narrative depth" to "Function docstrings — Google style" and removes the "How it works — algorithm/logic in numbered steps" requirement, replacing it with the sub-function-decomposition guidance from the `python-how-it-works-conflict` discussion decision; rewrites the "GOOD" example to drop its two-step algorithm narration; rewrites "Inline comments — narrate the reasoning" to drop the "mandatory at each logical step" requirement; trims "Line-wrap style" to keep only Python's own newline-preservation rendering note (the common rule now lives in `code-comments`); removes "Prohibited patterns" entirely (its three entries — comment-out, edit-history, mechanical restatement — are now fully covered by `code-comments` and nothing Python-specific remains):

````markdown
---
name: python-comments
description: Docstring and inline comment rules for Python. Use when writing Python comments.
---

# Comments and Documentation Skill

**Load the `code-comments` skill first.**

Guidelines for docstrings and comments in Python.
The goal is **readable code** — a developer should be able to understand what a module does and why, without tracing through the implementation.

---

## Module docstrings

- Every `.py` file **must** have a module-level docstring — it is the file's header comment.
- Follows the same triple-quote placement as function docstrings (see below): the opening `"""` alone on its own line, text starting on the next line.

## Function docstrings — Google style

- Use **Google-style** docstrings.
- **Multi-line docstrings start the text on the line after the opening `"""`**, never on the same line:

```python
# BAD — text on the same line as opening quotes
def foo():
    """Create random fold assignments for n_rows.

    Returns an array of length n_rows.
    """

# GOOD — opening quotes alone on first line, text starts on the next line
def foo():
    """
    Create random fold assignments for n_rows.

    Returns an array of length n_rows.
    """
```

- Single-line docstrings (rare — only for trivial helpers) keep everything on one line: `"""Return True if x is positive."""`
- **Never write a one-liner that restates the function name.** `def load_data` does not need `"""Load data."""`.
  Either write a substantive docstring or omit it.
- For any non-trivial function, the docstring must be **multi-line** and explain:
  1. **What** the function does at the domain level — not "processes data" but "stitches together a CBI price index from two sources".
  2. **What** it returns — describe the structure, columns, or shape of the output.
- When a function's steps genuinely need explaining, decompose it into named sub-functions that each get their own docstring — the decomposition itself becomes the documentation.
  Only when that isn't practical does a single inline comment inside the function body remain an accepted exception;
  it does not go in the docstring.
- Include `Args:` when parameters carry domain meaning not obvious from the name (e.g., `std_ratio`, `filter_outliers`, `RSI_stop_date`).
- Include `Returns:` when the return value is a complex structure (DataFrame with specific columns, tuple, dict).
- Omit docstrings only on trivial private helpers where the name and signature are self-explanatory.

### Good vs bad examples

```python
# BAD — restates the function name, tells the reader nothing
def create_CBI_from_SSB_and_RSI(SSB_quarterly, RSI_weekly, RSI_stop_date=None):
    """Create CBI from SSB and RSI data."""

# GOOD — explains the domain purpose and the output structure, without narrating the algorithm
def create_CBI_from_SSB_and_RSI(SSB_quarterly, RSI_weekly, RSI_stop_date=None):
    """
    Stitches together a CBI price index from two different price indices,
    preferring SSB_quarterly before RSI_weekly is sufficiently populated and RSI_weekly for the main period.

    Returns: DataFrame with "date" and "price" columns, plus additional information
        on how the index was created, and a "count" column representative of the
        number of transactions used to compute the index.
    """
```

### Class docstrings

- Document the class's purpose and list key instance variables with their meaning.
- Domain-specific abbreviations are acceptable in variable names when the docstring defines them (e.g., `df_MT` — DataFrame of Matched Transactions).

```python
class LORSIPartitionClass:
    """Logarithmic Repeated Sales Index for a single geographic partition.

    Computes LORSI values across date ranges and BRA (floor area) groups.
    Supports filtering, serialization, and conversion to DataFrames.

    Instance variables:
        LORSI: 3D numpy array (geo × BRA × time) of index values.
        count: 3D numpy array of transaction counts per cell.
        BRA_split: boolean array indicating which BRA groups are active.
    """
```

## Section dividers

- In longer modules (200+ lines), use docstring-style section dividers to separate logical groups:

```python
""" FUNCTIONS FOR DATA LOADING """
```

## Inline comments — narrate the reasoning

Inline comments explain the domain reasoning behind a non-obvious step, so a reader can follow the logic without deciphering the code.

- Use an inline comment on a step that isn't self-evident from the code alone — not on every step.
  A function with 5 logical steps does not need 5 comments;
  it needs one wherever the domain reasoning isn't already obvious from well-named identifiers.
- Explain **why this step is needed** and **what domain rule it implements**, not what the code mechanically does.
- Write in natural language: "Extract the date where the CBI data will start.
  This is simply the first date in the SSB data."

### Good vs bad examples

```python
# BAD — mechanical, tells you nothing beyond what the code says
min_date = df["date"].min()  # get min date

# GOOD — explains the domain reasoning behind the operation
# Extract the date where the CBI data will start. This is simply the first date in the SSB data.
CBI_start_date = SSB_quarterly["date"].min()
```

```python
# BAD — no comments, reader must reverse-engineer the filtering logic
df = df.dropna(subset=['grunnkrets_number', 'postcode', 'sold_date', 'location', 'BRA-i', 'price_inc_debt'])
df = df[df['price_inc_debt'] != 0]

# GOOD — explains what data quality rules are being enforced and why
# Remove transactions with missing geographic or property data — these cannot be placed in any partition.
df = df.dropna(subset=['grunnkrets_number', 'postcode', 'sold_date', 'location', 'BRA-i', 'price_inc_debt'])
# Exclude zero-price transactions, which represent non-market transfers (gifts, inheritance).
df = df[df['price_inc_debt'] != 0]
```

## Line-wrap style

Raw Python docstrings preserve literal newlines, so tools like `help()`, `pydoc`, and IDE tooltips display sentence-per-line text as short lines rather than reflowing it into one paragraph.
This is a display difference only — the text stays fully readable,
and the addressing/diff-locality benefit holds regardless of how it renders.
See the `code-comments` skill for the full line-wrap rule.

### Good vs bad examples

```python
# BAD — single unbroken line, hides sentence boundaries from diffs and citations
"""
Loads the raw transaction file and filters out zero-price rows. The result feeds directly into the CBI stitching step, and later steps assume the join has already happened.
"""

# GOOD — one sentence per line, with a clause-boundary break inside the second sentence
"""
Loads the raw transaction file and filters out zero-price rows.
The result feeds directly into the CBI stitching step,
and later steps assume the join has already happened.
"""
```
````
- **Commit:** `docs(python-comments): drop How-it-works narration, extract shared rules into code-comments`

### Card 4: Rewrite `csharp-comments` to load the shared skill and add a file header section

- **Context:**
  - `plugins/mill/skills/code-comments/SKILL.md`
- **Edits:**
  - `plugins/csharp/skills/csharp-comments/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Replace the entire content of `plugins/csharp/skills/csharp-comments/SKILL.md` with exactly the following.
  Relative to today's file: adds the Step-0 load line; adds a new "File header" section (first section, per the `csharp-file-header-syntax` discussion decision — a `///` comment block above `using`/`namespace`, not `/* */`, for consistency with `///` used on every other doc comment in a C# file); trims "XML documentation" to keep only the Go/C#-specific `/// <summary>` requirement (drops the restated what+why/not-how prose); trims "Line-wrap style" to keep only the XML-doc-tooling-collapses-into-one-paragraph sentence (the common rule now lives in `code-comments`); removes "Prohibited patterns" entirely (all three entries — comment-out, edit-history, no-end-of-line-comments — are now fully covered by `code-comments` and nothing C#-specific remains):

````markdown
---
name: csharp-comments
description: XML doc and inline comment rules for C#/.NET. Use when writing C# comments.
---

# Comments and Documentation Skill

**Load the `code-comments` skill first.**

Guidelines for code comments and XML documentation in C#/.NET.

---

## File header

Every `.cs` file must open with a `///` comment block, placed above the `using` statements and the `namespace` declaration.

**Example:**

```csharp
/// OrderProcessor.cs validates, prices, and persists orders for the checkout flow.
/// Each public method corresponds to one stage of the checkout pipeline.

using System;

namespace Checkout
{
```

## XML documentation

- All `public` methods and classes **must** have `/// <summary>` XML doc comments.

## Interface implementations — use `<inheritdoc/>`, never duplicate

- When a class implements an interface member, **never repeat** the interface's `/// <summary>` on the implementation.
- **Always write `/// <inheritdoc/>`** on the implementation.
  This makes the inheritance explicit and signals to future readers (and to Claude) that the doc lives on the interface and no new docstring is needed here.
- Only write a fresh `/// <summary>` on an implementation when it adds information beyond the interface contract, or when the member has no interface counterpart.

## Inline comments

- Use inline comments only to explain **why**, never **what**.
- If the code needs a "what" comment, the code itself is unclear — refactor instead.

## Line-wrap style

XML-doc tooling collapses consecutive `///` comment lines into one rendered paragraph, the same way CommonMark does for markdown, so a semantic line break is invisible to a reader of the rendered doc.
See the `code-comments` skill for the full line-wrap rule.

**Bad example:**

```csharp
/// <summary>
/// Validates the incoming order against the pricing catalog and applies any active
/// discount codes. It then persists the finalized order, and it returns the
/// confirmation number the caller displays to the customer.
/// </summary>
public string ProcessOrder(Order order) {
```

**Good example:**

```csharp
/// <summary>
/// Validates the incoming order against the pricing catalog and applies any active discount codes.
/// It then persists the finalized order,
/// and it returns the confirmation number the caller displays to the customer.
/// </summary>
public string ProcessOrder(Order order) {
```
````

Open edge case (non-blocking, per the `csharp-file-header-syntax` discussion decision): placing `///` above `using`/`namespace` with no declaration directly beneath it may trigger the compiler's CS1587 warning depending on exact placement. If a `.csproj`/`dotnet` toolchain is available in this environment, verify by compiling a throwaway `.cs` file with the proposed header placement; if it warns, note the finding in this card's commit body but do not change the shipped example — this is documented as an open edge case for a future C# batch to resolve, not a blocker for this task. If no `.csproj`/`dotnet` toolchain is available, skip the compile check — it was never required to block completion.
- **Commit:** `docs(csharp-comments): add file header section, extract shared rules into code-comments`

### Card 5: Verify batch 1 — no duplicated content, correct structure

- **Context:**
  - `plugins/mill/skills/code-comments/SKILL.md`
  - `plugins/golang/skills/golang-comments/SKILL.md`
  - `plugins/python/skills/python-comments/SKILL.md`
  - `plugins/csharp/skills/csharp-comments/SKILL.md`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Run these checks and fix any failure by re-editing the offending file from card 1-4's `Requirements:` text before proceeding — this card's job is to confirm cards 1-4 landed exactly as specified, not to make new decisions:
  1. `grep -n "must begin with a comment describing" plugins/golang/skills/golang-comments/SKILL.md` and equivalent greps for the removed purpose-not-mechanism prose, the "How it works" / numbered-algorithm-step language, and the "mandatory" per-step inline-comment language in `python-comments/SKILL.md` — all must return no matches (confirms `## Testing` bullets 1 and 4 in `_mill/discussion.md`).
  2. Confirm the first line under the H1 in each of `golang-comments/SKILL.md`, `python-comments/SKILL.md`, and `csharp-comments/SKILL.md` is exactly `**Load the `code-comments` skill first.**`.
  3. Confirm `plugins/mill/skills/code-comments/SKILL.md` has valid frontmatter (`name: code-comments`, a one-line `description`) and its content matches card 1's `Requirements:` block.
  4. Confirm the "Constants and variables" example in `golang-comments/SKILL.md` has no end-of-line comments (no trailing `//` sharing a line with a constant's value).
  5. Confirm `csharp-comments/SKILL.md`'s "Prohibited patterns" section and `python-comments/SKILL.md`'s "Prohibited patterns" section are both absent (fully removed, not just emptied).
- **Commit:** none

## Batch Tests

`verify:` is `null` for this batch and every batch in this plan — the task only edits Markdown `SKILL.md` prose, so there is no runnable test suite (see `no-automated-tests` in the overview's `## Shared Decisions`). Card 5 performs the manual/textual verification `_mill/discussion.md`'s `## Testing` section specifies, in place of an automated `verify:` command.
