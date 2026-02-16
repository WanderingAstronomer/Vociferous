<script lang="ts">
    /**
     * Styled button — primary/secondary/destructive variants.
     * Ported from PyQt6 button sizing and styling constants.
     */

    import type { Snippet } from "svelte";

    interface Props {
        variant?: "primary" | "secondary" | "destructive" | "ghost";
        disabled?: boolean;
        onclick?: () => void;
        children?: Snippet;
    }

    let { variant = "primary", disabled = false, onclick, children }: Props = $props();
</script>

<button class="styled-btn {variant}" {disabled} {onclick}>
    {#if children}{@render children()}{/if}
</button>

<style>
    .styled-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: var(--space-1);
        border: none;
        border-radius: var(--radius-md);
        font-family: var(--font-family);
        font-weight: var(--weight-emphasis);
        cursor: pointer;
        transition:
            background var(--transition-fast),
            color var(--transition-fast),
            opacity var(--transition-fast);
        white-space: nowrap;
        user-select: none;
    }

    .styled-btn:disabled {
        opacity: 0.4;
        cursor: not-allowed;
    }

    /* Primary */
    .styled-btn.primary {
        height: var(--btn-height-primary);
        min-width: var(--btn-min-width);
        padding: 0 var(--space-4);
        font-size: var(--text-base);
        background: var(--accent);
        color: var(--gray-0);
    }

    .styled-btn.primary:hover:not(:disabled) {
        background: var(--accent-hover);
    }

    /* Secondary */
    .styled-btn.secondary {
        height: var(--btn-height-secondary);
        padding: 0 var(--space-3);
        font-size: var(--text-sm);
        background: var(--surface-tertiary);
        color: var(--text-primary);
    }

    .styled-btn.secondary:hover:not(:disabled) {
        background: var(--gray-6);
    }

    /* Destructive */
    .styled-btn.destructive {
        height: var(--btn-height-secondary);
        padding: 0 var(--space-3);
        font-size: var(--text-sm);
        background: var(--color-danger-surface);
        color: var(--color-danger);
    }

    .styled-btn.destructive:hover:not(:disabled) {
        background: var(--red-8);
    }

    /* Ghost */
    .styled-btn.ghost {
        height: var(--btn-height-secondary);
        padding: 0 var(--space-2);
        font-size: var(--text-sm);
        background: transparent;
        color: var(--text-secondary);
    }

    .styled-btn.ghost:hover:not(:disabled) {
        color: var(--text-primary);
        background: var(--hover-overlay);
    }
</style>
