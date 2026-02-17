<script lang="ts">
    import { startKeyCapture, stopKeyCapture } from "../api";
    import { ws } from "../ws";
    import type { KeyCapturedData } from "../events";

    interface Props {
        value: string;
        onchange: (combo: string) => void;
        id?: string;
    }

    let { value, onchange, id }: Props = $props();

    let capturing = $state(false);
    let pendingCombo = $state<{ combo: string; display: string } | null>(null);
    let captureError = $state("");

    let unsubscribe: (() => void) | null = null;

    function startCapture() {
        capturing = true;
        pendingCombo = null;
        captureError = "";

        unsubscribe = ws.on("key_captured", (data: KeyCapturedData) => {
            pendingCombo = { combo: data.combo, display: data.display };
            capturing = false;
            // Auto-accept the captured key
            onchange(data.combo);
            cleanup();
        });

        startKeyCapture().catch((e: unknown) => {
            capturing = false;
            captureError = e instanceof Error ? e.message.replace(/^API\s\d+:\s*/i, "") : "Could not start key capture";
            cleanup();
        });
    }

    function cancelCapture() {
        capturing = false;
        pendingCombo = null;
        stopKeyCapture().catch(() => {});
        cleanup();
    }

    function cleanup() {
        if (unsubscribe) {
            unsubscribe();
            unsubscribe = null;
        }
    }

    function formatDisplay(raw: string): string {
        return raw
            .split("+")
            .map((k) => k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()))
            .join(" + ");
    }
</script>

<div class="flex items-center gap-2 min-h-10" {id}>
    <span
        class="h-10 min-w-[144px] px-[var(--space-2)] inline-flex items-center justify-center rounded-[var(--radius-sm)] border border-[var(--shell-border)] bg-[var(--surface-tertiary)] text-[var(--text-primary)] font-[var(--font-mono)] text-[var(--text-sm)] font-[var(--weight-emphasis)] tracking-wide"
        >{formatDisplay(value || "None")}</span
    >
    {#if capturing}
        <button
            class="h-10 inline-flex items-center gap-1.5 text-[var(--text-xs)] font-[var(--weight-emphasis)] py-1 px-[var(--space-2)] rounded-[var(--radius-sm)] border border-[var(--accent)] bg-[var(--surface-primary)] text-[var(--accent)] cursor-pointer whitespace-nowrap animate-[gentle-pulse_1.5s_ease-in-out_infinite]"
            onclick={cancelCapture}
        >
            <span class="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-[dot-blink_1s_ease-in-out_infinite]"
            ></span> Press a key…
        </button>
    {:else}
        <button
            class="h-10 min-w-[88px] inline-flex items-center justify-center text-[var(--text-xs)] font-[var(--weight-emphasis)] py-1 px-[var(--space-2)] rounded-[var(--radius-sm)] border border-[var(--accent)] bg-[var(--accent)] text-[var(--gray-0)] cursor-pointer whitespace-nowrap transition-[background,border-color,color] duration-[var(--transition-fast)] hover:bg-[var(--accent-hover)] hover:border-[var(--accent-hover)]"
            onclick={startCapture}>Set Key</button
        >
    {/if}
</div>

{#if captureError}
    <div class="mt-1 text-[var(--text-xs)] text-[var(--color-danger)] break-words">{captureError}</div>
{/if}

<style>
    @keyframes gentle-pulse {
        0%,
        100% {
            opacity: 1;
        }
        50% {
            opacity: 0.7;
        }
    }

    @keyframes dot-blink {
        0%,
        100% {
            opacity: 1;
        }
        50% {
            opacity: 0.3;
        }
    }
</style>
