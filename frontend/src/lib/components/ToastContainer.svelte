<!--
    ToastContainer renders passive, non-blocking notifications in a fixed overlay.
    It must never participate in document flow; toasts are feedback, not layout.
-->
<script lang="ts">
    import { toast, type ToastVariant } from "../toast.svelte";
    import { X, CheckCircle, AlertTriangle, AlertCircle, Info } from "lucide-svelte";

    const iconMap: Record<ToastVariant, typeof CheckCircle> = {
        success: CheckCircle,
        error: AlertCircle,
        warning: AlertTriangle,
        info: Info,
    };

    const colorMap: Record<ToastVariant, string> = {
        success: "border-[var(--color-success)] text-[var(--color-success)]",
        error: "border-[var(--color-danger)] text-[var(--color-danger)]",
        warning: "border-yellow-500 text-yellow-400",
        info: "border-[var(--accent)] text-[var(--accent)]",
    };
</script>

{#if toast.items.length > 0}
    <div
        class="absolute left-1/2 bottom-[var(--space-2)] z-[260] flex w-[420px] max-w-[calc(100%_-_32px)] max-h-[calc(100%_-_32px)] -translate-x-1/2 flex-col gap-[var(--space-2)] overflow-hidden pointer-events-none"
        aria-label="Notifications"
    >
        {#each toast.items as item (item.id)}
            {@const Icon = iconMap[item.variant]}
            <div
                class="pointer-events-auto flex items-start gap-[var(--space-2)] rounded-[var(--radius-md)] border bg-[var(--surface-secondary)] px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-sm)] shadow-xl {colorMap[
                    item.variant
                ]}"
                role="alert"
            >
                <Icon size={15} class="mt-0.5 shrink-0" />
                <span class="min-w-0 flex-1 leading-snug text-[var(--text-primary)]">{item.message}</span>
                <button
                    class="shrink-0 cursor-pointer border-none bg-transparent p-0 text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)]"
                    onclick={() => toast.dismiss(item.id)}
                    aria-label="Dismiss notification"
                >
                    <X size={13} />
                </button>
            </div>
        {/each}
    </div>
{/if}
