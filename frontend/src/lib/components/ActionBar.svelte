<script lang="ts">
    import type { Snippet } from "svelte";

    interface Props {
        children: Snippet;
        gap?: string; // Tailwind gap class — default gap-2; pass "gap-3" for wider spacing
        padx?: string; // Outer horizontal padding — default "px-4"
    }

    let { children, gap = "gap-2", padx = "px-4" }: Props = $props();
</script>

<div class="shrink-0 {padx} py-2 overflow-y-auto" style="scrollbar-gutter: stable">
    <div class="flex flex-wrap items-center {gap} bg-[var(--surface-secondary)] rounded-lg px-3 py-1.5">
        {@render children()}
    </div>
</div>
