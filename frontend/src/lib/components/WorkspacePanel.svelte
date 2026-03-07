<script lang="ts">
    /**
     * WorkspacePanel — rounded visual container with subtle border.
     * Ported from PyQt6 WorkspacePanel QPainter-drawn custom widget.
     * Supports editing and recording visual states via props.
     */

    import type { Snippet } from "svelte";

    interface Props {
        editing?: boolean;
        recording?: boolean;
        children?: Snippet;
    }

    let { editing = false, recording = false, children }: Props = $props();

    const baseClasses =
        "flex-1 flex flex-col overflow-hidden bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-xl transition-all duration-250";

    let paddingClasses = $derived.by(() => {
        // Recording: flush bottom so the spectrum grows into the panel edge
        if (recording) return "pt-4 px-4 pb-0";
        return "p-4";
    });

    let stateClasses = $derived.by(() => {
        if (editing) {
            return "border-[var(--accent)] shadow-[0_0_0_1px_var(--accent-muted)]";
        }
        if (recording) {
            return "border-[var(--blue-7)] shadow-[0_0_12px_rgba(90,159,212,0.1)]";
        }
        return "";
    });
</script>

<div class="{baseClasses} {paddingClasses} {stateClasses}">
    {#if children}{@render children()}{/if}
</div>
