# GitHub Copilot Instructions

These instructions apply to all development in this repository. Every contribution must follow the rules below.

## Development Rules

### 1. Tests Are Required

Every code change must include corresponding tests.

- New classes and functions must have unit tests covering expected behaviour, edge cases, and error conditions.
- Tests live in the `tests/` directory and mirror the structure of `src/`.
- Use `pytest` as the test framework, consistent with existing tests.
- Run the full test suite before submitting changes:
  ```bash
  python -m pytest tests/ -v
  ```

### 2. Object-Oriented Design and Code Organisation

All code must be well-structured and follow OOP principles.

- Decompose logic into focused, single-responsibility classes and functions; avoid large monolithic scripts.
- Follow Python naming conventions: `PascalCase` for classes, `snake_case` for functions and variables.
- Group related functionality into modules under `src/` (e.g. `dtm_processor.py`, `mesh_generator.py`).
- Shared CLI options belong in `src/commands/options.py`; new sub-commands each get their own module under `src/commands/`.
- Keep `main.py` as a thin entry point that only registers sub-commands.

### 3. README Must Be Updated

The `README.md` must be kept up to date with every functional change.

- New CLI options or commands → update the **CLI reference** tables.
- New pipeline stages or modules → update the **Pipeline details** and **Project layout** sections.
- New environment variables → update the **Environment variables** table.
- Any change that affects how a user installs, configures, or runs the tool must be reflected in **Quick start** or **Running without Docker**.
