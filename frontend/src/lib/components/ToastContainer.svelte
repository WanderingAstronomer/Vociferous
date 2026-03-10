<!--
    ToastContainer — renders active toast notifications and confirmation dialogs
    in a dedicated bottom strip (part of layout flow, not floating).

    Mount once at the app root (App.svelte). Toasts and confirmations render
    in a collapsible bottom strip that pushes content up when active.
-->
<script lang="ts">
    import { toast, type ToastVariant } from "../toast.svelte";
    import { X, CheckCircle, AlertTriangle, AlertCircle, Info } from "lucide-svelte";
    import StyledButton from "./StyledButton.svelte";

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

    function handleConfirmKeydown(e: KeyboardEvent) {
        const c = toast.activeConfirm;
        if (!c) return;
        if (e.key === "Escape") {
            e.preventDefault();
            toast.resolveConfirm(c.id, false);
        } else if (e.key === "Enter") {
            e.preventDefault();
            toast.resolveConfirm(c.id, true);
        }
    }

    // Determine if the strip should be visible
    const isActive = () => toast.items.length > 0 || toast.activeConfirm !== null;
</script>

<svelte:window onkeydown={handleConfirmKeydown} />

<!-- ── Bottom strip (toasts + confirmations) ── -->
<div
    class="shrink-0 relative transition-[max-height,border-color] duration-200 overflow-hidden
    {isActive()
        ? 'border-t border-[var(--shell-border)] max-h-60'
        : 'max-h-0'}"
>
    <!-- Backdrop: only when confirm is active; covers everything above the strip -->
    {#if toast.activeConfirm}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
            class="fixed inset-0 z-[210] bg-black/50"
            onclick={() => toast.activeConfirm && toast.resolveConfirm(toast.activeConfirm.id, false)}
        />
    {/if}

    <!-- Strip body (sits above backdrop) -->
    <div class="relative z-[215] bg-[var(--surface-secondary)] overflow-hidden flex flex-col">
        {#if toast.activeConfirm}
            {@const c = toast.activeConfirm}
            <!-- Confirmation card in strip -->
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div
                class="flex flex-col gap-2.5 p-4 border-t-0"
                role="alertdialog"
                tabindex="-1"
                aria-labelledby="confirm-title"
                aria-describedby="confirm-msg"
                onclick={(e) => e.stopPropagation()}
                onkeydown={(e) => e.stopPropagation()}
            >
                <div>
                    <h3
                        id="confirm-title"
                        class="text-[var(--text-primary)] text-[var(--text-base)] font-[var(--weight-emphasis)] m-0 mb-1"
                    >
                        {c.title}
                    </h3>
                    <p
                        id="confirm-msg"
                        class="text-[var(--text-secondary)] text-[var(--text-sm)] leading-relaxed m-0"
                    >
                        {c.message}
                    </p>
                </div>
                <div class="flex justify-end gap-2">
                    <StyledButton
                        size="sm"
                        variant="secondary"
                        onclick={() => toast.resolveConfirm(c.id, false)}
                    >
                        {c.cancelLabel ?? "Cancel"}
                    </StyledButton>
                    <StyledButton
                        size="sm"
                        variant={c.danger ? "destructive" : "primary"}
                        onclick={() => toast.resolveConfirm(c.id, true)}
                    >
                        {c.confirmLabel ?? "Confirm"}
                    </StyledButton>
                </div>
            </div>
        {:else}
            <!-- Toast list -->
            <div class="flex flex-col gap-1 px-4 py-2">
                {#each toast.items as item (item.id)}
                    {@const Icon = iconMap[item.variant]}
                    <div
                        class="flex items-start gap-2 px-2 py-1.5 rounded-[var(--radius-sm)] border bg-[var(--surface-secondary)] text-[var(--text-sm)] {colorMap[
                            item.variant
                        ]}"
                        role="alert"
                    >
                        <Icon size={14} class="shrink-0 mt-0.5" />
                        <span class="flex-1 text-[var(--text-primary)] leading-snug">{item.message}</span>
                        <button
                            class="shrink-0 bg-transparent border-none cursor-pointer text-[var(--text-tertiary)] hover:text-[var(--text-primary)] p-0 transition-colors"
                            onclick={() => toast.dismiss(item.id)}
                            aria-label="Dismiss"
                        >
                            <X size={12} />
                        </button>
                    </div>
                {/each}
            </div>
        {/if}
    </div>
</div>
