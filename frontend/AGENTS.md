# TalentMatch Frontend

## General Rules

- Never rewrite existing architecture without explicit instruction.
- Use Vite + React + TypeScript.
- Use TailwindCSS for styling.
- Use Shadcn/ui for pre-built components.
- Use TanStack Query for all server-state.
- Keep components small and focused.
- Write TypeScript types for everything.
- Don't study the backend .py files.

## Coding Style

- TypeScript strict mode.
- Functional components only.
- Named exports.
- Files under 300 lines.
- No comments unless asked.

## Technology Stack

- Framework: Vite + React
- Styling: TailwindCSS + Shadcn/ui
- Data Fetching: TanStack Query (React Query)
- Routing: React Router v6
- Icons: Lucide React
- Build: Vite


## API Integration

- Follow existing API client conventions in `src/lib/api.ts`.
- Do not invent API endpoints or response schemas.
- When API contract verification is necessary, prefer the
  live FastAPI OpenAPI schema at `http://localhost:8000/openapi.json`,
  if the backend is running.
- The Vite proxy forwards `/api` requests to the backend.
- Do not inspect backend Python files unless explicitly requested.

## File Structure

```
src/
  main.tsx          # Entry point
  App.tsx            # Routes
  app.css            # Tailwind imports
  lib/
    api.ts           # Fetch wrapper
    utils.ts         # cn() helper
  types/             # TypeScript interfaces
  hooks/             # React Query hooks
  components/        # Reusable components
  pages/             # Route pages
```
