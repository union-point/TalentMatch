# AI Resume Analyzer

## General Rules

- Never rewrite existing architecture without explicit instruction.
- Follow Clean Architecture.
- Use FastAPI.
- Use uv for package management.
- Keep modules small.
- Write type hints everywhere.
- Avoid unnecessary abstractions.

## Coding Style

- Python 3.13
- Ruff
- Black
- mypy compatible


## Git Commit Guidelines

1. **Auto-commit after small logical steps:**
   - Always commit your changes immediately after implementing or fixing a small, isolated chunk of work.
   - Do NOT wait until the end of the entire task to create one huge commit.
   - Run tests/type checks (if available) before committing to ensure the build isn't broken.

2. **Commit Message Format:**
   - **Single-line ONLY:** Strictly write 1-line commit messages. Do NOT include a commit body, extended description, or bullet points.
   - Use Conventional Commits (`feat:`, `fix:`, `refactor:`, `style:`, `chore:`).
   - Write short, clear descriptions in English in the imperative mood.