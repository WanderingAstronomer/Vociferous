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
</script>

<div class="workspace-panel" class:editing class:recording>
    {#if children}{@render children()}{/if}
</div>

<style>
    .workspace-panel {
        background: var(--surface-secondary);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-lg);
        padding: var(--panel-padding);
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        transition:
            border-color var(--transition-normal),
            box-shadow var(--transition-normal);
    }

    .workspace-panel.editing {
        border-color: var(--accent);
        box-shadow: 0 0 0 1px var(--accent-muted);
    }

    .workspace-panel.recording {
        border-color: var(--blue-7);
        box-shadow: 0 0 12px rgba(90, 159, 212, 0.1);
    }
</style>
