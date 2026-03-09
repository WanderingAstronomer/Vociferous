<!--
    ToastContainer — renders active toast notifications and confirmation dialogs.

    Mount once at the app root (App.svelte). Toasts stack from
    bottom-right and auto-dismiss after their TTL.
    Confirmations are modal-ish cards: one at a time, FIFO queue.
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
</script>

<svelte:window onkeydown={handleConfirmKeydown} />

<!-- ── Confirmation overlay ── -->
{#if toast.activeConfirm}
    {@const c = toast.activeConfirm}
    <!-- Backdrop dims the world — click to cancel -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
        class="fixed inset-0 z-[210] bg-black/50 flex items-center justify-center animate-fade-in"
        onkeydown={handleConfirmKeydown}
        onclick={() => toast.resolveConfirm(c.id, false)}
    >
        <!-- Card -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
            class="bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] shadow-2xl p-5 w-full max-w-sm mx-4 animate-slide-in"
            role="alertdialog"
            tabindex="-1"
            aria-labelledby="confirm-title"
            aria-describedby="confirm-msg"
            onclick={(e) => e.stopPropagation()}
            onkeydown={(e) => e.stopPropagation()}
        >
            <h3
                id="confirm-title"
                class="text-[var(--text-primary)] text-[var(--text-base)] font-[var(--weight-emphasis)] m-0 mb-2"
            >
                {c.title}
            </h3>
            <p id="confirm-msg" class="text-[var(--text-secondary)] text-[var(--text-sm)] leading-relaxed m-0 mb-5">
                {c.message}
            </p>
            <div class="flex justify-end gap-2">
                <StyledButton size="sm" variant="secondary" onclick={() => toast.resolveConfirm(c.id, false)}>
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
    </div>
{/if}

<!-- ── Toast stack ── -->
{#if toast.items.length > 0}
    <div class="fixed top-12 right-4 z-[200] flex flex-col gap-2 pointer-events-none max-w-[380px]">
        {#each toast.items as item (item.id)}
            {@const Icon = iconMap[item.variant]}
            <div
                class="pointer-events-auto flex items-start gap-2 px-3 py-2.5 rounded-[var(--radius-md)] border bg-[var(--surface-secondary)] shadow-lg animate-slide-in {colorMap[
                    item.variant
                ]}"
                role="alert"
            >
                <Icon size={16} class="shrink-0 mt-0.5" />
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
