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

    const baseClasses =
        "inline-flex items-center justify-center border-none font-semibold cursor-pointer transition-all duration-150 whitespace-nowrap select-none gap-2 rounded-lg disabled:opacity-40 disabled:cursor-not-allowed";

    let variantClasses = $derived.by(() => {
        switch (variant) {
            case "primary":
                return "h-12 min-w-60 px-6 text-base bg-[var(--accent)] text-[var(--gray-0)] hover:not-disabled:bg-[var(--accent-hover)]";
            case "secondary":
                return "h-10 px-4 text-sm bg-[var(--surface-tertiary)] text-[var(--text-primary)] hover:not-disabled:bg-[var(--gray-6)]";
            case "destructive":
                return "h-10 px-4 text-sm bg-[var(--color-danger-surface)] text-[var(--color-danger)] hover:not-disabled:bg-[var(--red-8)]";
            case "ghost":
                return "h-10 px-2 text-sm bg-transparent text-[var(--text-secondary)] hover:not-disabled:text-[var(--text-primary)] hover:not-disabled:bg-[var(--hover-overlay)]";
            default:
                return "";
        }
    });
</script>

<button class="{baseClasses} {variantClasses}" {disabled} {onclick}>
    {#if children}{@render children()}{/if}
</button>
