<!--
    ToastContainer — renders active toast notifications.

    Mount once at the app root (App.svelte). Toasts stack from
    bottom-right and auto-dismiss after their TTL.
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
    <div class="fixed bottom-4 right-4 z-[200] flex flex-col-reverse gap-2 pointer-events-none max-w-[380px]">
        {#each toast.items as item (item.id)}
            <div
                class="pointer-events-auto flex items-start gap-2 px-3 py-2.5 rounded-[var(--radius-md)] border bg-[var(--surface-secondary)] shadow-lg animate-slide-in {colorMap[
                    item.variant
                ]}"
                role="alert"
            >
                <svelte:component this={iconMap[item.variant]} size={16} class="shrink-0 mt-0.5" />
                <span class="flex-1 text-[var(--text-sm)] text-[var(--text-primary)] leading-snug">{item.message}</span>
                <button
                    class="shrink-0 bg-transparent border-none cursor-pointer text-[var(--text-tertiary)] hover:text-[var(--text-primary)] p-0"
                    onclick={() => toast.dismiss(item.id)}
                    aria-label="Dismiss"
                >
                    <X size={14} />
                </button>
            </div>
        {/each}
    </div>
{/if}

<style>
    @keyframes slide-in {
        from {
            opacity: 0;
            transform: translateX(20px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    :global(.animate-slide-in) {
        animation: slide-in 0.2s ease-out;
    }
</style>
