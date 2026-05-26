# Vociferous Frontend

Svelte 5 + TypeScript + Tailwind CSS v4 frontend for the Vociferous desktop app.

This is a Vite-built SPA served inside the pywebview shell. Backend communication goes through the local Litestar API and WebSocket bridge; state-changing UI actions should dispatch intents instead of reaching around the API boundary.

## Commands

```bash
npm install
npm run check
npm run build
npm run dev
```

## Conventions

- Use Svelte 5 runes for reactivity.
- Keep API calls in `src/lib/api.ts`.
- Keep WebSocket event types and validators in `src/lib/events.ts`.
- Use Tailwind utility classes and the design tokens in `src/app.css`.
- Run `npm run check` before handing off frontend changes.
