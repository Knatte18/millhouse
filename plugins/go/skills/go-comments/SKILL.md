---
name: go-comments
description: Godoc and inline comment rules for Go. Use when writing Go comments.
---

# Comments and Documentation Skill

Guidelines for code comments and documentation in Go.

---

## Introduction

The goal is to write code with doc comments detailed enough that a reader learning Go understands what a function does, why it exists, and how it works without reading the implementation. Inline comments explain why something is done, not what is being done mechanically.

---

## Package doc comments

Every package must have a package-level documentation comment in exactly one file (either `doc.go` or the main `.go` file of the package).

- The package comment must start with `Package <name>`, where `<name>` is the package name.
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
- Explain **what the symbol does** AND **why it exists** — not just a restatement of the name.
- A reader should understand the symbol's purpose from its signature and doc comment alone, without reading the implementation.

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

Do not repeat the type name in the doc comment; the receiver is part of the signature.

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
- Individual items get short end-of-line comments only when the name alone is insufficient to convey meaning.

**Example:**

```go
// HTTP status codes used by the API.
const (
	StatusOK       = 200  // OK
	StatusBadReq   = 400  // Bad Request
	StatusNotFound = 404  // Not Found
)
```

---

## Interface implementations

When a method satisfies an interface, write a brief comment acknowledging the delegation if it is non-obvious. Only write a full doc comment when the implementation adds behavior beyond the interface contract.

**Example:**

```go
// Write implements io.Writer by forwarding to the underlying buffer.
func (b *Buffer) Write(p []byte) (int, error) {
	return b.buf.Write(p)
}
```

---

## Inline comments — narrate the reasoning

Inline comments are mandatory at each distinct logical step in non-trivial functions. They explain domain reasoning and why a step is needed, not mechanical restatement.

Include one bad/good example pair:

**Bad example:**

```go
func ProcessOrder(order *Order) error {
	// Loop through items
	for _, item := range order.Items {
		// Check if in stock
		if !warehouse.HasStock(item.ID) {
			// Return error
			return fmt.Errorf("item out of stock: %d", item.ID)
		}
		// Decrement stock
		warehouse.DecrementStock(item.ID, item.Qty)
	}
	return nil
}
```

**Good example:**

```go
func ProcessOrder(order *Order) error {
	// Verify all items are in stock before making any changes;
	// if we reserve partway and fail, we must not leak partial reservations.
	for _, item := range order.Items {
		if !warehouse.HasStock(item.ID) {
			return fmt.Errorf("item out of stock: %d", item.ID)
		}
	}

	// Reserve each item. We know they all exist from the check above.
	for _, item := range order.Items {
		warehouse.DecrementStock(item.ID, item.Qty)
	}
	return nil
}
```

Rules:

- Explain **why** this step is needed and what constraint or domain rule it satisfies.
- Do **not** overdo it — trivial operations and obvious control flow need no comment.
- Avoid "what" comments; if the code needs one, refactor for clarity instead.

---

## Error handling

Always comment non-obvious error handling choices.

- Use the `fmt.Errorf("context: %w", err)` pattern to wrap errors; the `%w` verb preserves the error chain so callers can unwrap it with `errors.Unwrap()` or use `errors.Is()` to check for specific errors.
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

- **Never** comment out code. Delete it. Version control handles history.
- **No edit-history comments** ("added in v2", "removed old logic", "changed from X to Y").
- **No `/* block comments */` inside function bodies.** Use `//` line comments only.
- **No mechanical restatements** — if code needs explaining "what", refactor instead.

<!-- Project-specific comments configuration goes here -->
