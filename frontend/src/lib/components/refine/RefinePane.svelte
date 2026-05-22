<!--
    RefinePane — shared layout shell for the original/refined panels in RefineView.

    Renders the bordered container, the header row with start/end action slots and a
    centered title, and the scrollable body. Content semantics (loading, errors, diff,
    edit handlers, etc.) live in the parent.
-->
<script lang="ts">
    import type { Snippet } from "svelte";

    interface Props {
        title: string;
        muted?: boolean;
        headerStart?: Snippet;
        headerEnd?: Snippet;
        children: Snippet;
    }

    let { title, muted = false, headerStart, headerEnd, children }: Props = $props();
</script>

<div
    class="flex-1 flex flex-col border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] overflow-hidden transition-opacity duration-200"
    class:opacity-60={muted}
>
    <div class="flex items-center py-[var(--space-3)] px-[var(--space-4)] border-b border-[var(--shell-border)]">
        <div class="flex items-center gap-1 w-10">
            {#if headerStart}{@render headerStart()}{/if}
        </div>
        <h3
            class="m-0 flex-1 text-center text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-secondary)]"
        >
            {title}
        </h3>
        <div class="flex items-center gap-1 w-10 justify-end">
            {#if headerEnd}{@render headerEnd()}{/if}
        </div>
    </div>
    <div class="flex-1 overflow-y-auto p-[var(--space-4)]">
        {@render children()}
    </div>
</div>
