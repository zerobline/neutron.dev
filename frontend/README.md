# Neutron Frontend

Next.js App Router frontend for Neutron, the multi-agent AI development workspace.

## Requirements

- Node.js 20+
- Backend API running on `http://localhost:8000` unless `NEXT_PUBLIC_API_URL` is set.

## Commands

```bash
npm install
npm run dev                 # dev server on http://localhost:3000
npm run build               # production build
npm run lint                # ESLint 9 flat config
npm test -- --run           # Vitest suite
npm test -- --run --coverage # Vitest with 100% coverage gate
```

## Environment

Create `.env.local` when the backend URL differs from the default:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Structure

- `src/app/` — App Router pages for landing, dashboard, templates, profile, and workspace.
- `src/components/` — UI, dashboard, landing, settings, and workspace components.
- `src/hooks/use-websocket.ts` — project WebSocket client.
- `src/stores/project-store.ts` — Zustand workspace runtime state.
- `src/lib/api.ts` — typed API helpers.
- `src/lib/local-settings.ts` — local browser settings and connector persistence.
- `tests/` — Vitest + Testing Library tests.

## Coverage

The frontend is expected to stay at 100% statements, branches, functions, and lines. Add tests for every new branch when implementing UI behavior.
