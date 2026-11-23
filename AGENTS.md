# AI Resume Analyzer

## General Rules

- Preserve the existing architecture unless explicitly instructed otherwise.
- Keep modules small and focused.
- Avoid unnecessary abstractions.
- Follow established project conventions.

## Backend Rules

These rules apply to Python backend code, migrations, and backend tests.
- Follow the existing Clean Architecture.
- Use FastAPI.
- Use uv for package management.
- Use Python 3.13.
- Use type hints consistently.
- Follow the project's Ruff, Black, mypy and make configurations.

## Git Commit Guidelines

1. **Auto-commit after small logical steps:**
   - Always commit your changes immediately after implementing or fixing a small, isolated chunk of work.
   - Do NOT wait until the end of the entire task to create one huge commit.
   - Run tests/type checks (if available) before committing to ensure the build isn't broken.

2. **Commit Message Format:**
   - **Single-line ONLY:** Strictly write 1-line commit messages. Do NOT include a commit body, extended description, or bullet points.
   - Use Conventional Commits (`feat:`, `fix:`, `refactor:`, `style:`, `chore:`).
   - Write short, clear descriptions in English in the imperative mood.