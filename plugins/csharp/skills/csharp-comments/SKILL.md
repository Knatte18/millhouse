---
name: csharp-comments
description: XML doc and inline comment rules for C#/.NET. Use when writing C# comments.
---

# Comments and Documentation Skill

Guidelines for code comments and XML documentation in C#/.NET.

---

## XML documentation

- All `public` methods and classes **must** have `/// <summary>` XML doc comments.
- The doc comment should explain **what** the method does and **why** it exists.
- A reader should understand the method's purpose from its signature + doc comment alone, without reading the implementation.

## Interface implementations — use `<inheritdoc/>`, never duplicate

- When a class implements an interface member, **never repeat** the interface's `/// <summary>` on the implementation.
- **Always write `/// <inheritdoc/>`** on the implementation. This makes the inheritance explicit and signals to future readers (and to Claude) that the doc lives on the interface and no new docstring is needed here.
- Only write a fresh `/// <summary>` on an implementation when it adds information beyond the interface contract, or when the member has no interface counterpart.

## Inline comments

- Use inline comments only to explain **why**, never **what**.
- If the code needs a "what" comment, the code itself is unclear — refactor instead.

## Line-wrap style — semantic line breaks, not fixed-column wrapping

Do not hard-wrap a multi-line `/// <summary>` or inline comment at a fixed column.
Write one sentence per line instead — a semantic line break — so a diff or review citation lands on the sentence that changed, not the whole comment block.
Break also inside a long sentence, at an internal independent-clause boundary: a comma followed by a coordinating conjunction ("but", "and", "or"), or a semicolon, where what follows has its own subject and verb.
A comma followed by a coordinating conjunction that joins a list item or a compound predicate does not trigger a break.

XML-doc tooling collapses consecutive `///` comment lines into one rendered paragraph, the same way CommonMark does for markdown, so a semantic line break is invisible to a reader of the rendered doc.

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

## Prohibited patterns

- **Never** comment out code. Delete it. Version control handles history.
- **No edit-history comments** ("added in v2", "removed old logic", "changed from X to Y").
- **No end-of-line comments.** Place comments on their own line above the code.
