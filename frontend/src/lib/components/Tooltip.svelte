<script lang="ts">
    import type { Snippet } from "svelte";

    interface Props {
        text: string;
        children: Snippet;
    }

    let { text, children }: Props = $props();
    let visible = $state(false);
    let x = $state(0);
    let y = $state(0);
    let tipEl: HTMLDivElement | undefined = $state(undefined);

    function show(e: MouseEvent) {
        visible = true;
        position(e);
    }

    function move(e: MouseEvent) {
        if (visible) position(e);
    }

    function hide() {
        visible = false;
    }

    function position(e: MouseEvent) {
        x = e.clientX;
        y = e.clientY - 8;
    }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<span class="inline-flex" onmouseenter={show} onmousemove={move} onmouseleave={hide}>
    {@render children()}
</span>

{#if visible}
    <div
        bind:this={tipEl}
        class="fixed z-[9999] max-w-[280px] px-[var(--space-3)] py-[var(--space-2)] rounded-[var(--radius-md)] bg-[var(--surface-secondary)] border border-[var(--shell-border)] text-[var(--text-secondary)] text-[12px] leading-snug shadow-lg pointer-events-none"
        style="left: {x}px; top: {y}px; transform: translate(-50%, -100%);"
    >
        {text}
    </div>
{/if}
