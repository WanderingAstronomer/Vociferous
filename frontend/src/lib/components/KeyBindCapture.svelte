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

    let unsubscribe: (() => void) | null = null;

    function startCapture() {
        capturing = true;
        pendingCombo = null;

        unsubscribe = ws.on("key_captured", (data: KeyCapturedData) => {
            pendingCombo = { combo: data.combo, display: data.display };
            capturing = false;
            // Auto-accept the captured key
            onchange(data.combo);
            cleanup();
        });

        startKeyCapture().catch(() => {
            capturing = false;
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

<div class="keybind-capture" {id}>
    <span class="keybind-current">{formatDisplay(value || "None")}</span>
    {#if capturing}
        <button class="keybind-btn keybind-listening" onclick={cancelCapture}>
            <span class="pulse-dot"></span> Press a key…
        </button>
    {:else}
        <button class="keybind-btn" onclick={startCapture}>Set Key</button>
    {/if}
</div>

<style>
    .keybind-capture {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        min-height: 2.25rem;
    }

    .keybind-current {
        font-family: ui-monospace, "Cascadia Code", "Fira Code", monospace;
        font-size: 0.8rem;
        color: var(--text-primary);
        background: var(--bg-primary);
        border: 1px solid var(--border-subtle);
        border-radius: 0.375rem;
        padding: 0.3rem 0.75rem;
        min-width: 6rem;
        text-align: center;
    }

    .keybind-btn {
        font-size: 0.75rem;
        font-weight: 500;
        padding: 0.3rem 0.75rem;
        border-radius: 0.375rem;
        border: 1px solid var(--border-subtle);
        background: var(--bg-tertiary);
        color: var(--text-secondary);
        cursor: pointer;
        transition: background 0.15s, border-color 0.15s;
        white-space: nowrap;
    }

    .keybind-btn:hover {
        background: var(--bg-hover);
        border-color: var(--accent-primary);
        color: var(--text-primary);
    }

    .keybind-listening {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        border-color: var(--accent-primary);
        color: var(--accent-primary);
        animation: gentle-pulse 1.5s ease-in-out infinite;
    }

    .pulse-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: var(--accent-primary);
        animation: dot-blink 1s ease-in-out infinite;
    }

    @keyframes gentle-pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }

    @keyframes dot-blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }
</style>
