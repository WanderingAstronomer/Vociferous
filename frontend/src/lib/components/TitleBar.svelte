<script lang="ts">
    /**
     * TitleBar — Custom frameless window title bar.
     *
     * Provides:
     * - Drag region for window movement (pywebview-drag-region class)
     * - App title with icon
     * - Minimize / Maximize / Close buttons
     *
     * Control buttons call REST endpoints which delegate to pywebview window methods.
     * Gracefully no-ops when running in a browser (dev mode).
     */

    import { minimizeWindow, maximizeWindow, closeWindow } from "../api";
    import { Minus, Square, X } from "lucide-svelte";

    let maximized = $state(false);

    async function handleMinimize(): Promise<void> {
        try {
            await minimizeWindow();
        } catch {
            /* dev mode — no pywebview window */
        }
    }

    async function handleMaximize(): Promise<void> {
        try {
            await maximizeWindow();
            maximized = !maximized;
        } catch {
            /* dev mode */
        }
    }

    async function handleClose(): Promise<void> {
        try {
            await closeWindow();
        } catch {
            /* dev mode */
        }
    }
</script>

<div class="titlebar pywebview-drag-region">
    <div class="titlebar-title pywebview-drag-region">
        <span class="titlebar-text pywebview-drag-region">Vociferous</span>
    </div>

    <div class="titlebar-controls">
        <button class="titlebar-btn" onclick={handleMinimize} aria-label="Minimize">
            <Minus size={14} />
        </button>
        <button class="titlebar-btn" onclick={handleMaximize} aria-label={maximized ? "Restore" : "Maximize"}>
            {#if maximized}
                <!-- Restore icon: two overlapping squares -->
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.2">
                    <rect x="3" y="5" width="8" height="8" rx="1" />
                    <path d="M5 5V3a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1h-2" />
                </svg>
            {:else}
                <Square size={12} />
            {/if}
        </button>
        <button class="titlebar-btn titlebar-btn-close" onclick={handleClose} aria-label="Close">
            <X size={14} />
        </button>
    </div>
</div>

<style>
    .titlebar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        height: 32px;
        background: var(--shell-bg);
        border-bottom: 1px solid var(--shell-border);
        flex-shrink: 0;
        user-select: none;
        -webkit-user-select: none;
    }

    .titlebar-title {
        display: flex;
        align-items: center;
        gap: 6px;
        padding-left: 12px;
        pointer-events: none;
    }

    .titlebar-text {
        font-size: 12px;
        font-weight: 500;
        color: var(--text-secondary);
        letter-spacing: 0.02em;
    }

    .titlebar-controls {
        display: flex;
        align-items: stretch;
        height: 100%;
    }

    .titlebar-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 46px;
        height: 100%;
        background: transparent;
        border: none;
        color: var(--text-secondary);
        cursor: pointer;
        transition: background 0.1s, color 0.1s;
    }

    .titlebar-btn:hover {
        background: var(--hover-overlay);
        color: var(--text-primary);
    }

    .titlebar-btn-close:hover {
        background: var(--color-danger);
        color: white;
    }
</style>
