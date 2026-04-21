---
name: linting
description: Project-specific linting and style rules. Use for style decisions.
---

# Linting Skill

Project-specific linting and style rules. Extensible per project.

---

- Discover conventions from the existing codebase before applying new ones.
- When in doubt about a style choice, follow the pattern already established in the project.

## Python rules (observed during Layer 02)

- **Paths:** use `Path` from `pathlib`; never `os.path`.
- **Logging:** no `import logging`; use `print(..., file=sys.stderr)` for progress and errors.
- **File I/O encoding:** always pass `encoding="utf-8"` explicitly on `open()` calls.
- **Subprocess:** no `shell=True`; resolve executables with `shutil.which` before spawning.
- **UTC timestamps:** use `datetime.now(timezone.utc)`; never the deprecated `datetime.utcnow()`.
- **Assertions:** no `assert` where correctness matters (production logic or test verdicts); use explicit `if`/`raise` or `return` instead.
