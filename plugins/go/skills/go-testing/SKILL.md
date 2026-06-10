---
name: go-testing
description: Testing conventions for Go projects. Use when writing tests.
---

# Testing Skill

Swappable testing conventions for Go projects. Replace or extend this file to match your test framework.

---

## General Principles

See `@code:testing` for language-agnostic rules (assertion strictness, mock discipline, naming).

---

## Framework: standard `testing` package

Go's built-in test library (`testing`) is the standard framework. No external testing frameworks like testify.

---

## Naming conventions

**Test files:** Files containing tests are named `<name>_test.go` and reside in the same directory as the code they test.

**Test functions:** All test functions are named `TestXxx` with an uppercase first letter after `Test`. The `Xxx` part describes what is being tested.

**Subtests:** Use the underscore as a logical separator in subtest names: `TestFoo_ScenarioName`. This is the one permitted exception to Go's typical naming conventions (which discourage underscores in identifiers).

**Example:**

```go
func TestUserValidation(t *testing.T) {
	t.Run("ValidEmail", func(t *testing.T) {
		// test valid email
	})
	t.Run("InvalidEmail_Empty", func(t *testing.T) {
		// test empty email
	})
}
```

---

## Table-driven tests (the standard pattern)

All tests with multiple scenarios use the table-driven pattern.

**Pattern:**

- Declare a slice named `tests` containing all test cases.
- Each entry is named `tt` (not `tc`, not `case`, just `tt`).
- For each entry, call `t.Run(tt.name, ...)` to execute it as a subtest.
- Use `t.Error` (continues testing) as the default; use `t.Fatal` only when subsequent assertions depend on the success of the current one.

**Error message format:** `"Func(input) = got; want expected"` — actual before expected.

**Example from Technical Context:**

```go
func TestAdd(t *testing.T) {
	tests := []struct {
		name string
		a, b int
		want int
	}{
		{"positive", 2, 3, 5},
		{"negative", -1, -2, -3},
		{"zero", 0, 0, 0},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := Add(tt.a, tt.b)
			if got != tt.want {
				t.Errorf("Add(%d, %d) = %d; want %d", tt.a, tt.b, got, tt.want)
			}
		})
	}
}
```

---

## Test helpers

**Helper functions:** Call `t.Helper()` as the first line of any helper function. This ensures that failure messages report the line in the calling test, not the line inside the helper.

**Teardown:** Use `t.Cleanup(f)` to register cleanup functions. They are called after the test completes, in LIFO order. Prefer `t.Cleanup` over manually deferred cleanup.

**Temporary files:** Use `t.TempDir()` to create a temporary directory that is automatically cleaned up after the test.

**Example:**

```go
func TestFileWriter(t *testing.T) {
	tmpDir := t.TempDir()
	file := filepath.Join(tmpDir, "output.txt")
	// test writes to file
}

func assertNoError(t *testing.T, err error) {
	t.Helper()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}
```

---

## Struct comparison

For complex structs, use `cmp.Diff` from the module `github.com/google/go-cmp/cmp` rather than `reflect.DeepEqual`. The `Diff` function provides human-readable output showing what differs.

**Note:** `github.com/google/go-cmp` is a dependency of the Go project being tested, not of this skill file itself. Import it in your tests as needed.

**Example:**

```go
import "github.com/google/go-cmp/cmp"

func TestUserStruct(t *testing.T) {
	got := parseUser("John Doe")
	want := &User{Name: "John Doe", Email: ""}
	if diff := cmp.Diff(want, got); diff != "" {
		t.Errorf("parseUser() mismatch (-want +got):\n%s", diff)
	}
}
```

---

## Package naming

**Same-package tests:** Test files with `package foo` can access unexported (lowercase) identifiers in the `foo` package. This is allowed and useful for testing internal behavior.

**External tests:** Test files with `package foo_test` test only the exported API and are preferred for library packages. External tests ensure that the public interface works correctly from the perspective of an external user.

**Choose based on your test goals:**
- For low-level unit tests of internal behavior, use same-package tests.
- For integration tests and library packages, use external tests.

---

## Conventions to specify per project

> Replace this section with your test strategy.

### Placeholder: table-driven testing setup

The following conventions are suggested for your project; customize as needed:

- **Test directory:** Tests reside in `*_test.go` files alongside the code they test (standard Go layout).
- **Fixture strategy:** Use `testdata/` subdirectories for fixture files (JSON, YAML, etc.). Load fixtures explicitly in tests.
- **Integration test markers:** Use build tags (`// +build integration`) on integration test files to exclude them from fast unit test runs. Run integration tests separately with `go test -tags=integration ./...`.

<!-- Project-specific testing configuration goes here -->
