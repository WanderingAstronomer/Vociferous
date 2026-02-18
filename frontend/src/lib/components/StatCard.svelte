<script lang="ts">
    /**
     * Reusable stat card for metric display.
     * Two variants: "default" (compact, 4-col grid) and "featured" (larger, accent-bordered).
     */
    import type { Component, SvelteComponent } from "svelte";

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    type IconComponent = Component<any> | (new (...args: any[]) => SvelteComponent);

    interface Props {
        icon: IconComponent;
        value: string;
        label: string;
        sublabel: string;
        variant?: "default" | "featured";
        iconSize?: number;
    }

    let { icon: Icon, value, label, sublabel, variant = "default", iconSize }: Props = $props();

    const isFeatured = $derived(variant === "featured");
    const resolvedIconSize = $derived(iconSize ?? (isFeatured ? 28 : 24));
</script>

<div
    class="flex flex-col items-center gap-1 border rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] transition-[border-color] duration-[var(--transition-fast)] hover:border-[var(--accent)] {isFeatured
        ? 'p-[var(--space-5)] border-[var(--accent-muted)] gap-[var(--space-1)]'
        : 'p-[var(--space-4)] border-[var(--shell-border)]'}"
>
    <div class="{isFeatured ? 'text-[var(--accent)]' : 'text-[var(--text-tertiary)]'} mb-1">
        <Icon size={resolvedIconSize} />
    </div>
    <div
        class="font-[var(--weight-emphasis)] leading-[var(--leading-tight)] {isFeatured
            ? 'text-[2.5rem] text-[var(--accent)]'
            : 'text-[var(--text-lg)] text-[var(--text-primary)]'}"
    >
        {value}
    </div>
    <div class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)]">
        {label}
    </div>
    <div class="text-[var(--text-xs)] text-[var(--text-tertiary)] text-center">
        {sublabel}
    </div>
</div>
