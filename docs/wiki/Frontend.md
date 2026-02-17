# Frontend

## Stack

- **Svelte 5** with Runes reactivity (`$state`, `$derived`, `$effect`)
- **Tailwind CSS v4** (utility-first, no `<style>` blocks)
- **Vite 6** (dev server + production build)
- **TypeScript** in strict mode

## Architecture

The frontend is a single-page application served by the Python backend. It communicates exclusively through:

- **REST API** (`/api/*`) for actions and queries
- **WebSocket** (`/ws`) for real-time state updates

The frontend treats the backend as a remote server, even though both run locally.

## Reactivity Model (Svelte 5 Runes)

All state management uses Svelte 5 Runes — **no legacy stores or `export let` syntax**.

### State Files

- **`stores.svelte.ts`** — Global reactive state (transcripts, config, recording status, connection state)
- **`selection.svelte.ts`** — Multi-selection manager (shared across HistoryView, SearchView, ProjectsView)
- **`navigation.svelte.ts`** — View routing and navigation state

### Patterns

```typescript
// Reactive state declaration
let transcripts = $state<Transcript[]>([]);

// Derived computation
let filteredCount = $derived(transcripts.filter(t => t.project_id === activeProject).length);

// Side effects
$effect(() => {
    if (isConnected) fetchTranscripts();
});
```

## Component Structure

### Views (Page-Level)

| Component | Purpose |
|-----------|---------|
| `HistoryView.svelte` | Transcript list with multi-select, batch delete, batch project assignment |
| `SearchView.svelte` | Full-text search with multi-select, same batch operations |
| `SettingsView.svelte` | Configuration UI with grouped settings, custom dropdowns |
| `UserView.svelte` | User profile, display name |
| `ProjectsView.svelte` | Project tree with nested hierarchies, multi-select, batch operations |

### Shared Components

Located in `frontend/src/lib/components/` (or inline in views):

- Custom `<select>` replacement for Tailwind-styled dropdowns
- Selection toolbar (appears when items are selected)
- Project assignment modal

## Multi-Selection System

The `SelectionManager` class (`selection.svelte.ts`) provides consistent multi-select behavior across all list views:

### Interaction Model

| Action | Behavior |
|--------|----------|
| Click | Select single item, clear others |
| Ctrl+Click | Toggle item in/out of selection |
| Shift+Click | Range select from last clicked item |
| Ctrl+A | Select all visible items |
| Escape | Clear selection |

### Batch Operations

When items are selected, a toolbar appears with available actions:
- **Delete** — Batch delete with confirmation
- **Assign Project** — Move selected items to a project
- **Remove from Project** — Unassign project from selected items

## API Client

`frontend/src/lib/api.ts` handles all backend communication:

```typescript
// REST calls
const response = await api.get('/api/transcripts');
const result = await api.post('/api/intents', { type: 'delete_transcript', payload: { id } });

// WebSocket connection (auto-reconnect)
const ws = connectWebSocket((event) => {
    // Handle incoming state updates
});
```

## Build & Development

```bash
cd frontend

# Development with hot reload
npm run dev          # Starts Vite dev server on :5173

# Production build
npm run build        # Outputs to frontend/dist/

# Type checking
npm run check        # Runs svelte-check
```

## Design Tokens

The app uses a consistent color and spacing system via Tailwind CSS v4:

- Dark theme with `zinc` gray palette
- Accent colors for interactive elements
- Consistent spacing scale
- Responsive text sizing

## Key Conventions

1. **No `<style>` blocks** — Use Tailwind utilities exclusively (exception: custom animations)
2. **No legacy Svelte** — Runes only (`$state`, `$derived`, `$effect`), no `writable()` stores
3. **Strict TypeScript** — No `any` types, all API payloads have defined interfaces
4. **Component isolation** — Views don't import from each other; shared logic lives in `lib/`
