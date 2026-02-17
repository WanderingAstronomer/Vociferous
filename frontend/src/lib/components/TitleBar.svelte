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

    interface Props {
        isRecording?: boolean;
    }

    let { isRecording = false }: Props = $props();

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
            const result = await maximizeWindow();
            if (typeof result.maximized === "boolean") {
                maximized = result.maximized;
            } else {
                maximized = !maximized;
            }
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

<div
    class="flex items-center justify-between h-8 bg-[var(--shell-bg)] border-b border-[var(--shell-border)] shrink-0 select-none pywebview-drag-region"
>
    <div class="flex items-center gap-1.5 pl-3 pointer-events-none pywebview-drag-region">
        <span class="text-xs font-medium text-[var(--text-secondary)] tracking-wide pywebview-drag-region"
            >Vociferous</span
        >
        {#if isRecording}
            <span
                class="inline-flex items-center gap-1 text-[10px] leading-none py-0.5 px-1.5 rounded-full bg-[var(--color-danger-surface)] text-[var(--color-danger)] border border-[var(--color-danger)] pywebview-drag-region"
            >
                <span
                    class="w-1.5 h-1.5 rounded-full bg-[var(--color-danger)] animate-[pulse-dot_1.2s_ease-in-out_infinite]"
                ></span>
                REC
            </span>
        {/if}
    </div>

    <div class="flex items-stretch h-full">
        <button
            class="flex items-center justify-center w-[46px] h-full bg-transparent border-none text-[var(--text-secondary)] cursor-pointer transition-[background,color] duration-100 hover:bg-[var(--hover-overlay)] hover:text-[var(--text-primary)]"
            onclick={handleMinimize}
            aria-label="Minimize"
        >
            <Minus size={14} />
        </button>
        <button
            class="flex items-center justify-center w-[46px] h-full bg-transparent border-none text-[var(--text-secondary)] cursor-pointer transition-[background,color] duration-100 hover:bg-[var(--hover-overlay)] hover:text-[var(--text-primary)]"
            onclick={handleMaximize}
            aria-label={maximized ? "Restore" : "Maximize"}
        >
            {#if maximized}
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.2">
                    <rect x="3" y="5" width="8" height="8" rx="1" />
                    <path d="M5 5V3a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1h-2" />
                </svg>
            {:else}
                <Square size={12} />
            {/if}
        </button>
        <button
            class="flex items-center justify-center w-[46px] h-full bg-transparent border-none text-[var(--text-secondary)] cursor-pointer transition-[background,color] duration-100 hover:bg-[var(--color-danger)] hover:text-white"
            onclick={handleClose}
            aria-label="Close"
        >
            <X size={14} />
        </button>
    </div>
</div>

<style>
    @keyframes pulse-dot {
        0%,
        100% {
            opacity: 1;
        }
        50% {
            opacity: 0.35;
        }
    }
</style>
