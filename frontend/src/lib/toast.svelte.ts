/**
 * Global toast notification system.
 *
 * Uses Svelte 5 runes ($state) for a dead-simple reactive store.
 * Any component can `import { toast } from '../lib/toast.svelte'` and fire
 * `toast.push("Something happened", "success")`.
 *
 * ToastContainer.svelte reads `toast.items` and renders them.
 */

export type ToastVariant = "success" | "error" | "warning" | "info";

export interface ToastItem {
    id: number;
    message: string;
    variant: ToastVariant;
    expiresAt: number;
}

let _nextId = 0;
const DEFAULT_DURATION_MS = 4000;

/** Reactive array of active toasts. Read by ToastContainer. */
let items = $state<ToastItem[]>([]);

function push(message: string, variant: ToastVariant = "info", durationMs = DEFAULT_DURATION_MS): void {
    const id = ++_nextId;
    const expiresAt = Date.now() + durationMs;
    items = [...items, { id, message, variant, expiresAt }];

    setTimeout(() => {
        dismiss(id);
    }, durationMs);
}

function dismiss(id: number): void {
    items = items.filter((t) => t.id !== id);
}

export const toast = {
    get items() {
        return items;
    },
    push,
    dismiss,
    success: (msg: string, duration?: number) => push(msg, "success", duration),
    error: (msg: string, duration?: number) => push(msg, "error", duration),
    warning: (msg: string, duration?: number) => push(msg, "warning", duration),
    info: (msg: string, duration?: number) => push(msg, "info", duration),
};
