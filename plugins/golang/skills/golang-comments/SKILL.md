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
